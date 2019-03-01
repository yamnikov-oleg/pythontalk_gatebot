import telegram
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    telegram_user_id = Column(String(255), nullable=False)


def init_models(engine):
    # TODO: Is this necessary? Check later. I would like to avoid
    # any global state in the project.
    Base.metadata.bind = engine


def get_or_create_user(session: Session, tg_user: telegram.User) -> User:
    user = session.query(User)\
        .filter(User.telegram_user_id == tg_user.id)\
        .first()

    if not user:
        user = User(
            telegram_user_id=tg_user.id,
        )
        session.add(user)
        session.commit()

    return user
