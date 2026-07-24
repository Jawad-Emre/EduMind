import re
from datetime import datetime, timezone

from app.db.models import LevelEnum

EMA_WEIGHT = 0.2
SPIKE_THRESHOLD = 0.3
MAX_DELTA_PER_UPDATE = 0.08
QUIZ_CORRECT_DELTA = 0.12
QUIZ_FAILURE_PENALTY = 0.15
DECAY_PER_WEEK_IDLE = 0.02

ADVANCED_MARKERS = [
    "asymptotic", "gradient", "eigenvalue", "polymorphism", "recursion",
    "complexity", "optimization", "architecture", "trade-off", "implementation",
]


def score_message_signal(content: str) -> float:
    """
    Cheap heuristic scorer (0-1): longer, more technical, well-structured
    messages score higher. Not meant to be precise alone — combined with
    spike-verification and capped-delta to resist gaming.
    """
    words = content.split()
    if not words:
        return 0.0

    length_score = min(len(words) / 60, 1.0)
    marker_hits = sum(1 for w in words if w.lower().strip(".,?!") in ADVANCED_MARKERS)
    marker_score = min(marker_hits / 3, 1.0)
    question_depth = 1.0 if re.search(r"\bwhy\b|\bhow\b.*\brelates?\b", content.lower()) else 0.5

    return round((0.4 * length_score) + (0.4 * marker_score) + (0.2 * question_depth), 3)


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