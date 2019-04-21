from gatebot.bot import GateBot

from .utils import UserSession


def test_cascade_deletion(gatebot: GateBot):
    from gatebot.models import QuizPass

    session = UserSession(gatebot)

    session.play_sends_callback_query(1, "start_quiz")

    with gatebot.db_session() as db:
        for qp in db.query(QuizPass):
            db.delete(qp)
        db.commit()
