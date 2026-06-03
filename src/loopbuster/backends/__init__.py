"""State backends for distributed LoopBuster sessions.

Usage:
    from loopbuster.backends import MemoryBackend, AsyncRedisBackend

    backend = MemoryBackend()  # default, in-process
    backend = AsyncRedisBackend("redis://localhost")  # distributed
"""

from loopbuster.backends.base import AsyncRedisBackend, MemoryBackend, StateBackend

__all__ = ["StateBackend", "MemoryBackend", "AsyncRedisBackend"]
