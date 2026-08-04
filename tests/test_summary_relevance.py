"""Tests for the relevancy-gated profile update in session summaries.

Covers the pure logic changed for the profile_relevant feature:
  - _parse_summary_json: parsing/normalising the new profile_relevant flag
  - merge_knowledge_state: what actually lands in the profile

Run: python -m pytest tests/test_summary_relevance.py -v
"""
import json

from app.memory.session_store import _parse_summary_json, merge_knowledge_state


def _base_payload(**overrides) -> str:
    data = {
        "profile_relevant": True,
        "summary_text": "## Topic\nPhotosynthesis basics.",
        "topics_covered": ["Photosynthesis"],
        "understood_well": ["Light reactions"],
        "struggled_with": ["Calvin cycle"],
        "review_suggestions": ["Review the Calvin cycle"],
    }
    data.update(overrides)
    return json.dumps(data)


# --- _parse_summary_json: profile_relevant parsing -------------------------

def test_relevant_true_bool():
    out = _parse_summary_json(_base_payload(profile_relevant=True))
    assert out["profile_relevant"] is True


def test_relevant_false_bool():
    out = _parse_summary_json(_base_payload(profile_relevant=False))
    assert out["profile_relevant"] is False


def test_relevant_true_string():
    # Model sometimes returns "true" as a string.
    out = _parse_summary_json(_base_payload(profile_relevant="true"))
    assert out["profile_relevant"] is True


def test_relevant_string_case_insensitive():
    out = _parse_summary_json(_base_payload(profile_relevant="TRUE"))
    assert out["profile_relevant"] is True


def test_relevant_missing_defaults_false():
    # Conservative default: no flag => do not touch the profile.
    payload = json.dumps({"summary_text": "notes", "topics_covered": []})
    out = _parse_summary_json(payload)
    assert out["profile_relevant"] is False


def test_relevant_garbage_defaults_false():
    out = _parse_summary_json(_base_payload(profile_relevant="maybe"))
    assert out["profile_relevant"] is False


def test_parse_survives_code_fences():
    fenced = "```json\n" + _base_payload() + "\n```"
    out = _parse_summary_json(fenced)
    assert out["profile_relevant"] is True
    assert out["understood_well"] == ["Light reactions"]


# --- merge_knowledge_state: the downstream effect of the gate --------------

def test_merge_adds_relevant_concepts():
    summary = _parse_summary_json(_base_payload())
    state = merge_knowledge_state(None, summary)
    assert "Light reactions" in state["strengths"]
    assert "Calvin cycle" in state["struggles"]
    assert "Photosynthesis" in state["notes"]


def test_irrelevant_session_returns_empty_lists():
    # When the model flags a chat irrelevant it returns empty concept lists,
    # so merging into a fresh profile leaves strengths/struggles empty.
    irrelevant = _parse_summary_json(_base_payload(
        profile_relevant=False,
        understood_well=[],
        struggled_with=[],
        topics_covered=[],
    ))
    state = merge_knowledge_state(None, irrelevant)
    assert state["strengths"] == []
    assert state["struggles"] == []


def test_merge_does_not_lose_existing_profile():
    # Even if an irrelevant summary is (wrongly) merged, existing data survives.
    existing = {"strengths": ["Algebra"], "struggles": ["Fractions"], "notes": "prev"}
    irrelevant = _parse_summary_json(_base_payload(
        profile_relevant=False, understood_well=[], struggled_with=[], topics_covered=[],
    ))
    state = merge_knowledge_state(existing, irrelevant)
    assert "Algebra" in state["strengths"]
    assert "Fractions" in state["struggles"]
