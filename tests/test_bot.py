from unittest.mock import NonCallableMagicMock

from telegram import Bot
from pytest import fixture

from config import TestConfig
from gatebot.bot import GateBot
from gatebot.models import Base


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

    def test_user_starts_quiz(self, gatebot: GateBot):
        bot = self.play_user_sends_command(
            gatebot, "start", user_id=111, first_name="TestUser8")
        self.assert_getting_started_sent(
            gatebot, bot, user_id=111, first_name="TestUser8")

    def test_user_sends_start_in_group(self, gatebot: GateBot):
        bot = self.play_user_sends_command_in_group(
            gatebot, "start", user_id=111, first_name="TestUser8")
        self.assert_no_api_calls(bot)

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
                first_name: str,
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
