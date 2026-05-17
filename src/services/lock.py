from fastapi import Request
import os
import redis
from src.service import LeaveError

class LockAcquireException(LeaveError):
    def __init__(self, message: str, status_code: int = 425):
        # Default to 425 to match your API requirement
        self.message = message
        super().__init__(message, status_code)

class LockService:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)

    def acquire_lock_or_fail(self, lock_name: str, expire_seconds: int = 5):
        """
        Attempts to acquire a lock instantly.
        If it exists, it raises an error. If not, it sets it and does nothing else.
        """
        
        lock_key = f"lock:{lock_name}"
        
        acquired = self.redis_client.set(lock_key, "locked", ex=expire_seconds, nx=True)
        
        if not acquired:
            raise LockAcquireException(
                message="Request is currently being processed, please try again later",
                status_code=425
            )
        print(f"Lock {lock_key} acquired")

    def release_lock(self, lock_name: str):
        lock_key = f"lock:{lock_name}"
        self.redis_client.delete(lock_key)
        print(f"Lock {lock_key} released")


    def acquire_and_track(self, request: Request, lock_key: str, expire_seconds: int = 5):
        """New method: Call this when an HTTP request is present to ensure safe cleanup."""
        # 1. Try to get the lock FIRST. If it fails, it exits here safely without touching state.
        print("555555555555555 try lock_key: ", lock_key)
        self.acquire_lock_or_fail(lock_key, expire_seconds)

        # 2. Only register for middleware cleanup if we actually won the lock!
        if not hasattr(request.state, "acquired_locks"):
            request.state.acquired_locks = []
        request.state.acquired_locks.append(lock_key)