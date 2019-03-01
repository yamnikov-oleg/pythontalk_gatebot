import telegram
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()


def init_models(engine):
    # TODO: Is this necessary? Check later. I would like to avoid
    # any global state in the project.
    Base.metadata.bind = engine
