"""Entry point: `python main.py` (configure via GRIDBOT_* env vars)."""

import logging

from gridbot.bot import Bot
from gridbot.config import Config


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    Bot(Config()).run_forever()


if __name__ == "__main__":
    main()
