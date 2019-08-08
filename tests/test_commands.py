import pytest

from gatebot.bot import GateBot
from gatebot.questions import Question

from .utils import UserSession, mock_user_entity


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


def make_passed_member(gatebot: GateBot, member_status: str):
    session = UserSession(
        gatebot,
        force_questions=[
            QUESTION_1,
            QUESTION_2,
            QUESTION_3,
        ],
        member_status=member_status)

    session.play_joins_group()
    session.play_sends_callback_query(1, "start_quiz")
    session.play_sends_callback_query(1, "answer_0")  # Correct
    session.play_sends_callback_query(1, "next")
    session.play_sends_callback_query(1, "answer_3")  # Correct
    session.play_sends_callback_query(1, "next")
    session.play_sends_callback_query(1, "answer_1")  # Correct
    session.assert_sent_passed(result=3)
    session.assert_was_unrestricted()

    return session


@pytest.mark.parametrize('admin_status', ['admin', 'creator'])
@pytest.mark.parametrize('method', ['by_id', 'by_text_mention', 'by_reply'])
def test_kick(gatebot: GateBot, admin_status: str, method):
    member_session = make_passed_member(gatebot, 'member')
    admin_session = make_passed_member(gatebot, admin_status)

    if method == 'by_id':
        admin_session.play_sends_command_group(f"kick {member_session.user_id}")
    elif method == 'by_text_mention':
        admin_session.play_sends_command_group(f"kick 1", entities=[
            mock_user_entity(member_session),
        ])
    elif method == 'by_reply':
        admin_session.play_sends_command_group(f"kick 1", reply_to=member_session)
    else:
        raise ValueError(method)

    admin_session.assert_was_kicked(user_id=member_session.user_id)
    admin_session.assert_was_unbanned(user_id=member_session.user_id)
    admin_session.assert_sent_kicked(member_session, by_id=(method == 'by_id'))

    member_session.play_joins_group()
    member_session.assert_was_restricted()

    member_session.play_sends_callback_query(1, "start_quiz")
    member_session.assert_question_displayed(1, QUESTION_1, pos=1)


def test_kickme(gatebot: GateBot):
    session = make_passed_member(gatebot, 'member')

    session.play_sends_command_group("kickme")
    session.assert_was_kicked()
    session.assert_was_unbanned()
    session.assert_sent_kicked(session)

    session.play_joins_group()
    session.assert_was_restricted()

    session.play_sends_callback_query(1, "start_quiz")
    session.assert_question_displayed(1, QUESTION_1, pos=1)


@pytest.mark.parametrize('admin_status', ['admin', 'creator'])
@pytest.mark.parametrize('method', ['by_id', 'by_text_mention', 'by_reply'])
def test_ban(gatebot: GateBot, admin_status: str, method):
    member_session = make_passed_member(gatebot, 'member')
    admin_session = make_passed_member(gatebot, admin_status)

    if method == 'by_id':
        admin_session.play_sends_command_group(f"ban {member_session.user_id}")
    elif method == 'by_text_mention':
        admin_session.play_sends_command_group(f"ban 1", entities=[
            mock_user_entity(member_session),
        ])
    elif method == 'by_reply':
        admin_session.play_sends_command_group(f"ban 1", reply_to=member_session)
    else:
        raise ValueError(method)

    admin_session.assert_was_kicked(user_id=member_session.user_id)
    admin_session.assert_sent_banned(member_session, by_id=(method == 'by_id'))


@pytest.mark.parametrize('command', ['kick', 'ban'])
@pytest.mark.parametrize('method', ['by_id', 'by_text_mention', 'by_reply'])
def test_unauthorized(gatebot: GateBot, command, method):
    member_session = make_passed_member(gatebot, 'member')
    nonadmin_session = make_passed_member(gatebot, 'member')

    if method == 'by_id':
        nonadmin_session.play_sends_command_group(
            f"{command} {member_session.user_id}")
    elif method == 'by_text_mention':
        nonadmin_session.play_sends_command_group(f"{command} 1", entities=[
            mock_user_entity(member_session),
        ])
    elif method == 'by_reply':
        nonadmin_session.play_sends_command_group(f"{command} 1", reply_to=member_session)
    else:
        raise ValueError(method)

    nonadmin_session.assert_sent_unauthorized()
