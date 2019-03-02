from typing import Optional, List
from unittest.mock import NonCallableMagicMock, patch

from telegram import Bot
from pytest import fixture

from config import TestConfig
from gatebot.bot import GateBot
from gatebot.models import Base
from gatebot.questions import Question


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
        bot = self.play_user_joins_group(gatebot, user_id=111)
        self.assert_user_restricted(gatebot, bot, user_id=111)

    def test_user_sends_start(self, gatebot: GateBot):
        bot = self.play_user_sends_command(
            gatebot, "start", user_id=111, first_name="TestUser8")
        self.assert_getting_started_sent(
            gatebot, bot, user_id=111, first_name="TestUser8")

    def test_user_sends_start_in_group(self, gatebot: GateBot):
        bot = self.play_user_sends_command_in_group(
            gatebot, "start", user_id=111, first_name="TestUser8")
        self.assert_no_api_calls(bot)

    def test_user_starts_quiz(self, gatebot: GateBot):
        bot = self.play_user_sends_callback_query(
            gatebot,
            id=124,
            data="start_quiz",
            user_id=11,
            message_id=125,
            generate_questions=[
                QUESTION_1,
                QUESTION_2,
                QUESTION_3,
            ]
        )
        self.assert_callback_query_answered(bot, 124)
        self.assert_question_displayed(
            gatebot,
            bot,
            message_id=125,
            user_id=11,
            question=QUESTION_1,
            pos=1,
        )

    def test_user_starts_quiz_twice(self, gatebot: GateBot):
        bot = self.play_user_sends_callback_query(
            gatebot,
            id=124,
            data="start_quiz",
            user_id=11,
            message_id=125,
            generate_questions=[
                QUESTION_1,
                QUESTION_2,
                QUESTION_3,
            ]
        )
        self.assert_callback_query_answered(bot, 124)
        self.assert_question_displayed(
            gatebot,
            bot,
            message_id=125,
            user_id=11,
            question=QUESTION_1,
            pos=1,
        )

        bot = self.play_user_sends_callback_query(
            gatebot,
            id=124,
            data="start_quiz",
            user_id=11,
            message_id=126,
            generate_questions=[
                QUESTION_3,
                QUESTION_2,
                QUESTION_1,
            ]
        )
        self.assert_callback_query_answered(bot, 124)
        self.assert_already_started_sent(bot, 11)

        bot = self.play_user_sends_command(
            gatebot,
            "start",
            user_id=11,
        )
        self.assert_already_started_sent(bot, 11)

    def test_navigation(self, gatebot: GateBot):
        bot = self.play_user_sends_callback_query(
            gatebot,
            id=124,
            data="start_quiz",
            user_id=11,
            message_id=125,
            generate_questions=[
                QUESTION_1,
                QUESTION_2,
                QUESTION_3,
            ]
        )
        self.assert_callback_query_answered(bot, 124)
        self.assert_question_displayed(
            gatebot,
            bot,
            message_id=125,
            user_id=11,
            question=QUESTION_1,
            pos=1,
        )

        bot = self.play_user_sends_callback_query(
            gatebot,
            id=125,
            data="next",
            user_id=11,
            message_id=125,
        )
        self.assert_callback_query_answered(bot, 125)
        self.assert_question_displayed(
            gatebot,
            bot,
            message_id=125,
            user_id=11,
            question=QUESTION_2,
            pos=2,
        )

        bot = self.play_user_sends_callback_query(
            gatebot,
            id=125,
            data="next",
            user_id=11,
            message_id=125,
        )
        self.assert_callback_query_answered(bot, 125)
        self.assert_question_displayed(
            gatebot,
            bot,
            message_id=125,
            user_id=11,
            question=QUESTION_3,
            pos=3,
        )

        bot = self.play_user_sends_callback_query(
            gatebot,
            id=125,
            data="next",
            user_id=11,
            message_id=125,
        )
        self.assert_callback_query_answered(bot, 125)
        self.assert_question_displayed(
            gatebot,
            bot,
            message_id=125,
            user_id=11,
            question=QUESTION_1,
            pos=1,
        )

        bot = self.play_user_sends_callback_query(
            gatebot,
            id=125,
            data="prev",
            user_id=11,
            message_id=125,
        )
        self.assert_callback_query_answered(bot, 125)
        self.assert_question_displayed(
            gatebot,
            bot,
            message_id=125,
            user_id=11,
            question=QUESTION_3,
            pos=3,
        )

        bot = self.play_user_sends_callback_query(
            gatebot,
            id=125,
            data="prev",
            user_id=11,
            message_id=125,
        )
        self.assert_callback_query_answered(bot, 125)
        self.assert_question_displayed(
            gatebot,
            bot,
            message_id=125,
            user_id=11,
            question=QUESTION_2,
            pos=2,
        )

    # Play methods

    def play_user_joins_group(
                self,
                gatebot: GateBot,
                user_id: int,
            ) -> NonCallableMagicMock:
        bot = NonCallableMagicMock(spec=Bot)

        update = NonCallableMagicMock()
        update.message.chat.id = gatebot.config.GROUP_ID
        update.message.new_chat_members = [NonCallableMagicMock(id=user_id)]

        gatebot.new_chat_members(bot, update)

        return bot

    def play_user_sends_command(
                self,
                gatebot: GateBot,
                command: str,
                user_id: int,
                first_name: str = None,
            ) -> NonCallableMagicMock:
        bot = NonCallableMagicMock(spec=Bot)

        update = NonCallableMagicMock()
        update.message.chat.id = user_id
        update.message.from_user.id = user_id
        update.message.from_user.first_name = first_name

        method = getattr(gatebot, f'command_{command}')
        method(bot, update)

        return bot

    def play_user_sends_command_in_group(
                self,
                gatebot: GateBot,
                command: str,
                user_id: int,
                first_name: str,
            ) -> NonCallableMagicMock:
        bot = NonCallableMagicMock(spec=Bot)

        update = NonCallableMagicMock()
        update.message.chat.id = gatebot.config.GROUP_ID
        update.message.from_user.id = user_id
        update.message.from_user.first_name = first_name

        method = getattr(gatebot, f'command_{command}')
        method(bot, update)

        return bot

    def play_user_sends_callback_query(
                self,
                gatebot: GateBot,
                id: int,
                data: str,
                user_id: int,
                message_id: int,
                generate_questions: Optional[List[Question]] = None,
            ) -> NonCallableMagicMock:
        bot = NonCallableMagicMock(spec=Bot)

        update = NonCallableMagicMock()
        update.callback_query.id = id
        update.callback_query.data = data
        update.callback_query.from_user.id = user_id
        update.callback_query.message.chat.id = user_id
        update.callback_query.message.message_id = message_id

        if generate_questions:
            with patch('random.sample', return_value=generate_questions):
                gatebot.callback_query(bot, update)
        else:
            gatebot.callback_query(bot, update)

        return bot

    # Assert methods

    def assert_no_api_calls(self, bot: NonCallableMagicMock):
        assert len(bot.method_calls) == 0

    def assert_user_restricted(
                self,
                gatebot: GateBot,
                bot: NonCallableMagicMock,
                user_id: int,
            ) -> None:
        bot.restrict_chat_member.assert_called_once_with(
            chat_id=gatebot.config.GROUP_ID,
            user_id=user_id,
            can_send_message=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )

    def assert_getting_started_sent(
                self,
                gatebot: GateBot,
                bot: NonCallableMagicMock,
                user_id: int,
                first_name: str,
            ) -> None:
        calls = bot.send_message.call_args_list
        assert len(calls) == 1

        qs = gatebot.config.QUESTIONS_PER_QUIZ
        ans = gatebot.config.CORRECT_ANSWERS_REQUIRED
        welcome_text = (
            f"Hello {first_name}!\n"
            f"You're going to be presented with {qs} randomly picked "
            "questions about Python. To pass the test and be able to chat "
            f"you'll have to answer correctly {ans} of them.\n"
            "When you're ready, press 'Start the quiz'.\n"
            "Good luck!")

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == user_id
        assert welcome_text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"

        button_rows = kwargs['reply_markup'].inline_keyboard
        assert len(button_rows) == 1
        buttons = button_rows[0]
        assert len(buttons) == 1
        button = buttons[0]
        assert button.text == "Start the quiz"
        assert button.callback_data == "start_quiz"

    def assert_already_started_sent(
                self,
                bot: NonCallableMagicMock,
                user_id: int,
            ):
        calls = bot.send_message.call_args_list
        assert len(calls) == 1

        text = "You have already started the quiz."

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == user_id
        assert text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"
        assert 'reply_markup' not in kwargs

    def assert_callback_query_answered(
                self,
                bot: NonCallableMagicMock,
                id: int,
            ) -> None:
        calls = bot.answer_callback_query.call_args_list
        assert len(calls) == 1
        args, kwargs = calls[0]
        assert kwargs['callback_query_id'] == id

    def assert_question_displayed(
                self,
                gatebot: GateBot,
                bot: NonCallableMagicMock,
                message_id: int,
                user_id: int,
                question: Question,
                pos: int,
            ):
        calls = bot.edit_message_text.call_args_list
        assert len(calls) == 1

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == user_id
        assert kwargs['message_id'] == message_id
        assert question.text in kwargs['text']
        for ix, opt in enumerate(question.options):
            assert f"{ix}. {opt}" in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"

        button_rows = kwargs['reply_markup'].inline_keyboard

        nav_buttons = button_rows[0]
        assert len(nav_buttons) == 3

        back_button = nav_buttons[0]
        assert back_button.text == "<"
        assert back_button.callback_data == "prev"

        pos_button = nav_buttons[1]
        assert pos_button.text == f"{pos}/{gatebot.config.QUESTIONS_PER_QUIZ}"
        assert pos_button.callback_data == "ignore"

        next_button = nav_buttons[2]
        assert next_button.text == ">"
        assert next_button.callback_data == "next"
