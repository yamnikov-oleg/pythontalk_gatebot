from contextlib import contextmanager
from random import randint
from typing import Optional, List
from unittest.mock import NonCallableMagicMock, patch

from telegram import Bot

from gatebot.bot import GateBot
from gatebot.questions import Question


def generate_id() -> int:
    """
    Can be used to randomly generate user ids, message ids, etc.
    """
    return randint(100, 1000)


class UserSession:
    def __init__(
                self,
                gatebot: GateBot,
                first_name: str = 'TestUser',
                force_questions: Optional[List[Question]] = None,
            ):
        self.gatebot = gatebot
        self.user_id = generate_id()
        self.first_name = first_name
        self.force_questions = force_questions

        self.last_bot_mock = None
        self.last_play_data = {}
        self._reset_stage()

    def _reset_stage(self) -> NonCallableMagicMock:
        self.last_bot_mock = NonCallableMagicMock(spec=Bot)
        self.last_play_data = {}

    @contextmanager
    def _gatebot_env(self):
        if self.force_questions:
            with patch('random.sample', return_value=self.force_questions):
                yield
        else:
            yield

    #
    # Play methods
    #

    def play_joins_group(self):
        self._reset_stage()

        update = NonCallableMagicMock()
        update.message.chat.id = self.gatebot.config.GROUP_ID
        update.message.new_chat_members = [
            NonCallableMagicMock(id=self.user_id),
        ]

        with self._gatebot_env():
            self.gatebot.new_chat_members(self.last_bot_mock, update)

    def play_sends_command(self, command: str) -> int:
        self._reset_stage()

        update = NonCallableMagicMock()
        update.message.chat.id = self.user_id
        update.message.from_user.id = self.user_id
        update.message.from_user.first_name = self.first_name

        method = getattr(self.gatebot, f'command_{command}')
        with self._gatebot_env():
            method(self.last_bot_mock, update)

    def play_sends_command_group(self, command: str):
        self._reset_stage()

        update = NonCallableMagicMock()
        update.message.chat.id = self.gatebot.config.GROUP_ID
        update.message.from_user.id = self.user_id
        update.message.from_user.first_name = self.first_name

        method = getattr(self.gatebot, f'command_{command}')
        with self._gatebot_env():
            method(self.last_bot_mock, update)

    def play_sends_callback_query(self, message_id: int, data: str):
        self._reset_stage()

        self.last_play_data['callback_query_id'] = generate_id()

        update = NonCallableMagicMock()
        update.callback_query.id = self.last_play_data['callback_query_id']
        update.callback_query.data = data
        update.callback_query.from_user.id = self.user_id
        update.callback_query.message.chat.id = self.user_id
        update.callback_query.message.message_id = message_id

        with self._gatebot_env():
            self.gatebot.callback_query(self.last_bot_mock, update)

        calls = self.last_bot_mock.answer_callback_query.call_args_list
        assert len(calls) == 1, \
            "Callback query wasn't answered"

        args, kwargs = calls[0]
        id = self.last_play_data['callback_query_id']
        assert kwargs['callback_query_id'] == id, \
            "Callback query wasn't answered"

    #
    # Assert methods
    #

    def assert_no_api_calls(self):
        assert len(self.last_bot_mock.method_calls) == 0

    def assert_was_restricted(self):
        self.last_bot_mock.restrict_chat_member.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            user_id=self.user_id,
            can_send_message=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )

    def assert_sent_getting_started(self):
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        qs = self.gatebot.config.QUESTIONS_PER_QUIZ
        ans = self.gatebot.config.CORRECT_ANSWERS_REQUIRED
        welcome_text = (
            f"Hello {self.first_name}!\n"
            f"You're going to be presented with {qs} randomly picked "
            "questions about Python. To pass the test and be able to chat "
            f"you'll have to answer correctly {ans} of them.\n"
            "When you're ready, press 'Start the quiz'.\n"
            "Good luck!")

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.user_id
        assert welcome_text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"

        button_rows = kwargs['reply_markup'].inline_keyboard
        assert len(button_rows) == 1
        buttons = button_rows[0]
        assert len(buttons) == 1
        button = buttons[0]
        assert button.text == "Start the quiz"
        assert button.callback_data == "start_quiz"

    def assert_sent_already_started(self):
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        text = "You have already started the quiz."

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.user_id
        assert text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"
        assert 'reply_markup' not in kwargs

    def assert_question_displayed(
                self,
                message_id: int,
                question: Question,
                pos: int,
            ):
        calls = self.last_bot_mock.edit_message_text.call_args_list
        assert len(calls) == 1

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.user_id
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
        total = self.gatebot.config.QUESTIONS_PER_QUIZ
        assert pos_button.text == f"{pos}/{total}"
        assert pos_button.callback_data == "ignore"

        next_button = nav_buttons[2]
        assert next_button.text == ">"
        assert next_button.callback_data == "next"
