import logging
import random
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (Updater, MessageHandler, CommandHandler, Filters,
                          CallbackQueryHandler)
from telegram.update import Update
from telegram.utils.request import Request

from config.base import BaseConfig

from . import messages
from .models import init_models, create_quizpass, get_active_quizpass, QuizPass
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
        dispatcher.add_handler(CallbackQueryHandler(self.callback_query))
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

    def command_start(self, bot: Bot, update: Update) -> None:
        if update.message.chat.id != update.message.from_user.id:
            # Ignore commands sent not in pm
            return

        self.logger.info(
            "/start command sent by %s, id: %s",
            update.message.from_user.first_name,
            update.message.from_user.id)

        with self.db_session() as session:
            quizpass = get_active_quizpass(
                session, update.message.from_user.id)
            if quizpass:
                bot.send_message(
                    chat_id=update.message.from_user.id,
                    text="You have already started the quiz.",
                    parse_mode="HTML")
                return

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

    def callback_query(self, bot: Bot, update: Update) -> None:
        if update.callback_query.data == "ignore":
            self.callback_query_ignore(bot, update)
        elif update.callback_query.data == "start_quiz":
            self.callback_query_start_quiz(bot, update)
        elif update.callback_query.data == "next":
            self.callback_query_next(bot, update)
        elif update.callback_query.data == "prev":
            self.callback_query_prev(bot, update)
        else:
            self.callback_query_unknown(bot, update)

    def callback_query_unknown(self, bot: Bot, update: Update) -> None:
        self.logger.info(
            "Unknown callback query: %s", update.callback_query.data)
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

    def callback_query_ignore(self, bot: Bot, update: Update) -> None:
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

    def callback_query_start_quiz(self, bot: Bot, update: Update) -> None:
        self.logger.info("Callback query: start_quiz")
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(
                session, update.callback_query.from_user.id)
            if quizpass:
                bot.send_message(
                    chat_id=update.callback_query.from_user.id,
                    text="You have already started the quiz.",
                    parse_mode="HTML")
                return

            quizpass = self._generate_quizpass(
                session, update.callback_query.from_user.id)
            self._display_quizpass(
                bot,
                update.callback_query.message.message_id,
                update.callback_query.from_user.id,
                quizpass,
            )

    def callback_query_next(self, bot: Bot, update: Update) -> None:
        self.logger.info("Callback query: next")
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(
                session, update.callback_query.from_user.id)
            quizpass.move_to_next()
            session.commit()

            self._display_quizpass(
                bot,
                update.callback_query.message.message_id,
                update.callback_query.from_user.id,
                quizpass,
            )

    def callback_query_prev(self, bot: Bot, update: Update) -> None:
        self.logger.info("Callback query: prev")
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(
                session, update.callback_query.from_user.id)
            quizpass.move_to_prev()
            session.commit()

            self._display_quizpass(
                bot,
                update.callback_query.message.message_id,
                update.callback_query.from_user.id,
                quizpass,
            )

    def _generate_quizpass(self, session: Session, user_id: int) -> QuizPass:
        questions = random.sample(
            self.questions,
            self.config.QUESTIONS_PER_QUIZ,
        )
        return create_quizpass(
            session,
            user_id,
            questions,
            self.config.CORRECT_ANSWERS_REQUIRED,
        )

    def _display_quizpass(
                self,
                bot: Bot,
                message_id: int,
                user_id: int,
                quizpass: QuizPass,
            ) -> None:
        item = quizpass.current_item
        text = f"{item.text}\n\n"
        for option in item.options:
            text += f"{option.index}. {option.text}\n"
        text = text.strip()

        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("<", callback_data="prev"),
                    InlineKeyboardButton(
                        f"{item.index + 1}/{self.config.QUESTIONS_PER_QUIZ}",
                        callback_data="ignore",
                    ),
                    InlineKeyboardButton(">", callback_data="next"),
                ],
            ]),
        )
