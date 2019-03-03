#!/usr/bin/env python3
import IPython

from gatebot.bot import GateBot
from config import Config

bot = GateBot(Config())
with bot.db_session() as session:
    IPython.embed()
