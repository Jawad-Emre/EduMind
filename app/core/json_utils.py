import json
import re
import logging

logger = logging.getLogger(__name__)


def repair_and_parse_json(raw_text: str, context: str = "JSON") -> dict | list:
    """Parse JSON from LLM output, tolerating common structural mistakes.

    LLMs often emit JSON that's semantically correct but syntactically invalid:
    unescaped control characters in strings, trailing commas, stray quotes. This
    function applies best-effort repairs before parsing, so we extract the user's
    intended data rather than hard-failing on a technicality.

    Args:
        raw_text: The raw text from the LLM (may contain markdown fences, etc.).
        context: A short label (e.g. "Summary", "Quiz") for logging.

    Returns:
        The parsed JSON object (dict or list).

    Raises:
        json.JSONDecodeError: If the text is irreparably malformed.
    """
    # 1. Strip markdown code fences
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    # 2. Try parsing as-is first (fast path for well-formed JSON)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass  # proceed to repairs

    # 3. Remove trailing commas before closing brackets/braces (common LLM mistake)
    #    Match: , followed by optional whitespace, then ] or }
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    # 4. Escape unescaped control characters *inside* string literals.
    #    This is fragile (requires distinguishing string content from structure),
    #    so we use a heuristic: find spans between quotes and escape raw control
    #    characters there. Only handles common cases (newline, tab, carriage return).
    #    A true fix would require a full JSON tokenizer, but that's overkill here.
    def escape_controls_in_strings(text: str) -> str:
        # Split on quotes, preserving the quotes. Odd-indexed segments are inside strings.
        segments = text.split('"')
        for i in range(1, len(segments), 2):  # every other segment is inside a string
            # Escape raw control chars. Don't double-escape already-escaped ones.
            segments[i] = (
                segments[i]
                .replace("\\", "\\\\")   # backslash first (avoid double-escaping)
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t")
                .replace("\b", "\\b")
                .replace("\f", "\\f")
            )
        return '"'.join(segments)

    try:
        cleaned = escape_controls_in_strings(cleaned)
    except Exception:
        # If the heuristic itself crashes (malformed quotes), skip it and try parsing anyway.
        pass

    # 5. Final parse attempt
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Log a snippet of the bad JSON so we can debug the next failure.
        snippet_start = max(0, e.pos - 40)
        snippet_end = min(len(cleaned), e.pos + 40)
        snippet = cleaned[snippet_start:snippet_end]
        logger.error(
            "%s JSON parse failed at pos %d: %s. Snippet: ...%s...",
            context, e.pos, e.msg, snippet
        )
        raise
