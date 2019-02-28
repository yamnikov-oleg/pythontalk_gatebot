#!/usr/bin/env python3
from config import Config
from gatebot.bot import GateBot

if __name__ == "__main__":
    gatebot = GateBot(Config())
    gatebot.run()
