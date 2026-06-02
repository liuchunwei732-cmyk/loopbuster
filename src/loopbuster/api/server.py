from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os
import json
import redis
from loopbuster.storage.redis import RedisBackend

app = FastAPI(title="LoopBuster Dashboard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 依赖注入，复用 RedisBackend
def get_redis_backend():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        return RedisBackend(redis_url=redis_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis connection failed: {e}")

@app.get("/api/stats")
async def get_stats(backend: RedisBackend = Depends(get_redis_backend)):
    client = backend.client
    try:
        # 获取所有的 state key
        state_keys = client.keys("loopbuster:state:*")
        actions_keys = client.keys("loopbuster:actions:*")

        total_sessions = len(state_keys)
        total_actions = 0
        loop_blocks = 0

        # 统计 actions
        for key in actions_keys:
            total_actions += client.llen(key)
            # 解析拦截信息, 简单统计一下 blocked 或 error 等标记
            actions = client.lrange(key, 0, -1)
            for action_str in actions:
                try:
                    action = json.loads(action_str)
                    # 假设这里基于某种标识符判断是否被拦截，例如 status='blocked' 或存在 'loop_detected' 
                    if action.get("status") == "blocked" or action.get("loop_detected") or action.get("action") == "block":
                        loop_blocks += 1
                except json.JSONDecodeError:
                    continue

        return {
            "total_sessions": total_sessions,
            "total_actions": total_actions,
            "loop_blocks": loop_blocks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
async def get_logs(
    backend: RedisBackend = Depends(get_redis_backend),
    limit: int = Query(50, description="Maximum number of logs to return"),
    session_id: Optional[str] = Query(None, description="Filter by session ID")
):
    client = backend.client
    try:
        logs = []
        if session_id:
            keys = [f"loopbuster:actions:{session_id}"]
        else:
            keys = client.keys("loopbuster:actions:*")
        
        for key in keys:
            sess_id = key.decode("utf-8").split(":")[-1] if isinstance(key, bytes) else key.split(":")[-1]
            # 获取最新的记录
            actions_raw = client.lrange(key, -limit, -1)
            for raw in actions_raw:
                try:
                    action = json.loads(raw)
                    action["session_id"] = sess_id
                    logs.append(action)
                except json.JSONDecodeError:
                    continue
        
        # 简单排序，如果日志里有 timestamp 就按时间排，否则按返回顺序
        logs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return logs[:limit]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
