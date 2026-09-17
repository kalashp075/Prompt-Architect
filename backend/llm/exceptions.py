class LLMError(Exception):
    """A user-safe failure from the LLM integration."""


class LLMRateLimitError(LLMError):
    """Gemini quota or rate-limit failure."""
