from datetime import datetime, timezone
from functools import lru_cache

from transformers import pipeline

from app.db.models import LevelEnum

EMA_WEIGHT = 0.2
SPIKE_THRESHOLD = 0.3
MAX_DELTA_PER_UPDATE = 0.08
QUIZ_CORRECT_DELTA = 0.12
QUIZ_FAILURE_PENALTY = 0.15
DECAY_PER_WEEK_IDLE = 0.02

ZEROSHOT_MODEL_NAME = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"

SIGNAL_LABELS = [
    "correct explanation",
    "incorrect explanation",
    "deep reasoning question",
    "surface-level question",
    "advanced technical vocabulary",
]

# Formula weights — priors for now, not yet calibrated against real quiz outcomes.
CORRECTNESS_WEIGHT = 0.5
DEPTH_WEIGHT = 0.3
VOCABULARY_WEIGHT = 0.2


@lru_cache(maxsize=1)
def _get_classifier():
    """Load the zero-shot model once per process, not per call.

    lru_cache guarantees this runs exactly once — first call loads the
    ~440MB model into memory, every call after reuses the same instance.
    """
    return pipeline("zero-shot-classification", model=ZEROSHOT_MODEL_NAME)


def score_message_signal(content: str) -> float:
    """
    Local zero-shot NLI scorer (0-1): classifies the message against
    correctness, reasoning depth, and vocabulary sophistication labels
    in a single model call. No LLM API, no per-message network cost.

    Combined downstream with spike-verification and capped-delta to
    resist noisy or gamed signals.
    """
    if not content or not content.strip():
        return 0.0

    classifier = _get_classifier()
    result = classifier(content, SIGNAL_LABELS)
    scores = dict(zip(result["labels"], result["scores"]))

    correctness = scores.get("correct explanation", 0.5)
    depth = scores.get("deep reasoning question", 0.5)
    vocabulary = scores.get("advanced technical vocabulary", 0.5)

    return round(
        (CORRECTNESS_WEIGHT * correctness)
        + (DEPTH_WEIGHT * depth)
        + (VOCABULARY_WEIGHT * vocabulary),
        3,
    )


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def update_confidence_from_message(
    current_score: float,
    message_signal_score: float,
    pending_spike: float | None,
) -> tuple[float, float | None]:
    """
    Returns (new_confidence_score, new_pending_spike_value).
    pending_spike tracks an unverified jump awaiting 2-3 consistent follow-ups.
    """
    gap = message_signal_score - current_score

    if abs(gap) > SPIKE_THRESHOLD:
        if pending_spike is not None and abs(message_signal_score - pending_spike) < 0.1:
            # second consistent high signal — trust it now, fall through to normal update
            pass
        else:
            # first anomalous jump — hold, don't update yet
            return current_score, message_signal_score

    raw_new = (EMA_WEIGHT * message_signal_score) + ((1 - EMA_WEIGHT) * current_score)
    capped_delta = _clamp(raw_new - current_score, -MAX_DELTA_PER_UPDATE, MAX_DELTA_PER_UPDATE)
    new_score = _clamp(current_score + capped_delta)
    return new_score, None  # spike resolved either way


def update_confidence_from_quiz(current_score: float, passed: bool) -> float:
    delta = QUIZ_CORRECT_DELTA if passed else -QUIZ_FAILURE_PENALTY
    return _clamp(current_score + delta)


def apply_decay(current_score: float, last_updated: datetime) -> float:
    weeks_idle = (datetime.now(timezone.utc) - last_updated).days / 7
    if weeks_idle < 1:
        return current_score
    return _clamp(current_score - (DECAY_PER_WEEK_IDLE * weeks_idle))


def score_to_level(score: float) -> LevelEnum:
    if score < 0.35:
        return LevelEnum.beginner
    if score < 0.7:
        return LevelEnum.intermediate
    return LevelEnum.advanced