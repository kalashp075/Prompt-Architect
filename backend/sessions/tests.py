import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import User
from llm.schemas import AnalysisSpec, ClarificationQuestion

from .models import PromptSession, Specification
from .views import QUESTION_LIMITS, SessionCollectionView
from .serializers import CreateSessionSerializer


class AdaptiveClarificationTests(TestCase):
    def test_session_creation_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/sessions/",
            {"raw_input": "Build a web app for a small team.", "target_category": "frontend"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_raw_input_has_a_bounded_length(self):
        serializer = CreateSessionSerializer(data={
            "raw_input": "x" * 4001,
            "target_category": "general",
        })
        self.assertFalse(serializer.is_valid())

    def test_fullstack_uses_ten_question_cap(self):
        self.assertEqual(QUESTION_LIMITS[PromptSession.TargetCategory.FULLSTACK], 10)

    def test_history_reads_do_not_use_gemini_throttle(self):
        view = SessionCollectionView()
        request = APIRequestFactory().get("/api/sessions/")
        view.setup(request)

        self.assertEqual(view.get_throttles(), [])

    def test_history_excludes_error_sessions(self):
        PromptSession.objects.create(
            raw_input="This failed prompt should not appear in history.",
            target_category=PromptSession.TargetCategory.GENERAL,
            status=PromptSession.Status.ERROR,
            user=self.user,
        )
        PromptSession.objects.create(
            raw_input="This unfinished prompt should not appear in history.",
            target_category=PromptSession.TargetCategory.GENERAL,
            status=PromptSession.Status.AWAITING_ANSWERS,
            user=self.user,
        )

        response = self.client.get("/api/sessions/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(item["status"] == PromptSession.Status.COMPLETE for item in response.data))

    def test_delete_session_removes_only_owned_session(self):
        response = self.client.delete(f"/api/sessions/{self.session.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(PromptSession.objects.filter(id=self.session.id).exists())
        self.assertFalse(Specification.objects.filter(session_id=self.session.id).exists())

    def test_delete_all_sessions_removes_only_current_users_sessions(self):
        other_user = User.objects.create(id=uuid.uuid4(), email="other@example.com")
        other_session = PromptSession.objects.create(
            raw_input="Keep this other user's prompt.",
            target_category=PromptSession.TargetCategory.GENERAL,
            status=PromptSession.Status.COMPLETE,
            user=other_user,
        )

        response = self.client.delete("/api/sessions/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["deleted_count"], 1)
        self.assertFalse(PromptSession.objects.filter(id=self.session.id).exists())
        self.assertTrue(PromptSession.objects.filter(id=other_session.id).exists())

    def test_delete_session_denies_other_users(self):
        other_user = User.objects.create(id=uuid.uuid4(), email="other@example.com")
        self.session.user = other_user
        self.session.save(update_fields=["user"])

        response = self.client.delete(f"/api/sessions/{self.session.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PromptSession.objects.filter(id=self.session.id).exists())

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(id=uuid.uuid4(), email="tester@example.com")
        self.client.force_authenticate(user=self.user)
        self.session = PromptSession.objects.create(
            raw_input="Build a web app for a small team.",
            target_category=PromptSession.TargetCategory.FRONTEND,
            status=PromptSession.Status.AWAITING_ANSWERS,
            question_limit=10,
            question_count=0,
            current_question="Who will use this application?",
            user=self.user,
        )
        self.specification = Specification.objects.create(
            session=self.session,
            goal="Build a web app.",
            requirements=["It must be responsive."],
            constraints=["Payment integration is deferred until later."],
            assumptions=[],
            unknowns=[],
        )

    @patch("sessions.views.GeminiClient")
    def test_answer_is_persisted_as_confirmed_and_next_question_is_generated(self, client_class):
        client_class.return_value.next_question.return_value = ClarificationQuestion(
            question="Which frontend framework should the team use?"
        )

        response = self.client.post(
            f"/api/sessions/{self.session.id}/question-answer/",
            {"answer": "Small business owners"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.question_count, 1)
        self.assertEqual(self.session.current_question, "Which frontend framework should the team use?")
        self.assertEqual(
            self.session.specification.answers[0]["provenance"],
            "confirmed",
        )
        self.assertEqual(self.session.specification.answers[0]["answer"], "Small business owners")

    @patch("sessions.views.GeminiClient")
    def test_skipped_answer_is_unresolved_and_does_not_become_confirmed(self, client_class):
        client_class.return_value.next_question.return_value = ClarificationQuestion(
            question="What is the visual style?"
        )

        response = self.client.post(
            f"/api/sessions/{self.session.id}/question-answer/",
            {"skipped": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        answer = response.data["specification"]["answers"][0]
        self.assertTrue(answer["skipped"])
        self.assertEqual(answer["provenance"], "skipped")
        self.assertEqual(answer["answer"], "")

    @patch("sessions.views.GeminiClient")
    def test_make_assumptions_uses_history_and_preserves_answers(self, client_class):
        self.specification.answers = [{
            "question": "Who will use this application?",
            "answer": "Small business owners",
            "skipped": False,
            "provenance": "confirmed",
        }]
        self.specification.save(update_fields=["answers"])
        client_class.return_value.generate_assumptions.return_value = AnalysisSpec(
            goal="Build a web app.",
            requirements=["It must be responsive.", "Serve small business owners."],
            preferences=[],
            constraints=["Payment integration is deferred until later."],
            assumptions=["Use a simple component structure."],
            unknowns=[],
        )

        response = self.client.post(
            f"/api/sessions/{self.session.id}/assumptions/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, PromptSession.Status.AWAITING_CUSTOM_REQS)
        self.assertEqual(
            self.session.specification.answers[0]["answer"],
            "Small business owners",
        )
        client_class.return_value.generate_assumptions.assert_called_once()
