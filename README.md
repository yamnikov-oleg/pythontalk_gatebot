# Python Talk Gate Bot

Telegram bot used for @python_talk group to quiz new members on basic Python knowledge before letting them chat.

## Installation

The bot requires Python of version 3.6 or higher.

1. Create a virtual environment and activate it:
   ```
   $ virtualenv -p python3 venv
   $ source ./venv/bin/activate
   ```
2. Install all the requirements:
   ```
   $ pip install -r requirements.txt
   ```
3. Configure the bot accordingly (see "Configuration" section).
4. Apply migrations:
   ```
   $ alembic upgrade head
   ```
5. Run the bot:
   ```
   $ ./run.py
   ```

## Configuration

Bot's configuration is located in the `config` directory:

* `base.py` - default configuration.
* `test.py` - test configuration, used when running tests.

Please, do not edit these files, unless you're developing the bot.

To configure the bot on deployment, create a new file `local.py` in this directory with the following contents:

```python
from .base import BaseConfig


class LocalConfig(BaseConfig):
    BOT_TOKEN = ''
```

Fill in `BOT_TOKEN` variable. You can overwrite any other variable available in `base.BaseConfig` if needed.

`local.py` is already included in `.gitignore`.

## Development commands

* Run tests:
  ```
  $ pytest
  ```
* Auto-generate a new migration:
  ```
  $ alembic revision --autogenerate -m "You migration message"
  ```
  Make sure you have the latest version of DB schema before generating new migrations.
* Run IPython shell with DB session and bot models in scope:
  ```
  $ ./shell.py
  ```
