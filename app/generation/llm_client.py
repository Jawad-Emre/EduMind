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


def generate_response(messages: list[dict], max_tokens: int = 3500) -> str:
    """
    Takes a messages list (from prompt_builder.build_prompt) and returns
    the model's text response. Retries once on transient errors.
    """
    """
    Yields text chunks as they're generated, instead of returning
    the full response at once. Caller is responsible for assembling
    the full text if needed (e.g., for saving to DB after streaming ends).
    """
    client = _get_client()

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.4,
                max_tokens=max_tokens,
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