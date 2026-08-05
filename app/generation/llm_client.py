from groq import Groq

from app.core.config import settings
from app.core.exceptions import ExtractionError

MODEL_NAME = "llama-3.3-70b-versatile"
MAX_RETRIES = 2

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def generate_response(
    messages: list[dict],
    max_tokens: int = 3500,
    json_mode: bool = False,
) -> str:
    """
    Takes a messages list (from prompt_builder.build_prompt) and returns
    the model's text response. Retries once on transient errors.

    When json_mode=True, asks Groq to constrain the output to valid JSON
    (response_format json_object). This prevents the malformed-JSON failures
    (unescaped control chars, missing delimiters) that break summary/quiz
    parsing. The prompt must mention "JSON" for this mode to work, and the
    top-level value must be a JSON object (not a bare array).
    """
    client = _get_client()

    kwargs = {
        "model": MODEL_NAME,
        "temperature": 0.4,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            completion = client.chat.completions.create(
                messages=messages,
                **kwargs,
            )

            content = completion.choices[0].message.content
            if not content or not content.strip():
                raise ExtractionError("LLM returned an empty response")
            return content.strip()

        except Exception as e:
            last_error = e
            if attempt == MAX_RETRIES:
                break

    raise ExtractionError(f"Failed to generate response after retries: {last_error}")