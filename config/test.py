from .base import BaseConfig


class TestConfig(BaseConfig):
    BOT_TOKEN = '000000000:testtoken'
    GROUP_ID = -12341
    SQLALCHEMY_URL = 'sqlite:///:memory:'
