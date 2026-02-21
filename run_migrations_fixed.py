import asyncio
import sys
from alembic import command
from alembic.config import Config


def _fix_windows_event_loop():
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )


def main():
    _fix_windows_event_loop()

    cfg = Config("alembic.ini")
    print("INFO Running alembic upgrade head ...")
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    main()
