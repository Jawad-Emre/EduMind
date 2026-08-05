import json

from app.generation.llm_client import generate_response
from app.core.exceptions import ExtractionError
from app.core.json_utils import repair_and_parse_json

QUIZ_GENERATION_PROMPT = (
    "Based on the following study material, generate {num_questions} multiple-choice "
    "quiz questions to test understanding. For EACH option, include a short one-sentence "
    "explanation of why it's correct or incorrect. Return ONLY valid JSON, no other text, "
    "in this exact format (note the top-level object wrapper with a 'questions' key — this "
    "is required for the JSON parser):\n"
    '{{"questions": [\n'
    '  {{"question": "...", "options": [\n'
    '    {{"text": "A", "is_correct": true, "explanation": "..."}},\n'
    '    {{"text": "B", "is_correct": false, "explanation": "..."}},\n'
    '    {{"text": "C", "is_correct": false, "explanation": "..."}},\n'
    '    {{"text": "D", "is_correct": false, "explanation": "..."}}\n'
    "  ]}}\n"
    "]}}\n\n"
    "MATERIAL:\n{material_text}"
)



def generate_quiz_questions(material_text: str, num_questions: int = 5) -> list[dict]:
    """
    Takes combined chunk text from a StudyMaterial and generates quiz questions.
    Returns a list of {"question", "options", "correct_answer"} dicts.
    """
    prompt = [
        {"role": "system", "content": "You are a quiz generator. Output only valid JSON."},
        {
            "role": "user",
            "content": QUIZ_GENERATION_PROMPT.format(
                num_questions=num_questions, material_text=material_text[:4000]
            ),
        },
    ]

    # json_mode=True constrains Groq to emit syntactically valid JSON (prevents the
    # malformed-JSON failures that broke quiz parsing before). The prompt was changed
    # to wrap the array in an object ({"questions": [...]}) because json_mode requires
    # a top-level object, not a bare array.
    raw_response = generate_response(prompt, max_tokens=2500, json_mode=True)

    try:
        data = repair_and_parse_json(raw_response, context="Quiz")
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Quiz generation returned invalid JSON: {e}")

    # Unwrap the object wrapper to get the questions array.
    if isinstance(data, dict) and "questions" in data:
        questions = data["questions"]
    elif isinstance(data, list):
        # Fallback: if the model ignored the wrapper instruction and returned a bare array anyway.
        questions = data
    else:
        raise ExtractionError("Quiz generation returned unexpected JSON structure")

    if not isinstance(questions, list) or not questions:
        raise ExtractionError("Quiz generation returned no usable questions")

    for q in questions:
        if "question" not in q or "options" not in q:
            raise ExtractionError("Quiz generation returned malformed question structure")
        if not isinstance(q["options"], list) or len(q["options"]) < 2:
            raise ExtractionError("Quiz question has insufficient options")
        for opt in q["options"]:
            if not all(k in opt for k in ("text", "is_correct", "explanation")):
                raise ExtractionError("Quiz option missing required fields")

    return questions


def score_quiz_attempt(questions: list[dict], answers: list[str]) -> float:
    if len(answers) != len(questions):
        raise ExtractionError("Number of answers does not match number of questions")

    correct = 0
    for q, submitted_text in zip(questions, answers):
        correct_option = next((o for o in q["options"] if o["is_correct"]), None)
        if correct_option and submitted_text.strip().lower() == correct_option["text"].strip().lower():
            correct += 1

    return round(correct / len(questions), 3)