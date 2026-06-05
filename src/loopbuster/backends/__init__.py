<<<<<<< HEAD
"""State backends for LoopBuster.

Provides MemoryBackend (default, in-process) and RedisBackend (distributed).
"""

from loopbuster.backends.base import MemoryBackend, RedisBackend, StateBackend

__all__ = ["StateBackend", "MemoryBackend", "RedisBackend"]
=======
"""State backends for distributed LoopBuster sessions.

Usage:
    from loopbuster.backends import MemoryBackend, AsyncRedisBackend

    backend = MemoryBackend()  # default, in-process
    backend = AsyncRedisBackend("redis://localhost")  # distributed
"""

from loopbuster.backends.base import AsyncRedisBackend, MemoryBackend, StateBackend

__all__ = ["StateBackend", "MemoryBackend", "AsyncRedisBackend"]
>>>>>>> codex/deep-detection-v0.3.0
