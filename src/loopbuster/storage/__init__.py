"""Storage backends for LoopBuster session persistence.

The sync RedisBackend is used by the FastAPI dashboard server.
For async distributed usage, see loopbuster.backends.AsyncRedisBackend.
"""

from loopbuster.storage.redis import RedisBackend

__all__ = ["RedisBackend"]
