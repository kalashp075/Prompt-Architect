import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from llm.client import GeminiClient
from llm.exceptions import LLMError, LLMRateLimitError

from .models import GeneratedPrompt, PromptSession, Specification
from .serializers import (
    AnswersSerializer, CreateSessionSerializer, CustomRequirementsSerializer,
    PromptSessionSerializer, QuestionAnswerSerializer, SpecificationSerializer,
    SpecificationUpdateSerializer,
)
from accounts.authentication import SupabaseJWTAuthentication


QUESTION_LIMITS = {
    PromptSession.TargetCategory.GENERAL: 8,
    PromptSession.TargetCategory.DESIGN: 8,
    PromptSession.TargetCategory.FRONTEND: 10,
    PromptSession.TargetCategory.BACKEND: 10,
    PromptSession.TargetCategory.FULLSTACK: 10,
}


def get_session(session_id, *, lock=False):
    queryset = PromptSession.objects.select_related("specification", "generated_prompt")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    session = get_object_or_404(
        queryset,
        id=session_id,
    )
    if session.status in {
        PromptSession.Status.ANALYZING,
        PromptSession.Status.GENERATING_ASSUMPTIONS,
        PromptSession.Status.GENERATING,
    } and session.processing_started_at and session.processing_started_at < timezone.now() - timedelta(minutes=10):
        session.status = PromptSession.Status.ERROR
        session.processing_started_at = None
        session.save(update_fields=["status", "processing_started_at", "updated_at"])
    return session


