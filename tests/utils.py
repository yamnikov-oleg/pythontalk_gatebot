import queue
import time
from contextlib import contextmanager
from datetime import timedelta
from random import randint
from typing import Optional, List
from unittest.mock import NonCallableMagicMock, patch

from telegram import Bot

from gatebot import models
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
                force_questions: Optional[List[Question]] = None,
            ):
        self.gatebot = gatebot
        self.user_id = generate_id()
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

        method = getattr(self.gatebot, f'command_{command}')
        with self._gatebot_env():
            method(self.last_bot_mock, update)

    def play_sends_command_group(self, command: str):
        self._reset_stage()

        update = NonCallableMagicMock()
        update.message.chat.id = self.gatebot.config.GROUP_ID
        update.message.from_user.id = self.user_id

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

    def play_time_passed(self, delta: timedelta):
        # This method simulates passage of time by accessing GateBot's and
        # python-telegram-bot internals and changing shift timestamps there
        # by `delta`.

        self._reset_stage()

        # Shift back datetime fields in GateBot's DB
        rewind_fields = {
            models.QuizPass: ['created_at'],
            models.QuizItem: ['answered_at'],
        }
        with self.gatebot.db_session() as session:
            for model, fields in rewind_fields.items():
                for obj in session.query(model):
                    for field in fields:
                        value = getattr(obj, field)
                        if value:
                            value -= delta
                            setattr(obj, field, value)
            session.commit()

        # Look through ptb's job queue to run the jobs which are scheduled
        # to run after `delta` and reschedule those which have to run later.
        collected_jobs = []
        while True:
            try:
                run_at, job = self.gatebot.updater.job_queue._queue.get(False)
                collected_jobs.append((run_at, job))
            except queue.Empty:
                break

        reschedule_jobs = []
        now = time.time()
        for run_at, job in collected_jobs:
            run_at -= delta.total_seconds()
            if run_at < now:
                job.run(self.last_bot_mock)
            else:
                reschedule_jobs.append((run_at, job))

        for run_at, job in reschedule_jobs:
            self.gatebot.updater.job_queue._queue.put((run_at, job))

    #
    # Assert methods
    #

    def assert_no_api_calls(self):
        assert len(self.last_bot_mock.method_calls) == 0

    def assert_no_restriction_api_calls(self):
        assert len(self.last_bot_mock.restrict_chat_member.call_args_list) == 0

    def assert_no_kick_api_calls(self):
        assert len(self.last_bot_mock.kick_chat_member.call_args_list) == 0

    def assert_was_restricted(self):
        self.last_bot_mock.restrict_chat_member.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            user_id=self.user_id,
            can_send_message=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )

    def assert_was_unrestricted(self):
        self.last_bot_mock.restrict_chat_member.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            user_id=self.user_id,
            can_send_message=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )

    def assert_was_kicked(self):
        self.last_bot_mock.kick_chat_member.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            user_id=self.user_id,
        )

    def assert_was_unbanned(self):
        self.last_bot_mock.unban_chat_member.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            user_id=self.user_id,
        )

    def assert_sent_getting_started(self):
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        qs = self.gatebot.config.QUESTIONS_PER_QUIZ
        ans = self.gatebot.config.CORRECT_ANSWERS_REQUIRED
        welcome_text = (
            f"Hello fellow pythonista!\n"
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

    def assert_sent_passed(self, result: int):
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        total = self.gatebot.config.QUESTIONS_PER_QUIZ
        text = (
            f"You have passed the quiz with the result of {result}/{total}.\n"
            "You can now chat in the group.")

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.user_id
        assert text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"
        assert 'reply_markup' not in kwargs

    def assert_sent_failed(self, result: int, wait_hours: int = None):
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        total = self.gatebot.config.QUESTIONS_PER_QUIZ
        required = self.gatebot.config.CORRECT_ANSWERS_REQUIRED
        wait_hours = wait_hours or self.gatebot.config.WAIT_HOURS_ON_FAIL
        text = (
            "Unfortunately you have failed with the result of "
            f"{result}/{total}, which is not enough to pass ({required}). "
            f"But no worries, you can try again in {wait_hours} hours.")

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
                answered: Optional[str] = None,
            ):
        if answered not in [None, 'correct', 'wrong']:
            raise ValueError(f"Invalid value of answered: {answered!r}")

        calls = self.last_bot_mock.edit_message_text.call_args_list
        assert len(calls) == 1

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.user_id
        assert kwargs['message_id'] == message_id
        assert question.text in kwargs['text']
        for ix, opt in enumerate(question.options):
            assert f"{ix}. {opt}" in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"

        if answered is None:
            assert 'Correct' not in kwargs['text']
            assert 'Wrong' not in kwargs['text']
        elif answered == 'correct':
            assert 'Correct' in kwargs['text']
        elif answered == 'wrong':
            assert 'Wrong' in kwargs['text']

        button_rows = kwargs['reply_markup'].inline_keyboard

        if answered is None:
            ans_buttons, nav_buttons = button_rows
        else:
            nav_buttons, = button_rows

        if answered is None:
            assert len(ans_buttons) == len(question.options)
            for ix in range(len(question.options)):
                assert ans_buttons[ix].text == str(ix)
                assert ans_buttons[ix].callback_data == f"answer_{ix}"

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
