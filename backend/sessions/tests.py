from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from llm.schemas import AnalysisSpec, ClarificationQuestion

from .models import PromptSession, Specification
from .views import QUESTION_LIMITS


class AdaptiveClarificationTests(TestCase):
    def test_fullstack_uses_ten_question_cap(self):
        self.assertEqual(QUESTION_LIMITS[PromptSession.TargetCategory.FULLSTACK], 10)

    def setUp(self):
        self.client = APIClient()
        self.session = PromptSession.objects.create(
            raw_input="Build a web app for a small team.",
            target_category=PromptSession.TargetCategory.FRONTEND,
            status=PromptSession.Status.AWAITING_ANSWERS,
            question_limit=10,
            question_count=0,
            current_question="Who will use this application?",
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
