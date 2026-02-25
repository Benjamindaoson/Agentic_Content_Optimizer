"""
Initialize database tables.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import init_db


async def main():
    print("Initializing database tables...")
    try:
        await init_db()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
