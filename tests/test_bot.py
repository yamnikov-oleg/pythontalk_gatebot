from unittest.mock import NonCallableMagicMock

from telegram import Bot

from gatebot.bot import GateBot

from .fixtures import *  # noqa: F401,F403


def test_user_joins(gatebot: GateBot):
    bot = NonCallableMagicMock(spec=Bot)

    update = NonCallableMagicMock()
    update.message.chat.id = -111
    update.message.new_chat_members = [NonCallableMagicMock(id=11)]

    gatebot.new_chat_members(bot, update)

    bot.restrict_chat_member.assert_called_once_with(
        chat_id=-111,
        user_id=11,
        can_send_message=False,
        can_send_media_messages=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
    )
