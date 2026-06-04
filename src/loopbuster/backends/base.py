"""State backends for LoopBuster.

MemoryBackend — default in-process storage (no dependencies).
RedisBackend — distributed storage via Redis (requires `pip install loopbuster[redis]`).
"""

from __future__ import annotations

import json
from typing import Any


class StateBackend:
    """Base class for state backends."""

    async def get_history(self, session_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def append_history(self, session_id: str, entry: dict[str, Any]) -> None:
        raise NotImplementedError

    async def get_metadata(self, session_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def set_metadata(self, session_id: str, metadata: dict[str, Any]) -> None:
        raise NotImplementedError


class MemoryBackend(StateBackend):
    """In-memory state backend (default, no dependencies)."""

    def __init__(self) -> None:
        self._histories: dict[str, list[dict[str, Any]]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    async def get_history(self, session_id: str) -> list[dict[str, Any]]:
        return self._histories.get(session_id, [])

    async def append_history(self, session_id: str, entry: dict[str, Any]) -> None:
        if session_id not in self._histories:
            self._histories[session_id] = []
        self._histories[session_id].append(entry)

    async def get_metadata(self, session_id: str) -> dict[str, Any]:
        return self._metadata.get(session_id, {})

    async def set_metadata(self, session_id: str, metadata: dict[str, Any]) -> None:
        self._metadata[session_id] = metadata


class RedisBackend(StateBackend):
    """Redis-based state backend for distributed environments.

    Requires: pip install loopbuster[redis]
    """

    def __init__(self, redis_url: str = "redis://localhost", prefix: str = "loopbuster:") -> None:
        try:
            from redis.asyncio import Redis as AsyncRedis
        except ImportError:
            raise ImportError(
                "redis package is required for RedisBackend. "
                "Install it with: pip install loopbuster[redis]"
            )
        self.redis = AsyncRedis.from_url(redis_url, decode_responses=True)
        self.prefix = prefix

    def _hist_key(self, session_id: str) -> str:
        return f"{self.prefix}hist:{session_id}"

    def _meta_key(self, session_id: str) -> str:
        return f"{self.prefix}meta:{session_id}"

    async def get_history(self, session_id: str) -> list[dict[str, Any]]:
        data = await self.redis.lrange(self._hist_key(session_id), 0, -1)
        return [json.loads(item) for item in data] if data else []

    async def append_history(self, session_id: str, entry: dict[str, Any]) -> None:
        await self.redis.rpush(self._hist_key(session_id), json.dumps(entry))
        await self.redis.expire(self._hist_key(session_id), 86400)  # 24 hours

    async def get_metadata(self, session_id: str) -> dict[str, Any]:
        data = await self.redis.get(self._meta_key(session_id))
        return json.loads(data) if data else {}

    async def set_metadata(self, session_id: str, metadata: dict[str, Any]) -> None:
        await self.redis.set(self._meta_key(session_id), json.dumps(metadata), ex=86400)
