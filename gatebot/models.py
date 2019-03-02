from typing import List

from sqlalchemy import Column, Integer, DateTime, func, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship

from .questions import Question

Base = declarative_base()


class QuizPass(Base):
    """
    A single quiz pass for a given user. Created when user starts (or restarts)
    the quiz, and questions for the pass have been selected.
    """
    __tablename__ = 'quizpass'

    id = Column(Integer, primary_key=True)

    # Telegram user id
    user_id = Column(Integer, index=True, nullable=False)
    correct_required = Column(Integer, nullable=False)
    current_item_index = Column(Integer, nullable=False, server_default='0')
    created_at = Column(
        DateTime(timezone=True), default=func.now(), nullable=False)

    quizitems = relationship(
        'QuizItem',
        order_by='QuizItem.index',
        back_populates='quizpass')

    @property
    def current_item(self) -> 'QuizItem':
        for item in self.quizitems:
            if item.index == self.current_item_index:
                return item
        raise ValueError(f"Item index out of range: {self.current_item_index}")


class QuizItem(Base):
    __tablename__ = 'quizitem'

    id = Column(Integer, primary_key=True)

    quizpass_id = Column(Integer, ForeignKey('quizpass.id'), nullable=False)
    quizpass = relationship(
        'QuizPass',
        back_populates='quizitems')

    index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    correct_answer = Column(Integer, nullable=False)

    options = relationship(
        'Option',
        order_by='Option.index',
        back_populates='quizitem')


class Option(Base):
    __tablename__ = 'option'

    id = Column(Integer, primary_key=True)

    quizitem_id = Column(Integer, ForeignKey('quizitem.id'), nullable=False)
    quizitem = relationship(
        'QuizItem',
        back_populates='options')

    index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)


def init_models(engine):
    # TODO: Is this necessary? Check later. I would like to avoid
    # any global state in the project.
    Base.metadata.bind = engine


def create_quizpass(
            session: Session,
            user_id: int,
            questions: List[Question],
            correct_required: int,
        ) -> QuizPass:
    quizpass = QuizPass(
        user_id=user_id,
        correct_required=correct_required,
    )
    session.add(quizpass)
    session.commit()

    for q_ix, question in enumerate(questions):
        item = QuizItem(
            quizpass_id=quizpass.id,
            index=q_ix,
            text=question.text,
            correct_answer=question.answer,
        )
        session.add(item)
        session.commit()

        for option_index, option_text in enumerate(question.options):
            option = Option(
                quizitem_id=item.id,
                index=option_index,
                text=option_text,
            )
            session.add(option)
            session.commit()

    return quizpass
