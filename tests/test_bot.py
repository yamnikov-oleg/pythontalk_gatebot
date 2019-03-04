from pytest import fixture

from config import TestConfig
from gatebot.bot import GateBot
from gatebot.models import Base
from gatebot.questions import Question

from .utils import UserSession


QUESTION_1 = Question(
    text="Test question #1",
    options=[
        "Test option 1.1",
        "Test option 1.2",
        "Test option 1.3",
    ],
    answer=0,
)

QUESTION_2 = Question(
    text="Test question #2",
    options=[
        "Test option 2.1",
        "Test option 2.2",
        "Test option 2.3",
        "Test option 2.4",
    ],
    answer=3,
)

QUESTION_3 = Question(
    text="Test question #3",
    options=[
        "Test option 3.1",
        "Test option 3.2",
        "Test option 3.3",
        "Test option 3.4",
        "Test option 3.5",
    ],
    answer=1,
)


@fixture
def gatebot():
    gatebot = GateBot(TestConfig())
    gatebot.config.QUESTIONS_PER_QUIZ = 3
    gatebot.config.CORRECT_ANSWERS_REQUIRED = 2

    Base.metadata.create_all()

    return gatebot


class TestStories:
    def test_user_joins(self, gatebot: GateBot):
        session = UserSession(gatebot)

        session.play_joins_group()
        session.assert_was_restricted()

    def test_user_sends_start(self, gatebot: GateBot):
        session = UserSession(gatebot)

        session.play_sends_command("start")
        session.assert_sent_getting_started()

    def test_user_sends_start_in_group(self, gatebot: GateBot):
        session = UserSession(gatebot)

        session.play_sends_command_group("start")
        session.assert_no_api_calls()

    def test_user_starts_quiz(self, gatebot: GateBot):
        session = UserSession(gatebot, force_questions=[
            QUESTION_1,
            QUESTION_2,
            QUESTION_3,
        ])

        session.play_sends_callback_query(1, "start_quiz")
        session.assert_question_displayed(1, QUESTION_1, pos=1)

    def test_user_starts_quiz_twice(self, gatebot: GateBot):
        session = UserSession(gatebot, force_questions=[
            QUESTION_1,
            QUESTION_2,
            QUESTION_3,
        ])

        session.play_sends_callback_query(1, "start_quiz")
        session.assert_question_displayed(1, QUESTION_1, pos=1)

        session.play_sends_callback_query(2, "start_quiz")
        session.assert_sent_already_started()

        session.play_sends_command("start")
        session.assert_sent_already_started()

    def test_navigation(self, gatebot: GateBot):
        session = UserSession(gatebot, force_questions=[
            QUESTION_1,
            QUESTION_2,
            QUESTION_3,
        ])

        session.play_sends_callback_query(1, "start_quiz")
        session.assert_question_displayed(1, QUESTION_1, pos=1)

        session.play_sends_callback_query(1, "next")
        session.assert_question_displayed(1, QUESTION_2, pos=2)

        session.play_sends_callback_query(1, "next")
        session.assert_question_displayed(1, QUESTION_3, pos=3)

        session.play_sends_callback_query(1, "next")
        session.assert_question_displayed(1, QUESTION_1, pos=1)

        session.play_sends_callback_query(1, "prev")
        session.assert_question_displayed(1, QUESTION_3, pos=3)

        session.play_sends_callback_query(1, "prev")
        session.assert_question_displayed(1, QUESTION_2, pos=2)

    def test_answering_questions(self, gatebot: GateBot):
        session = UserSession(gatebot, force_questions=[
            QUESTION_1,
            QUESTION_2,
            QUESTION_3,
        ])

        session.play_sends_callback_query(1, "start_quiz")
        session.assert_question_displayed(1, QUESTION_1, pos=1)

        session.play_sends_callback_query(1, "answer_0")
        session.assert_question_displayed(
            1, QUESTION_1, pos=1, answered='correct')

        session.play_sends_callback_query(1, "next")
        session.assert_question_displayed(1, QUESTION_2, pos=2)

        session.play_sends_callback_query(1, "answer_2")
        session.assert_question_displayed(
            1, QUESTION_2, pos=2, answered='wrong')

        session.play_sends_callback_query(1, "prev")
        session.assert_question_displayed(
            1, QUESTION_1, pos=1, answered='correct')

    def test_joins_and_passes(self, gatebot: GateBot):
        session = UserSession(gatebot, force_questions=[
            QUESTION_1,
            QUESTION_2,
            QUESTION_3,
        ])

        session.play_joins_group()
        session.play_sends_callback_query(1, "start_quiz")
        session.play_sends_callback_query(1, "answer_0")  # Correct
        session.play_sends_callback_query(1, "next")
        session.play_sends_callback_query(1, "answer_3")  # Correct
        session.play_sends_callback_query(1, "next")
        session.play_sends_callback_query(1, "answer_2")  # Wrong
        session.assert_sent_passed(result=2)
        session.assert_was_unrestricted()

    def test_passes_and_joins(self, gatebot: GateBot):
        session = UserSession(gatebot, force_questions=[
            QUESTION_1,
            QUESTION_2,
            QUESTION_3,
        ])

        session.play_sends_callback_query(1, "start_quiz")
        session.play_sends_callback_query(1, "answer_0")  # Correct
        session.play_sends_callback_query(1, "next")
        session.play_sends_callback_query(1, "answer_3")  # Correct
        session.play_sends_callback_query(1, "next")
        session.play_sends_callback_query(1, "answer_1")  # Correct
        session.assert_sent_passed(result=3)
        session.assert_was_unrestricted()

        session.play_joins_group()
        session.assert_no_restriction_api_calls()

    def test_starts_quiz_and_joins(self, gatebot: GateBot):
        session = UserSession(gatebot, force_questions=[
            QUESTION_1,
            QUESTION_2,
            QUESTION_3,
        ])

        session.play_sends_callback_query(1, "start_quiz")
        session.play_sends_callback_query(1, "answer_0")  # Correct

        session.play_joins_group()
        session.assert_was_restricted()

    def test_fails(self, gatebot: GateBot):
        session = UserSession(gatebot, force_questions=[
            QUESTION_1,
            QUESTION_2,
            QUESTION_3,
        ])

        session.play_sends_callback_query(1, "start_quiz")
        session.play_sends_callback_query(1, "answer_1")  # Wrong
        session.play_sends_callback_query(1, "next")
        session.play_sends_callback_query(1, "answer_2")  # Wrong
        session.play_sends_callback_query(1, "next")
        session.play_sends_callback_query(1, "answer_1")  # Correct
        session.assert_sent_failed(result=1)
        session.assert_no_restriction_api_calls()
