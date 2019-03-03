#!/usr/bin/env python3
import IPython

from gatebot.bot import GateBot
from gatebot.models import *  # noqa: F401, F403
from config import Config

bot = GateBot(Config())
with bot.db_session() as session:
    IPython.embed()
