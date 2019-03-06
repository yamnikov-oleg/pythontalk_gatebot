from datetime import timedelta

from gatebot.bot import GateBot

from .utils import UserSession


def test_kick_inactive_user(gatebot: GateBot):
    session = UserSession(gatebot)

    session.play_joins_group()

    session.play_time_passed(timedelta(minutes=14))
    session.assert_no_kick_api_calls()

    session.play_time_passed(timedelta(minutes=2))
    session.assert_was_kicked()
    # Unban user they can join back.
    session.assert_was_unbanned()


def test_dont_kick_active_user(gatebot: GateBot):
    session = UserSession(gatebot)

    session.play_joins_group()

    session.play_time_passed(timedelta(minutes=14))
    session.play_sends_command("start")
    session.play_sends_callback_query(1, "start_quiz")

    session.play_time_passed(timedelta(minutes=2))
    session.assert_no_kick_api_calls()
