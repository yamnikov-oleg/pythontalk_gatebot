from pytest import fixture

from config import TestConfig
from gatebot.bot import GateBot


@fixture
def gatebot():
    return GateBot(TestConfig())
