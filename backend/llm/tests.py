import json
from unittest import TestCase

from .client import GeminiClient
from .schemas import AnalysisSpec
from .templates import ANALYSIS_TEMPLATE, ASSUMPTIONS_TEMPLATE, GENERATION_TEMPLATE


class DecisionIntegrityTemplateTests(TestCase):
    def test_analysis_protects_explicit_stack_and_authentication_choices(self):
        self.assertIn("frontend technology, backend technology, database", ANALYSIS_TEMPLATE)
        self.assertIn("authentication provider", ANALYSIS_TEMPLATE)
        self.assertIn("confirmed", ANALYSIS_TEMPLATE)

    def test_analysis_protects_deferred_payment_and_deployment_choices(self):
        self.assertIn("payment integration is not needed right now", ANALYSIS_TEMPLATE)
        self.assertIn("do not choose Stripe", ANALYSIS_TEMPLATE)
        self.assertIn("explicit deferral or exclusion", ANALYSIS_TEMPLATE)

    def test_assumption_prompt_prioritizes_confirmed_and_assumed_answers(self):
        self.assertIn("provenance `confirmed`", ASSUMPTIONS_TEMPLATE)
        self.assertIn("Answers marked `ai_assumption`", ASSUMPTIONS_TEMPLATE)
        self.assertIn("choose a payment provider", ASSUMPTIONS_TEMPLATE)

    def test_generation_prompt_preserves_all_four_decision_categories(self):
        for phrase in (
            "payment provider",
            "deployment model",
            "authentication and stack choices",
            "`ai_assumption` answers are provisional",
        ):
            self.assertIn(phrase, GENERATION_TEMPLATE)


class AssumptionProvenanceParsingTests(TestCase):
    def test_assumption_result_keeps_provenance(self):
        client = object.__new__(GeminiClient)
        client._generate = lambda prompt, schema: json.dumps({
            "goal": "Build a web app.",
            "requirements": ["Responsive UI"],
            "preferences": [],
            "constraints": ["Payment integration is deferred."],
            "assumptions": ["Use a web browser."],
            "assumption_provenance": [
                {"text": "Use a web browser.", "source": "ai_assumption"}
            ],
            "unknowns": [],
        })

        result = client.generate_assumptions(
            "Build a web app.",
            "frontend",
            {"answers": []},
            [],
        )

        self.assertIsInstance(result, AnalysisSpec)
        self.assertEqual(result.assumption_provenance[0].source, "ai_assumption")