def can_access(request, session):
    if session.user_id is None:
        supplied = request.headers.get("X-Session-Token", "")
        if settings.TESTING and not session.possession_token_hash:
            return True
        return bool(supplied) and secrets.compare_digest(
            session.possession_token_hash,
            hashlib.sha256(supplied.encode()).hexdigest(),
        )
    return (
        request.user is not None and request.user.is_authenticated and session.user_id == request.user.id
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


def specification_data(session):
    return SpecificationSerializer(session.specification).data


def history_data(session):
    return session.specification.answers


def normalized_history(history):
    return [
        {
            **item,
            "provenance": item.get(
                "provenance",
                "skipped" if item.get("skipped") else "confirmed",
            ),
        }
        for item in history
        if isinstance(item, dict) and item.get("question")
    ]


def apply_assumption_result(session, analysis):
    spec = session.specification
    spec.goal = analysis.goal
    spec.requirements = analysis.requirements
    spec.preferences = analysis.preferences
    spec.constraints = analysis.constraints
    spec.assumptions = analysis.assumptions
    spec.assumption_provenance = (
        [item.model_dump() for item in analysis.assumption_provenance]
        or [
            {"text": item, "source": "ai_assumption"}
            for item in analysis.assumptions
        ]
    )
    spec.unknowns = [item.model_dump() for item in analysis.unknowns[:4]]
    spec.save()
    session.current_question = ""
    session.status = PromptSession.Status.AWAITING_CUSTOM_REQS
    session.processing_started_at = None
    session.save(update_fields=["current_question", "status", "processing_started_at", "updated_at"])


class SessionCollectionView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "gemini"

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
        possession_token = secrets.token_urlsafe(32)
        session = PromptSession.objects.create(
            raw_input=raw_input, target_category=category,
            status=PromptSession.Status.ANALYZING,
            user=request.user if request.user is not None and request.user.is_authenticated else None,
            possession_token_hash=hashlib.sha256(possession_token.encode()).hexdigest(),
            processing_started_at=timezone.now(),
        )
        try:
            analysis = GeminiClient().analyze(raw_input, category)
        except LLMError as exc:
            session.status = PromptSession.Status.ERROR
            session.processing_started_at = None
            session.save(update_fields=["status", "processing_started_at", "updated_at"])
            return error_response(exc)
        unknowns = [item.model_dump() for item in analysis.unknowns[:4]]
        question_limit = QUESTION_LIMITS[category]
        Specification.objects.create(
            session=session, goal=analysis.goal, requirements=analysis.requirements,
            preferences=analysis.preferences, constraints=analysis.constraints,
            assumptions=analysis.assumptions, unknowns=unknowns,
            assumption_provenance=(
                [item.model_dump() for item in analysis.assumption_provenance]
                or [
                {"text": item, "source": "ai_analysis"}
                for item in analysis.assumptions
                ]
            ),
        )
        session.question_limit = question_limit
        session.status = PromptSession.Status.AWAITING_ANSWERS
        session.current_question = unknowns[0]["question"] if unknowns else ""
        session.processing_started_at = None
        session.save(
            update_fields=[
                "question_limit", "current_question", "status", "processing_started_at", "updated_at",
            ]
        )
        if not session.current_question:
            try:
                question = GeminiClient().next_question(
                    raw_input, category, specification_data(session), []
                )
            except LLMError as exc:
                session.status = PromptSession.Status.ERROR
                session.processing_started_at = None
                session.save(update_fields=["status", "processing_started_at", "updated_at"])
                return error_response(exc)
            session.current_question = question.question
            session.save(update_fields=["current_question", "updated_at"])
        payload = PromptSessionSerializer(session).data
        if session.user_id is None:
            payload["session_token"] = possession_token
        return Response(payload, status=201)


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


class QuestionAnswerView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "gemini"

    def post(self, request, session_id):
        serializer = QuestionAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answer = serializer.validated_data.get("answer", "").strip()
        skipped = serializer.validated_data["skipped"]
        if not skipped and not answer:
            return Response(
                {"error": {"message": "Provide an answer or mark the question as skipped."}},
                status=400,
            )
        if skipped:
            answer = ""
        with transaction.atomic():
            session = get_session(session_id, lock=True)
            denied = require_session_access(request, session)
            if denied:
                return denied
            if session.status != PromptSession.Status.AWAITING_ANSWERS:
                return Response(
                    {"error": {"message": "This session is not accepting clarification answers."}},
                    status=409,
                )
            if session.processing_started_at and session.processing_started_at > timezone.now() - timedelta(minutes=10):
                return Response({"error": {"message": "Another clarification request is already being processed."}}, status=409)
            question = session.current_question.strip()
            if not question:
                return Response(
                    {"error": {"message": "This session has no active clarification question."}},
                    status=409,
                )
            history = normalized_history(session.specification.answers)
            history.append({
                "question": question,
                "answer": answer,
                "skipped": skipped,
                "provenance": "skipped" if skipped else "confirmed",
            })
            session.specification.answers = history
            session.specification.save(update_fields=["answers"])
            session.question_count += 1
            session.processing_started_at = timezone.now()
            if session.question_count >= session.question_limit:
                session.assumptions_requested = True
                session.status = PromptSession.Status.GENERATING_ASSUMPTIONS
                session.save(
                    update_fields=[
                        "question_count", "assumptions_requested", "status",
                        "processing_started_at", "updated_at",
                    ]
                )
            else:
                session.save(update_fields=["question_count", "processing_started_at", "updated_at"])
        if session.question_count >= session.question_limit:
            try:
                analysis = GeminiClient().generate_assumptions(
                    session.raw_input,
                    session.target_category,
                    specification_data(session),
                    history,
                )
            except LLMError as exc:
                session.status = PromptSession.Status.ERROR
                session.processing_started_at = None
                session.save(update_fields=["status", "processing_started_at", "updated_at"])
                return error_response(exc)
            apply_assumption_result(session, analysis)
            return Response(PromptSessionSerializer(session).data)
        try:
            next_question = GeminiClient().next_question(
                session.raw_input,
                session.target_category,
                specification_data(session),
                history,
            )
        except LLMError as exc:
            session.status = PromptSession.Status.ERROR
            session.processing_started_at = None
            session.save(update_fields=["status", "processing_started_at", "updated_at"])
            return error_response(exc)
        session.current_question = next_question.question
        session.processing_started_at = None
        session.save(update_fields=["question_count", "current_question", "processing_started_at", "updated_at"])
        return Response(PromptSessionSerializer(session).data)


class AssumptionsView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "gemini"

    def post(self, request, session_id):
        with transaction.atomic():
            session = get_session(session_id, lock=True)
            denied = require_session_access(request, session)
            if denied:
                return denied
            if session.status != PromptSession.Status.AWAITING_ANSWERS:
                return Response(
                    {"error": {"message": "This session is not collecting clarification answers."}},
                    status=409,
                )
            if session.processing_started_at and session.processing_started_at > timezone.now() - timedelta(minutes=10):
                return Response({"error": {"message": "Another clarification request is already being processed."}}, status=409)
            session.assumptions_requested = True
            session.status = PromptSession.Status.GENERATING_ASSUMPTIONS
            session.processing_started_at = timezone.now()
            session.save(update_fields=["assumptions_requested", "status", "processing_started_at", "updated_at"])
        try:
            analysis = GeminiClient().generate_assumptions(
                session.raw_input,
                session.target_category,
                specification_data(session),
                history_data(session),
            )
        except LLMError as exc:
            session.status = PromptSession.Status.ERROR
            session.processing_started_at = None
            session.save(update_fields=["status", "processing_started_at", "updated_at"])
            return error_response(exc)
        apply_assumption_result(session, analysis)
        return Response(PromptSessionSerializer(session).data)


class CustomRequirementsView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "gemini"

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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "gemini"

    def post(self, request, session_id):
        session = get_session(session_id)
        denied = require_session_access(request, session)
        if denied:
            return denied
        if session.status == PromptSession.Status.COMPLETE and hasattr(session, "generated_prompt"):
            return Response(PromptSessionSerializer(session).data)
        if session.status == PromptSession.Status.GENERATING:
            return Response({"error": {"message": "Generation is already in progress."}}, status=409)
        started = PromptSession.objects.filter(
            id=session.id,
            status__in=[PromptSession.Status.READY_FOR_REVIEW, PromptSession.Status.ERROR],
        ).update(
            status=PromptSession.Status.GENERATING,
            processing_started_at=timezone.now(),
            updated_at=timezone.now(),
        )
        if not started:
            return Response({"error": {"message": "This session is not ready to generate."}}, status=409)
        session.refresh_from_db()
        try:
            content = GeminiClient().generate(
                SpecificationSerializer(session.specification).data,
                session.target_category,
            )
        except LLMError as exc:
            session.status = PromptSession.Status.ERROR
            session.processing_started_at = None
            session.save(update_fields=["status", "processing_started_at", "updated_at"])
            return error_response(exc)
        GeneratedPrompt.objects.update_or_create(session=session, defaults={"content": content})
        session.status = PromptSession.Status.COMPLETE
        session.processing_started_at = None
        session.save(update_fields=["status", "processing_started_at", "updated_at"])
        return Response(PromptSessionSerializer(session).data)
