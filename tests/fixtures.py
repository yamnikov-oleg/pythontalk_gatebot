from pytest import fixture

from config import TestConfig
from gatebot.bot import GateBot
from gatebot.models import Base


@fixture
def gatebot():
    bot = GateBot(TestConfig())
    Base.metadata.create_all()
    return bot
