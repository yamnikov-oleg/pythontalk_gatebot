import json
from typing import List


class Question:
    """
    A single question of the quiz.
    """
    def __init__(self, text: str, options: List[str], answer: int):
        self.text = text
        self.options = options
        self.answer = answer

    def validate(self):
        if self.answer < 0 or self.answer >= len(self.options):
            raise ValueError(f"answer is out of range")


def load_questions(path: str) -> List[Question]:
    """
    Parses the questions file, validates it and returns the list of questions.
    """
    with open(path) as f:
        question_dicts = json.load(f)

    questions = []
    for i, d in enumerate(question_dicts):
        q = Question(
            text=d['question'],
            options=d['options'],
            answer=d['answer'],
        )

        try:
            q.validate()
        except Exception:
            raise ValueError(
                f"Error while parsing question {i + 1}: {q.text!r}")

        questions.append(q)

    return questions
