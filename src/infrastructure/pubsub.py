import sys

from broadcaster import Broadcast

from config import settings

url = settings.DATABASE_URL.replace("+asyncpg", "")
if "sqlite" in url or "pytest" in sys.modules:
    url = "memory://"
broadcast = Broadcast(url)
