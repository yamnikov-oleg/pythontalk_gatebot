from gatebot.bot import GateBot

from .utils import UserSession


def test_deletes_join_messages(gatebot: GateBot):
    session = UserSession(gatebot)

    session.play_joins_group(message_id=1)
    session.assert_deletes_message(1)

    gatebot.config.DELETE_JOIN_MESSAGES = False
    session.play_joins_group(message_id=2)
    session.assert_deletes_no_messages()


def test_deletes_leave_messages(gatebot: GateBot):
    session = UserSession(gatebot)

    session.play_leaves_group(message_id=1)
    session.assert_deletes_message(1)

    gatebot.config.DELETE_LEAVE_MESSAGES = False
    session.play_leaves_group(message_id=2)
    session.assert_deletes_no_messages()
