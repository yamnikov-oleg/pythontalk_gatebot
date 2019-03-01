class BaseConfig:
    # Bot token generated by the Bot Father.
    # The only required config var.
    BOT_TOKEN = None

    # Proxy URL for the bot's requests, if necessary.
    # E.g. 'socks5://127.0.0.1:9050'
    PROXY_URL = None

    # Database URL for SQLAlchemy
    SQLALCHEMY_URL = 'sqlite:///gatebot.db'

    # Path to the json file, containing questions and answers for the quizzes.
    QUESTIONS_FILE = 'questions.json'
