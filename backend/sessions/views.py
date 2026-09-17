from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from llm.client import GeminiClient
from llm.exceptions import LLMError, LLMRateLimitError

from .models import GeneratedPrompt, PromptSession, Specification
from .serializers import (
    AnswersSerializer, CreateSessionSerializer, CustomRequirementsSerializer,
    PromptSessionSerializer, SpecificationSerializer, SpecificationUpdateSerializer,
)
from accounts.authentication import SupabaseJWTAuthentication


def get_session(session_id):
    return get_object_or_404(
        PromptSession.objects.select_related("specification", "generated_prompt"),
        id=session_id,
    )


def can_access(request, session):
    return (
        session.user_id is None
        or (request.user is not None and request.user.is_authenticated and session.user_id == request.user.id)
    )


def require_session_access(request, session):
    if not can_access(request, session):
        return Response({"error": {"message": "Session not found."}}, status=404)
    return None


def error_response(exc):
    if isinstance(exc, LLMRateLimitError):
        code = "rate_limited"
    elif "specification" in str(exc).lower():
        code = "malformed_json"
    else:
        code = "llm_error"
    return Response({"error": {"code": code, "message": str(exc)}}, status=503)


class SessionCollectionView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        if request.user is None or not request.user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=401)
        sessions = PromptSession.objects.filter(user=request.user).order_by("-created_at")
        return Response(PromptSessionSerializer(sessions, many=True).data)

    def post(self, request):
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_input = serializer.validated_data["raw_input"]
        category = serializer.validated_data["target_category"]
        session = PromptSession.objects.create(
            raw_input=raw_input, target_category=category,
            status=PromptSession.Status.ANALYZING,
            user=request.user if request.user is not None and request.user.is_authenticated else None,
        )
        try:
            analysis = GeminiClient().analyze(raw_input, category)
        except LLMError as exc:
            session.status = PromptSession.Status.ERROR
            session.save(update_fields=["status", "updated_at"])
            return error_response(exc)
        unknowns = [item.model_dump() for item in analysis.unknowns[:4]]
        Specification.objects.create(
            session=session, goal=analysis.goal, requirements=analysis.requirements,
            preferences=analysis.preferences, constraints=analysis.constraints,
            assumptions=analysis.assumptions, unknowns=unknowns,
        )
        session.status = (
            PromptSession.Status.AWAITING_ANSWERS if unknowns
            else PromptSession.Status.AWAITING_CUSTOM_REQS
        )
        session.save(update_fields=["status", "updated_at"])
        return Response(PromptSessionSerializer(session).data, status=201)


class SessionDetailView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, session_id):
        session = get_session(session_id)
        denied = require_session_access(request, session)
        if denied:
            return denied
        return Response(PromptSessionSerializer(session).data)


class AnswersView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]

    def patch(self, request, session_id):
        session = get_session(session_id)
        denied = require_session_access(request, session)
        if denied:
            return denied
        serializer = AnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data
        if any("question" not in item or "answer" not in item for item in answers):
            return Response({"error": {"message": "Each answer must include question and answer."}}, status=400)
        existing = {
            item["question"]: item
            for item in session.specification.answers
            if isinstance(item, dict) and "question" in item
        }
        existing.update({item["question"]: item for item in answers})
        session.specification.answers = list(existing.values())
        session.specification.save(update_fields=["answers"])
        session.status = PromptSession.Status.AWAITING_CUSTOM_REQS
        session.save(update_fields=["status", "updated_at"])
        return Response(PromptSessionSerializer(session).data)


class CustomRequirementsView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]

    def patch(self, request, session_id):
        session = get_session(session_id)
        denied = require_session_access(request, session)
        if denied:
            return denied
        serializer = CustomRequirementsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        custom = serializer.validated_data["custom_requirements"]
        spec = session.specification
        if custom.strip().lower() in {
            "",
            "none",
            "no additional requirements",
            "no additional requirements.",
            "nothing",
            "nothing else",
        }:
            added_preferences = []
            added_constraints = []
            conflicts = []
        else:
            try:
                merge = GeminiClient().merge_custom_requirements(
                    SpecificationSerializer(spec).data, custom
                )
            except LLMError as exc:
                return error_response(exc)
            added_preferences = merge.added_preferences
            added_constraints = merge.added_constraints
            conflicts = merge.conflicts
        spec.custom_requirements = custom
        spec.preferences = list(dict.fromkeys(spec.preferences + added_preferences))
        spec.constraints = list(dict.fromkeys(spec.constraints + added_constraints))
        if conflicts:
            spec.assumptions = list(dict.fromkeys(
                spec.assumptions
                + [f"Custom requirement conflict: {item}" for item in conflicts]
            ))
        spec.save()
        session.status = PromptSession.Status.READY_FOR_REVIEW
        session.save(update_fields=["status", "updated_at"])
        return Response(PromptSessionSerializer(session).data)


class SpecificationView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]

    def patch(self, request, session_id):
        session = get_session(session_id)
        denied = require_session_access(request, session)
        if denied:
            return denied
        serializer = SpecificationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(session.specification, field, value)
        session.specification.save()
        session.status = PromptSession.Status.READY_FOR_REVIEW
        session.save(update_fields=["status", "updated_at"])
        return Response(PromptSessionSerializer(session).data)


class BackView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]

    previous_statuses = {
        PromptSession.Status.AWAITING_CUSTOM_REQS: PromptSession.Status.AWAITING_ANSWERS,
        PromptSession.Status.READY_FOR_REVIEW: PromptSession.Status.AWAITING_CUSTOM_REQS,
        PromptSession.Status.COMPLETE: PromptSession.Status.READY_FOR_REVIEW,
    }

    def post(self, request, session_id):
        session = get_session(session_id)
        denied = require_session_access(request, session)
        if denied:
            return denied
        previous_status = self.previous_statuses.get(session.status)
        if previous_status is None:
            return Response(
                {"error": {"message": "This step cannot go back."}},
                status=409,
            )
        session.status = previous_status
        session.save(update_fields=["status", "updated_at"])
        return Response(PromptSessionSerializer(session).data)


class GenerateView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        session = get_session(session_id)
        denied = require_session_access(request, session)
        if denied:
            return denied
        session.status = PromptSession.Status.GENERATING
        session.save(update_fields=["status", "updated_at"])
        try:
            content = GeminiClient().generate(
                SpecificationSerializer(session.specification).data,
                session.target_category,
            )
        except LLMError as exc:
            session.status = PromptSession.Status.ERROR
            session.save(update_fields=["status", "updated_at"])
            return error_response(exc)
        GeneratedPrompt.objects.update_or_create(session=session, defaults={"content": content})
        session.status = PromptSession.Status.COMPLETE
        session.save(update_fields=["status", "updated_at"])
        return Response(PromptSessionSerializer(session).data)
