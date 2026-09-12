import asyncio
import pytest


def _get_singleflight():
    from nonebot_plugin_apod.singleflight import SingleFlight

    return SingleFlight


class TestSingleFlight:
    async def test_concurrent_dedup(self):
        SingleFlight = _get_singleflight()
        sf = SingleFlight[str]()
        call_count = 0

        async def slow_work() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return "done"

        results = await asyncio.gather(*(sf.do("key1", slow_work) for _ in range(5)))

        assert call_count == 1
        assert results == ["done"] * 5

    async def test_different_keys(self):
        SingleFlight = _get_singleflight()
        sf = SingleFlight[str]()
        calls: dict[str, int] = {"k1": 0, "k2": 0}

        async def work(k: str) -> str:
            calls[k] += 1
            await asyncio.sleep(0.02)
            return f"result_{k}"

        r1, r2 = await asyncio.gather(
            sf.do("k1", lambda: work("k1")),
            sf.do("k2", lambda: work("k2")),
        )

        assert calls["k1"] == 1
        assert calls["k2"] == 1
        assert r1 == "result_k1"
        assert r2 == "result_k2"

    async def test_exception_broadcast(self):
        SingleFlight = _get_singleflight()
        sf = SingleFlight[str]()
        call_count = 0

        async def failing_work() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.02)
            raise ValueError("custom error")

        results = await asyncio.gather(
            *(sf.do("fail_key", failing_work) for _ in range(3)),
            return_exceptions=True,
        )

        assert call_count == 1
        for res in results:
            assert isinstance(res, ValueError)
            assert str(res) == "custom error"

        async def success_work() -> str:
            return "recovered"

        assert await sf.do("fail_key", success_work) == "recovered"

    async def test_cancellation_shield(self):
        SingleFlight = _get_singleflight()
        sf = SingleFlight[str]()
        leader_finished = False

        async def long_running() -> str:
            nonlocal leader_finished
            await asyncio.sleep(0.1)
            leader_finished = True
            return "finished"

        leader_task = asyncio.create_task(sf.do("shield_key", long_running))
        await asyncio.sleep(0.01)

        follower_task = asyncio.create_task(sf.do("shield_key", long_running))
        await asyncio.sleep(0.01)
        follower_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await follower_task

        leader_result = await leader_task
        assert leader_result == "finished"
        assert leader_finished is True
