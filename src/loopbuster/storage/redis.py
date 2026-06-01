"""
RedisBackend for LoopBuster
Supports distributed agent state management.
"""
import json

class RedisBackend:
    def __init__(self, redis_client=None, redis_url=None):
        if redis_client:
            self.client = redis_client
        elif redis_url:
            import redis
            self.client = redis.Redis.from_url(redis_url)
        else:
            raise ValueError("Either redis_client or redis_url must be provided")

    def save_state(self, session_id: str, state_data: dict):
        self.client.set(f"loopbuster:state:{session_id}", json.dumps(state_data))

    def get_state(self, session_id: str) -> dict:
        data = self.client.get(f"loopbuster:state:{session_id}")
        return json.loads(data) if data else None

    def append_action(self, session_id: str, action: dict):
        self.client.rpush(f"loopbuster:actions:{session_id}", json.dumps(action))

    def get_actions(self, session_id: str) -> list:
        data = self.client.lrange(f"loopbuster:actions:{session_id}", 0, -1)
        return [json.loads(item) for item in data]
