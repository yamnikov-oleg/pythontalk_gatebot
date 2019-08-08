import queue
import time
from contextlib import contextmanager
from datetime import timedelta
from random import randint
from typing import Optional, List
from unittest.mock import NonCallableMagicMock, patch

from telegram import Bot, ChatMember, MessageEntity

from gatebot import models, messages
from gatebot.bot import GateBot
from gatebot.questions import Question


def generate_id() -> int:
    """
    Can be used to randomly generate user ids, message ids, etc.
    """
    return randint(100, 1000)


def mock_user_entity(session: 'UserSession'):
    entity = NonCallableMagicMock()
    entity.user.id = session.user_id
    entity.user.first_name = session.first_name
    return entity


class UserSession:
    """
    This class provides several methods to simulate a user's actions and
    other events (play_* methods) and assert bot's reaction to these events
    (assert_* methods).

    Each "play" method resets the mock of telegram bot api, which means that
    assert methods only assert bot's reaction to the most recent action.

    Upon construction this class generates a new user id and sends all updates
    to the bot on the behalf of that virtual user.
    """
    def __init__(
                self,
                gatebot: GateBot,
                force_questions: Optional[List[Question]] = None,
                member_status: str = 'member',
            ):
        """
        If force_questions is specified, UserSession will patch
        random.sample function to make GateBot generate new quizzes with
        the given questions.
        """
        self.gatebot = gatebot
        self.user_id = generate_id()
        self.force_questions = force_questions
        self.member_status = member_status

        self.first_name = "Test<User>"
        # Should be displayed in HTML messages
        self.escaped_first_name = "Test&lt;User&gt;"

        self.last_bot_mock = None
        self.last_play_data = {}
        self._reset_stage()

    def _reset_stage(self) -> NonCallableMagicMock:
        self.last_bot_mock = NonCallableMagicMock(spec=Bot)

        # Set up get_chat_member mock
        def get_chat_member(chat_id, user_id):
            if int(user_id) == self.user_id:
                status = self.member_status
            else:
                status = 'member'

            chat_member = NonCallableMagicMock(spec=ChatMember)
            chat_member.status = status
            return chat_member

        self.last_bot_mock.get_chat_member.side_effect = get_chat_member

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

    def play_joins_group(self, message_id=None):
        """User joins the group"""
        self._reset_stage()

        update = NonCallableMagicMock()
        update.message.message_id = message_id or generate_id()
        update.message.chat.id = self.gatebot.config.GROUP_ID
        update.message.new_chat_members = [
            NonCallableMagicMock(id=self.user_id, first_name=self.first_name),
        ]

        with self._gatebot_env():
            self.gatebot.new_chat_members(self.last_bot_mock, update)

    def play_leaves_group(self, message_id=None):
        """User leaves the group"""
        self._reset_stage()

        update = NonCallableMagicMock()
        update.message.message_id = message_id or generate_id()
        update.message.chat.id = self.gatebot.config.GROUP_ID
        update.message.left_chat_member = \
            NonCallableMagicMock(id=self.user_id, first_name=self.first_name)

        with self._gatebot_env():
            self.gatebot.left_chat_member(self.last_bot_mock, update)

    def play_sends_command(self, command: str) -> int:
        """User sends a command to the bot in PM"""
        self._reset_stage()

        update = NonCallableMagicMock()
        update.message.chat.id = self.user_id
        update.message.from_user.id = self.user_id
        update.message.from_user.first_name = self.first_name

        method = getattr(self.gatebot, f'command_{command}')
        with self._gatebot_env():
            method(self.last_bot_mock, update)

    def play_sends_command_group(
            self,
            command_text: str,
            entities=None,
            reply_to: 'UserSession' = None):
        """User sends a command to the group"""
        self._reset_stage()

        if " " in command_text:
            command, _ = command_text.split(" ", 1)
        else:
            command = command_text

        update = NonCallableMagicMock()
        update.message.chat.id = self.gatebot.config.GROUP_ID
        update.message.from_user.id = self.user_id
        update.message.from_user.first_name = self.first_name
        update.message.text = command_text
        update.message.entities = entities

        if reply_to:
            update.message.reply_to_message.from_user.id = reply_to.user_id
            update.message.reply_to_message.from_user.first_name = reply_to.first_name
        else:
            update.message.reply_to_message = None

        method = getattr(self.gatebot, f'command_{command}')
        with self._gatebot_env():
            method(self.last_bot_mock, update)

    def play_sends_callback_query(self, message_id: int, data: str):
        """User sends a callback query"""
        self._reset_stage()

        self.last_play_data['callback_query_id'] = generate_id()

        update = NonCallableMagicMock()
        update.callback_query.id = self.last_play_data['callback_query_id']
        update.callback_query.data = data
        update.callback_query.from_user.id = self.user_id
        update.callback_query.from_user.first_name = self.first_name
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
        """
        This methods simulates passage of time using following hacks:
        1. It shifts datetimes in the gatebot's DB back by delta.
        2. It reschedules jobs in ptb's updater's job queue back by delta and
        runs those jobs which are due.
        """
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
        """GateBot made to calls to telegram bot api"""
        assert len(self.last_bot_mock.method_calls) == 0

    def assert_no_restriction_api_calls(self):
        """GateBot made no restrict_chat_member calls"""
        assert len(self.last_bot_mock.restrict_chat_member.call_args_list) == 0

    def assert_no_kick_api_calls(self):
        """GateBot made no kick_chat_member calls"""
        assert len(self.last_bot_mock.kick_chat_member.call_args_list) == 0

    def assert_was_restricted(self):
        """GateBot restricted current user"""
        self.last_bot_mock.restrict_chat_member.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            user_id=self.user_id,
            can_send_message=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )

    def assert_was_unrestricted(self):
        """GateBot unrestricted current user"""
        self.last_bot_mock.restrict_chat_member.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            user_id=self.user_id,
            can_send_message=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )

    def assert_was_kicked(self, user_id=None):
        """GateBot kicked current user"""
        self.last_bot_mock.kick_chat_member.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            user_id=user_id or self.user_id,
        )

    def assert_was_unbanned(self, user_id=None):
        """GateBot unbanned current user"""
        self.last_bot_mock.unban_chat_member.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            user_id=user_id or self.user_id,
        )

    def assert_no_messages_sent(self):
        """GateBot made no send_message calls"""
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 0

    def assert_sent_getting_started(self):
        """
        GateBot sent "getting started" message to the user with the button
        to start the quiz.
        """
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        welcome_text = messages.GETTING_STARTED.format(
            questions_total=self.gatebot.config.QUESTIONS_PER_QUIZ,
            answers_required=self.gatebot.config.CORRECT_ANSWERS_REQUIRED,
        )

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

    def assert_sent_passed(self, result: int):
        """
        GateBot notified user that they have passed the test and shown
        their result with the button to share it.
        """
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        text = messages.PASSED.format(
            result=result,
            total=self.gatebot.config.QUESTIONS_PER_QUIZ,
        )

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.user_id
        assert text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"

        button_rows = kwargs['reply_markup'].inline_keyboard
        assert len(button_rows) == 1
        buttons = button_rows[0]
        assert len(buttons) == 1
        button = buttons[0]
        assert button.text == "Share the result"
        assert button.callback_data == "share_result"

    def assert_sent_failed(self, result: int, wait_hours: int = None):
        """
        GateBot notified user that they have passed the test and shown
        their result.
        """
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        text = messages.FAILED.format(
            result=result,
            total=self.gatebot.config.QUESTIONS_PER_QUIZ,
            required=self.gatebot.config.CORRECT_ANSWERS_REQUIRED,
            wait_hours=wait_hours or self.gatebot.config.WAIT_HOURS_ON_FAIL,
        )

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.user_id
        assert text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"
        assert 'reply_markup' not in kwargs

    def assert_sent_results(self, result: int):
        """
        GateBot sent user's quiz result into the group.
        """
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        user_link = (
            f'<a href="tg://user?id={self.user_id}">'
            f'{self.escaped_first_name}</a>')
        text = messages.RESULT_SHARE.format(
            user=user_link,
            result=result,
            total=self.gatebot.config.QUESTIONS_PER_QUIZ,
        )

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.gatebot.config.GROUP_ID
        assert text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"
        assert 'reply_markup' not in kwargs

    def assert_sent_unauthorized(self):
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.gatebot.config.GROUP_ID
        assert messages.UNAUTHORIZED in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"

    def assert_sent_kicked(self, session: 'UserSession', by_id: bool = False):
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        if by_id:
            displayed_name = session.user_id
        else:
            displayed_name = session.escaped_first_name

        user_link = (
            f'<a href="tg://user?id={session.user_id}">'
            f'{displayed_name}</a>')
        text = messages.KICKED.format(user=user_link)

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.gatebot.config.GROUP_ID
        assert text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"

    def assert_sent_banned(self, session: 'UserSession', by_id: bool = False):
        calls = self.last_bot_mock.send_message.call_args_list
        assert len(calls) == 1

        if by_id:
            displayed_name = session.user_id
        else:
            displayed_name = session.escaped_first_name

        user_link = (
            f'<a href="tg://user?id={session.user_id}">'
            f'{displayed_name}</a>')
        text = messages.BANNED.format(user=user_link)

        args, kwargs = calls[0]
        assert kwargs['chat_id'] == self.gatebot.config.GROUP_ID
        assert text in kwargs['text']
        assert kwargs['parse_mode'] == "HTML"

    def assert_question_displayed(
                self,
                message_id: int,
                question: Question,
                pos: int,
                answered: Optional[str] = None,
            ):
        """
        GateBot updated the quiz message to display the given question.

        `pos` specified number of the question in the quiz (1 for the first
        question), which is required because GateBot displays it in the
        message.

        If `answered` is not specified, the question will be expected to be
        unanswered.
        If `answered` is set to 'correct', the question will be expected to
        be answered correctly.
        If `answered` is set to 'wrong', the question will be expected to
        be answered incorrectly.
        """
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

    def assert_deletes_message(self, message_id):
        """GateBot has deleted the given message"""
        self.last_bot_mock.delete_message.assert_called_once_with(
            chat_id=self.gatebot.config.GROUP_ID,
            message_id=message_id,
        )

    def assert_deletes_no_messages(self):
        """GateBot made no delete_message calls"""
        self.last_bot_mock.delete_message.assert_not_called()
