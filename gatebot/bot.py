import logging
import math
import random
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from telegram import (Bot, ChatPermissions, InlineKeyboardButton,
                      InlineKeyboardMarkup, User)
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters, Job,
                          MessageHandler, Updater)
from telegram.update import Update
from telegram.utils.request import Request

from config.base import BaseConfig

from . import messages
from .models import QuizPass, create_quizpass, get_active_quizpass, init_models
from .questions import load_questions

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
        self.questions = load_questions(self.config.QUESTIONS_FILE)

    def _init_updater(self) -> Updater:
        if self.config.PROXY_URL:
            request = Request(con_pool_size=8, proxy_url=self.config.PROXY_URL)
            bot = Bot(self.config.BOT_TOKEN, request=request)
        else:
            request = Request(con_pool_size=8)
            bot = Bot(self.config.BOT_TOKEN, request=request)

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
        dispatcher.add_handler(
            MessageHandler(
                Filters.status_update.left_chat_member,
                self.left_chat_member))
        dispatcher.add_handler(CallbackQueryHandler(self.callback_query))
        dispatcher.add_handler(CommandHandler('start', self.command_start))
        dispatcher.add_handler(CommandHandler('kick', self.command_kick))
        dispatcher.add_handler(CommandHandler('kickme', self.command_kickme))
        dispatcher.add_handler(CommandHandler('ban', self.command_ban))

        return updater

    def _init_db_sessionmaker(self) -> sessionmaker:
        engine = create_engine(self.config.SQLALCHEMY_URL)
        init_models(engine)

        sm = sessionmaker(bind=engine)
        return sm

    def _escape_html(self, s: str) -> str:
        return s.replace("<", "&lt;").replace(">", "&gt;")

    def _display_user(self, id, first_name) -> str:
        return (
            f'<a href="tg://user?id={id}">'
            f'{self._escape_html(first_name)}'
            '</a>')

    def _log_user(self, user: User) -> str:
        return f"{user.first_name} (id={user.id})"

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
        with self.db_session() as session:
            for member in update.message.new_chat_members:
                self.logger.info(
                    "New user joined: %s", self._log_user(member))

                quizpass = get_active_quizpass(session, member.id)
                allowed_to_chat = quizpass and \
                    quizpass.is_finished and \
                    quizpass.has_passed

                if not allowed_to_chat:
                    bot.restrict_chat_member(
                        chat_id=update.message.chat.id,
                        user_id=member.id,
                        permissions=ChatPermissions(
                            can_send_message=False,
                            can_send_media_messages=False,
                            can_send_other_messages=False,
                            can_add_web_page_previews=False,
                            can_send_polls=False,
                        ),
                    )

                    self.updater.job_queue.run_once(
                        self.job_kick_if_inactive,
                        when=self.config.KICK_INACTIVE_AFTER,
                        context=member.id)

        if self.config.DELETE_JOIN_MESSAGES:
            bot.delete_message(
                chat_id=update.message.chat.id,
                message_id=update.message.message_id,
            )

    def left_chat_member(self, bot: Bot, update: Update) -> None:
        self.logger.info(
            "User left: %s", self._log_user(update.message.left_chat_member))
        if self.config.DELETE_LEAVE_MESSAGES:
            bot.delete_message(
                chat_id=update.message.chat.id,
                message_id=update.message.message_id,
            )

    def job_kick_if_inactive(self, bot: Bot, job: Job):
        with self.db_session() as session:
            user_id = job.context
            quizpass = get_active_quizpass(session, user_id)
            if not quizpass:
                self.logger.info(
                    "User (id=%s) was kicked for not starting the quiz",
                    user_id)
                bot.kick_chat_member(
                    chat_id=self.config.GROUP_ID,
                    user_id=user_id)
                bot.unban_chat_member(
                    chat_id=self.config.GROUP_ID,
                    user_id=user_id)

    def command_start(self, bot: Bot, update: Update) -> None:
        if update.message.chat.id != update.message.from_user.id:
            # Ignore commands sent not in pm
            return

        self.logger.info(
            "/start command sent by %s",
            self._log_user(update.message.from_user))

        with self.db_session() as session:
            if not self._on_start_quiz(
                    session, bot, update.message.from_user.id):
                return

        bot.send_message(
            chat_id=update.message.chat.id,
            text=messages.GETTING_STARTED.format(
                questions_total=self.config.QUESTIONS_PER_QUIZ,
                answers_required=self.config.CORRECT_ANSWERS_REQUIRED,
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Start the quiz", callback_data="start_quiz"),
            ]]),
        )

    def _get_target(self, update: Update) -> Optional[Tuple[int, str]]:
        if update.message.entities:
            for entity in update.message.entities:
                if entity.user:
                    return entity.user.id, entity.user.first_name

        if update.message.reply_to_message:
            user = update.message.reply_to_message.from_user
            return user.id, user.first_name

        try:
            command, args = update.message.text.split(" ", 1)
            return int(args), args
        except (TypeError, ValueError):
            pass

        return None

    def _is_admin(self, bot: Bot, user_id: int) -> bool:
        chat_member = bot.get_chat_member(self.config.GROUP_ID, user_id)
        return chat_member.status in ['creator', 'admin']

    def command_kick(self, bot: Bot, update: Update) -> None:
        if not self._is_admin(bot, update.message.from_user.id):
            bot.send_message(
                chat_id=self.config.GROUP_ID,
                text=messages.UNAUTHORIZED,
                parse_mode="HTML",
                reply_to_message_id=update.message.message_id,
            )
            return

        self.logger.info(
            "/kick command sent by %s",
            self._log_user(update.message.from_user))

        target = self._get_target(update)
        if not target:
            bot.send_message(
                chat_id=self.config.GROUP_ID,
                text=messages.NO_TARGET,
                parse_mode="HTML",
                reply_to_message_id=update.message.message_id,
            )
            return

        target_id, target_name = target

        bot.kick_chat_member(
            chat_id=self.config.GROUP_ID,
            user_id=target_id)
        bot.unban_chat_member(
            chat_id=self.config.GROUP_ID,
            user_id=target_id)

        bot.send_message(
            chat_id=self.config.GROUP_ID,
            text=messages.KICKED.format(user=self._display_user(target_id, target_name)),
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(session, target_id)
            if quizpass:
                session.delete(quizpass)

    def command_kickme(self, bot: Bot, update: Update) -> None:
        self.logger.info(
            "/kickme command sent by %s",
            self._log_user(update.message.from_user))

        target = update.message.from_user

        bot.kick_chat_member(
            chat_id=self.config.GROUP_ID,
            user_id=target.id)
        bot.unban_chat_member(
            chat_id=self.config.GROUP_ID,
            user_id=target.id)

        bot.send_message(
            chat_id=self.config.GROUP_ID,
            text=messages.KICKED.format(user=self._display_user(target.id, target.first_name)),
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(session, target.id)
            if quizpass:
                session.delete(quizpass)

    def command_ban(self, bot: Bot, update: Update) -> None:
        if not self._is_admin(bot, update.message.from_user.id):
            bot.send_message(
                chat_id=self.config.GROUP_ID,
                text=messages.UNAUTHORIZED,
                parse_mode="HTML",
                reply_to_message_id=update.message.message_id,
            )
            return

        self.logger.info(
            "/ban command sent by %s",
            self._log_user(update.message.from_user))

        target = self._get_target(update)
        if not target:
            bot.send_message(
                chat_id=self.config.GROUP_ID,
                text=messages.NO_TARGET,
                parse_mode="HTML",
                reply_to_message_id=update.message.message_id,
            )
            return

        target_id, target_name = target

        bot.kick_chat_member(
            chat_id=self.config.GROUP_ID,
            user_id=target_id)

        bot.send_message(
            chat_id=self.config.GROUP_ID,
            text=messages.BANNED.format(user=self._display_user(target_id, target_name)),
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(session, target_id)
            if quizpass:
                session.delete(quizpass)

    def callback_query(self, bot: Bot, update: Update) -> None:
        answer_re = re.compile(r'^answer_(\d+)$')
        answer_match = answer_re.match(update.callback_query.data)

        if update.callback_query.data == "ignore":
            self.callback_query_ignore(bot, update)
        elif update.callback_query.data == "start_quiz":
            self.callback_query_start_quiz(bot, update)
        elif update.callback_query.data == "next":
            self.callback_query_next(bot, update)
        elif update.callback_query.data == "prev":
            self.callback_query_prev(bot, update)
        elif answer_match:
            self.callback_query_answer(bot, update, int(answer_match.group(1)))
        elif update.callback_query.data == "share_result":
            self.callback_query_share_result(bot, update)
        else:
            self.callback_query_unknown(bot, update)

    def callback_query_unknown(self, bot: Bot, update: Update) -> None:
        self.logger.info(
            "Unknown callback query '%s' from %s",
            update.callback_query.data,
            self._log_user(update.callback_query.from_user))
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

    def callback_query_ignore(self, bot: Bot, update: Update) -> None:
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

    def callback_query_start_quiz(self, bot: Bot, update: Update) -> None:
        self.logger.info(
            "Callback query 'start_quiz' from %s",
            self._log_user(update.callback_query.from_user))
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

        with self.db_session() as session:
            if not self._on_start_quiz(
                    session, bot, update.callback_query.from_user.id):
                return

            quizpass = get_active_quizpass(
                session, update.callback_query.from_user.id)
            if quizpass and not quizpass.is_finished:
                self._display_quizpass(
                    bot,
                    update.callback_query.message.message_id,
                    update.callback_query.from_user.id,
                    quizpass,
                )
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
        self.logger.info(
            "Callback query 'next' from %s",
            self._log_user(update.callback_query.from_user))
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(
                session, update.callback_query.from_user.id)
            if not quizpass:
                return

            quizpass.move_to_next()
            session.commit()

            self._display_quizpass(
                bot,
                update.callback_query.message.message_id,
                update.callback_query.from_user.id,
                quizpass,
            )

    def callback_query_prev(self, bot: Bot, update: Update) -> None:
        self.logger.info(
            "Callback query 'prev' from %s",
            self._log_user(update.callback_query.from_user))
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(
                session, update.callback_query.from_user.id)
            if not quizpass:
                return

            quizpass.move_to_prev()
            session.commit()

            self._display_quizpass(
                bot,
                update.callback_query.message.message_id,
                update.callback_query.from_user.id,
                quizpass,
            )

    def callback_query_answer(
            self, bot: Bot, update: Update, answer: int) -> None:
        self.logger.info(
            "Callback query 'answer_%s' from %s",
            answer,
            self._log_user(update.callback_query.from_user))
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(
                session, update.callback_query.from_user.id)
            if not quizpass:
                return

            if not quizpass.current_item.is_answered:
                quizpass.current_item.set_answer(answer)
            session.commit()

            self._display_quizpass(
                bot,
                update.callback_query.message.message_id,
                update.callback_query.from_user.id,
                quizpass,
            )

            if quizpass.is_finished:
                if quizpass.has_passed:
                    bot.send_message(
                        chat_id=update.callback_query.from_user.id,
                        text=messages.PASSED.format(
                            result=quizpass.correct_given,
                            total=len(quizpass.quizitems),
                        ),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton(
                                "Share the result",
                                callback_data="share_result",
                            ),
                        ]]),
                    )
                    # May fail if the user is admin
                    bot.restrict_chat_member(
                        chat_id=self.config.GROUP_ID,
                        user_id=update.callback_query.from_user.id,
                        permissions=ChatPermissions(
                            can_send_message=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,
                            can_add_web_page_previews=True,
                            can_send_polls=True,
                        ),
                    )
                else:
                    bot.send_message(
                        chat_id=update.callback_query.from_user.id,
                        text=messages.FAILED.format(
                            result=quizpass.correct_given,
                            total=len(quizpass.quizitems),
                            required=quizpass.correct_required,
                            wait_hours=self.config.WAIT_HOURS_ON_FAIL,
                        ),
                        parse_mode="HTML",
                    )

    def callback_query_share_result(self, bot: Bot, update: Update) -> None:
        self.logger.info(
            "Callback query 'share_result' from %s",
            self._log_user(update.callback_query.from_user))
        bot.answer_callback_query(
            callback_query_id=update.callback_query.id,
        )

        with self.db_session() as session:
            quizpass = get_active_quizpass(
                session, update.callback_query.from_user.id)
            if not quizpass:
                return

            can_share = quizpass and \
                quizpass.is_finished and \
                quizpass.has_passed and\
                not quizpass.result_shared
            if not can_share:
                return

            bot.send_message(
                chat_id=self.config.GROUP_ID,
                text=messages.RESULT_SHARE.format(
                    user=self._display_user(
                        update.callback_query.from_user.id,
                        update.callback_query.from_user.first_name,
                    ),
                    result=quizpass.correct_given,
                    total=len(quizpass.quizitems),
                ),
                parse_mode="HTML",
            )

            quizpass.result_shared = True
            session.commit()

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

    def _on_start_quiz(
            self, session: Session, bot: Bot, user_id: int) -> bool:
        """
        Checks if user can start/restart quiz. If they can, returns True.
        If they can't sends appropriate message to the user and returns False.
        """
        quizpass = get_active_quizpass(session, user_id)
        if quizpass and quizpass.is_finished:
            if quizpass.has_passed:
                # User has passed.
                bot.send_message(
                    chat_id=user_id,
                    text=messages.PASSED.format(
                        result=quizpass.correct_given,
                        total=len(quizpass.quizitems),
                    ),
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "Share the result",
                            callback_data="share_result",
                        ),
                    ]]),
                )
                return False
            else:
                now = datetime.utcnow().replace(tzinfo=timezone.utc)

                # Time since last answer
                time_passed = now - quizpass.last_answer_at

                # Time user has to wait after fail
                time_has_to_pass = timedelta(
                    hours=self.config.WAIT_HOURS_ON_FAIL)

                # User failed and hasn't waited enough time.
                if time_passed < time_has_to_pass:
                    wait_seconds = (time_has_to_pass - time_passed)\
                        .total_seconds()
                    wait_hours = int(math.ceil(wait_seconds / 3600))
                    bot.send_message(
                        chat_id=user_id,
                        text=messages.FAILED.format(
                            result=quizpass.correct_given,
                            total=len(quizpass.quizitems),
                            required=quizpass.correct_required,
                            wait_hours=wait_hours,
                        ),
                        parse_mode="HTML")
                    return False

        return True

    def _display_quizpass(
                self,
                bot: Bot,
                message_id: int,
                user_id: int,
                quizpass: QuizPass,
            ) -> None:
        """
        Edits the given message to display current question in the given
        quizpass.
        """
        item = quizpass.current_item
        text = f"{item.text}\n\n"
        for option in item.options:
            text += f"{option.index}. {option.text}\n"

        if item.is_answered:
            text += "\n"
            if item.is_answered_correctly:
                text += "Correct.\n"
            else:
                text += "Wrong.\n"

        text = text.strip()

        ans_buttons = []
        for ix in range(len(item.options)):
            ans_buttons.append(InlineKeyboardButton(
                str(ix), callback_data=f"answer_{ix}",
            ))

        nav_buttons = [
            InlineKeyboardButton("<", callback_data="prev"),
            InlineKeyboardButton(
                f"{item.index + 1}/{self.config.QUESTIONS_PER_QUIZ}",
                callback_data="ignore",
            ),
            InlineKeyboardButton(">", callback_data="next"),
        ]

        if item.is_answered:
            keyboard = InlineKeyboardMarkup([
                nav_buttons,
            ])
        else:
            keyboard = InlineKeyboardMarkup([
                ans_buttons,
                nav_buttons,
            ])

        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
