import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class SingleFlight(Generic[T]):
    def __init__(self) -> None:
        self._calls: dict[Any, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def do(self, key: Any, fn: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            if key in self._calls:
                fut = self._calls[key]
                is_leader = False
            else:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                self._calls[key] = fut
                is_leader = True

        if not is_leader:
            return await asyncio.shield(fut)

        try:
            res = await fn()
            if not fut.done():
                fut.set_result(res)
            return res
        except BaseException as e:
            if not fut.done():
                fut.set_exception(e)
            raise
        finally:
            async with self._lock:
                self._calls.pop(key, None)
