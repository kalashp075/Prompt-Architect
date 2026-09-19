import json
import os
import time
import logging

from google import genai
from google.genai import types
from pydantic import ValidationError

from .exceptions import LLMError, LLMRateLimitError
from .schemas import (
    AnalysisSpec, ClarificationQuestion, CustomRequirementMerge,
    UpdatedAnalysisSpec,
)
from .templates import (
    ANALYSIS_TEMPLATE,
    ASSUMPTIONS_TEMPLATE,
    CATEGORY_FOCUS,
    GENERATION_TEMPLATE,
    MERGE_TEMPLATE,
    QUESTION_TEMPLATE,
    STRICT_ANALYSIS_SUFFIX,
)


class GeminiClient:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        model = os.environ.get("GEMINI_MODEL")
        if not api_key or not model:
            raise LLMError("Gemini is not configured. Set GEMINI_API_KEY and GEMINI_MODEL.")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.max_output_tokens = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "4096"))
        self.max_input_chars = int(os.environ.get("GEMINI_MAX_INPUT_CHARS", "24000"))
        self.max_attempts = min(int(os.environ.get("GEMINI_MAX_ATTEMPTS", "3")), 3)
        self.logger = logging.getLogger("llm.gemini")

    def _generate(self, prompt, *, schema=None):
        if len(prompt) > self.max_input_chars:
            raise LLMError("This request is too large to process. Please shorten it and try again.")
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=self.max_output_tokens,
            response_mime_type="application/json" if schema else "text/plain",
            response_schema=schema.model_json_schema() if schema else None,
        )
        for attempt in range(self.max_attempts):
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
                text = response.text or ""
                if len(text) > self.max_output_tokens * 8:
                    raise LLMError("Gemini returned an unexpectedly large response.")
                usage = getattr(response, "usage_metadata", None)
                self.logger.info(
                    "gemini_request_complete",
                    extra={
                        "model": self.model,
                        "attempt": attempt + 1,
                        "input_tokens": getattr(usage, "prompt_token_count", None),
                        "output_tokens": getattr(usage, "candidates_token_count", None),
                    },
                )
                return text
            except Exception as exc:
                if attempt < self.max_attempts - 1 and self._is_transient(exc):
                    time.sleep(0.25 * (2 ** attempt))
                    continue
                return self._raise_llm_error(exc)

    @staticmethod
    def _is_transient(exc):
        message = str(exc).lower()
        return any(token in message for token in ("429", "quota", "rate", "503", "unavailable", "timeout", "temporarily"))

    @staticmethod
    def _raise_llm_error(exc):
            message = str(exc).lower()
            if "429" in message or "quota" in message or "rate" in message:
                raise LLMRateLimitError(
                    "Gemini is temporarily rate-limited. Please wait and try again."
                ) from exc
            if "503" in message or "unavailable" in message:
                raise LLMError(
                    "Gemini is temporarily unavailable because the selected model is busy. "
                    "Please try again or choose another available GEMINI_MODEL."
                ) from exc
            if "404" in message or "not_found" in message:
                raise LLMError(
                    "The configured GEMINI_MODEL is unavailable. Set GEMINI_MODEL to an "
                    "available model in Google AI Studio and restart Django."
                ) from exc
            raise LLMError("Gemini could not complete this request. Please try again.") from exc

    def analyze(self, raw_input, target_category):
        prompt = ANALYSIS_TEMPLATE.format(
            raw_input=raw_input, target_category=target_category
        )
        for attempt in range(2):
            try:
                text = self._generate(
                    prompt + (STRICT_ANALYSIS_SUFFIX if attempt else ""),
                    schema=AnalysisSpec,
                )
                return AnalysisSpec.model_validate(json.loads(text))
            except (json.JSONDecodeError, ValidationError, TypeError) as exc:
                if attempt == 1:
                    raise LLMError(
                        "Something went wrong generating your specification — try rephrasing or try again."
                    ) from exc

    def merge_custom_requirements(self, spec, custom_requirements):
        prompt = MERGE_TEMPLATE.format(
            spec=json.dumps(spec, ensure_ascii=False),
            custom_requirements=custom_requirements,
        )
        try:
            return CustomRequirementMerge.model_validate(
                json.loads(self._generate(prompt, schema=CustomRequirementMerge))
            )
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise LLMError(
                "Something went wrong adding your custom requirements — please try again."
            ) from exc

    def next_question(self, raw_input, target_category, spec, history):
        prompt = QUESTION_TEMPLATE.format(
            raw_input=raw_input,
            target_category=target_category,
            spec=json.dumps(spec, ensure_ascii=False),
            history=json.dumps(history, ensure_ascii=False),
        )
        try:
            return ClarificationQuestion.model_validate(
                json.loads(self._generate(prompt, schema=ClarificationQuestion))
            )
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise LLMError(
                "Something went wrong generating the next clarification question — please try again."
            ) from exc

    def generate_assumptions(self, raw_input, target_category, spec, history):
        prompt = ASSUMPTIONS_TEMPLATE.format(
            raw_input=raw_input,
            target_category=target_category,
            spec=json.dumps(spec, ensure_ascii=False),
            history=json.dumps(history, ensure_ascii=False),
        )
        try:
            return UpdatedAnalysisSpec.model_validate(
                json.loads(self._generate(prompt, schema=UpdatedAnalysisSpec))
            )
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise LLMError(
                "Something went wrong filling in the remaining assumptions — please try again."
            ) from exc

    def generate(self, spec, target_category):
        prompt = GENERATION_TEMPLATE.format(
            target_category=target_category,
            category_focus=CATEGORY_FOCUS[target_category],
            spec=json.dumps(spec, ensure_ascii=False),
        )
        return self._generate(prompt)
