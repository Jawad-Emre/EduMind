import json

from app.quiz.quiz_generator import generate_quiz_questions


def _make_question(index: int) -> dict:
    return {
        "question": f"Question {index}?",
        "options": [
            {"text": "A", "is_correct": True, "explanation": "Correct"},
            {"text": "B", "is_correct": False, "explanation": "Wrong"},
            {"text": "C", "is_correct": False, "explanation": "Wrong"},
            {"text": "D", "is_correct": False, "explanation": "Wrong"},
        ],
    }


def _build_payload(count: int) -> str:
    questions = [_make_question(i) for i in range(1, count + 1)]
    return json.dumps({"questions": questions})


def test_generate_quiz_questions_caps_requested_count_at_ten(monkeypatch):
    calls = []

    def fake_generate_response(messages, max_tokens, json_mode=False):
        calls.append((max_tokens, json_mode))
        return _build_payload(10)

    monkeypatch.setattr("app.quiz.quiz_generator.generate_response", fake_generate_response)

    questions = generate_quiz_questions("some study material", 20)

    assert len(questions) == 10
    assert len(calls) == 1
