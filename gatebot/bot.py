import logging
import random
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, MessageHandler, CommandHandler, Filters
from telegram.update import Update
from telegram.utils.request import Request

from config.base import BaseConfig

from . import messages
from .models import init_models, create_quizpass, QuizPass
from .questions import load_question


logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s : %(name)s : %(levelname)s] %(message)s',
)


class GateBot:
    def __init__(self, config: BaseConfig) -> None:
        self.config = config

        self.logger = logging.getLogger('gatebot')
        self.updater = self._init_updater()
        self.db_sessionmaker = self._init_db_sessionmaker()
        self.questions = load_question(self.config.QUESTIONS_FILE)

    def _init_updater(self) -> Updater:
        if self.config.PROXY_URL:
            request = Request(con_pool_size=8, proxy_url=self.config.PROXY_URL)
            bot = Bot(self.config.BOT_TOKEN, request=request)
        else:
            bot = Bot(self.config.BOT_TOKEN)

        updater = Updater(
            bot=bot,
            request_kwargs={
                "read_timeout": 6,
                "connect_timeout": 7,
            },
        )

        dispatcher = updater.dispatcher

        dispatcher.add_handler(
            MessageHandler(
                Filters.status_update.new_chat_members,
                self.new_chat_members))
        dispatcher.add_handler(CommandHandler('start', self.command_start))

        return updater

    def _init_db_sessionmaker(self) -> sessionmaker:
        engine = create_engine(self.config.SQLALCHEMY_URL)
        init_models(engine)

        sm = sessionmaker(bind=engine)
        return sm

    @contextmanager
    def db_session(self):
        session = self.db_sessionmaker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def run(self) -> None:
        self.logger.info("GateBot started")
        self.logger.info("Loaded questions: %s", len(self.questions))
        self.updater.start_polling()

    def new_chat_members(self, bot: Bot, update: Update) -> None:
        for member in update.message.new_chat_members:
            self.logger.info(
                "New user %s joined, id: %s", member.first_name, member.id)
            bot.restrict_chat_member(
                chat_id=update.message.chat.id,
                user_id=member.id,
                can_send_message=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            )

    def _generate_quizpass(self, session: Session, user_id: int) -> QuizPass:
        questions = random.sample(
            self.questions,
            self.config.QUESTIONS_PER_QUIZ,
        )
        return create_quizpass(session, user_id, questions)

    def command_start(self, bot: Bot, update: Update) -> None:
        if update.message.chat.id != update.message.from_user.id:
            # Ignore commands sent not in pm
            return

        self.logger.info(
            "/start command sent by %s, id: %s",
            update.message.from_user.first_name,
            update.message.from_user.id)

        bot.send_message(
            chat_id=update.message.chat.id,
            text=messages.GETTING_STARTED.format(
                first_name=update.message.from_user.first_name,
                questions_total=self.config.QUESTIONS_PER_QUIZ,
                answers_required=self.config.CORRECT_ANSWERS_REQUIRED,
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Start the quiz", callback_data="start_quiz"),
            ]]),
        )
