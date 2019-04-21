from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (BigInteger, Boolean, Column, ForeignKey, Integer, Text,
                        func)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship
from sqlalchemy_utc import UtcDateTime

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
    user_id = Column(BigInteger, index=True, nullable=False)
    correct_required = Column(Integer, nullable=False)
    current_item_index = Column(Integer, nullable=False, server_default='0')
    created_at = Column(UtcDateTime, default=func.now(), nullable=False)
    result_shared = Column(Boolean, default=False, server_default='False')

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

    def move_to_next(self):
        self.current_item_index += 1
        if self.current_item_index >= len(self.quizitems):
            self.current_item_index = 0

    def move_to_prev(self):
        self.current_item_index -= 1
        if self.current_item_index < 0:
            self.current_item_index = len(self.quizitems) - 1

    @property
    def is_finished(self) -> bool:
        return all(item.is_answered for item in self.quizitems)

    @property
    def correct_given(self) -> int:
        return len([
            item
            for item in self.quizitems
            if item.is_answered_correctly
        ])

    @property
    def has_passed(self) -> bool:
        return self.correct_given >= self.correct_required

    @property
    def last_answer_at(self) -> Optional[datetime]:
        answer_times = [
            item.answered_at
            for item in self.quizitems
            if item.answered_at]
        if answer_times:
            return max(answer_times)
        return None


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
    given_answer = Column(Integer)
    answered_at = Column(UtcDateTime)

    options = relationship(
        'Option',
        order_by='Option.index',
        back_populates='quizitem')

    def set_answer(self, answer: int):
        if answer < 0 or answer >= len(self.options):
            raise ValueError(f"Answer out of range: {answer}")

        self.given_answer = answer
        self.answered_at = datetime.utcnow().replace(tzinfo=timezone.utc)

    @property
    def is_answered(self) -> bool:
        return self.given_answer is not None and self.answered_at

    @property
    def is_answered_correctly(self) -> bool:
        return self.is_answered and self.correct_answer == self.given_answer


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


def get_active_quizpass(session: Session, user_id: int) -> Optional[QuizPass]:
    return session.query(QuizPass)\
        .filter(QuizPass.user_id == user_id)\
        .order_by(QuizPass.created_at.desc())\
        .first()
