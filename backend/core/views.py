from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import SupabaseJWTAuthentication
from sessions.models import PromptSession


@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok"})


class AccountExportView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        if request.user is None or not request.user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=401)
        sessions = PromptSession.objects.filter(user=request.user).select_related(
            "specification", "generated_prompt"
        ).order_by("created_at")
        return Response({
            "account": {"id": str(request.user.id), "email": request.user.email},
            "sessions": [
                {
                    "id": str(session.id),
                    "raw_input": session.raw_input,
                    "target_category": session.target_category,
                    "status": session.status,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                    "specification": (
                        {
                            "goal": session.specification.goal,
                            "requirements": session.specification.requirements,
                            "preferences": session.specification.preferences,
                            "constraints": session.specification.constraints,
                            "assumptions": session.specification.assumptions,
                            "assumption_provenance": session.specification.assumption_provenance,
                            "unknowns": session.specification.unknowns,
                            "answers": session.specification.answers,
                            "custom_requirements": session.specification.custom_requirements,
                        }
                        if hasattr(session, "specification") else None
                    ),
                    "generated_prompt": (
                        {
                            "content": session.generated_prompt.content,
                            "created_at": session.generated_prompt.created_at,
                        }
                        if hasattr(session, "generated_prompt") else None
                    ),
                }
                for session in sessions
            ],
        })


class AccountDataDeleteView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]

    def delete(self, request):
        if request.user is None or not request.user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=401)
        with transaction.atomic():
            deleted_count, _ = PromptSession.objects.filter(user=request.user).delete()
            request.user.delete()
        return Response({"deleted_count": deleted_count})
