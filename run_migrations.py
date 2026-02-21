import asyncio
import sys
from alembic.config import main

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    main(["upgrade", "head"])
