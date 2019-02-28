import logging

from telegram import Bot
from telegram.ext import Updater, MessageHandler, Filters
from telegram.update import Update
from telegram.utils.request import Request

from config.base import BaseConfig


logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s : %(name)s : %(levelname)s] %(message)s',
)


class GateBot:
    def __init__(self, config: BaseConfig) -> None:
        self.config = config

        self.logger = logging.getLogger('gatebot')
        self.updater = self._init_updater()

    def _init_updater(self) -> Updater:
        if self.config.PROXY:
            request = Request(con_pool_size=8, proxy_url=self.config.PROXY)
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

        return updater

    def run(self) -> None:
        self.logger.info("GateBot started")
        self.updater.start_polling()

    def new_chat_members(self, bot: Bot, update: Update) -> None:
        self.logger.info("New status update")
        bot.restrict_chat_member(
            chat_id=update.message.chat.id,
            user_id=update.message.new_chat_members[0].id,
            can_send_message=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )
