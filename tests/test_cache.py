import asyncio


class TestCacheImage:
    async def test_initial_value_is_none(self):
        from nonebot_plugin_apod.config import get_cache_image, clear_cache_image

        await clear_cache_image()
        assert await get_cache_image() is None

    async def test_set_then_get(self):
        from nonebot_plugin_apod.config import (
            clear_cache_image,
            get_cache_image,
            set_cache_image,
        )

        data = b"fake_image_bytes"
        await set_cache_image(data)
        assert await get_cache_image() == data
        await clear_cache_image()

    async def test_clear(self):
        from nonebot_plugin_apod.config import (
            clear_cache_image,
            get_cache_image,
            set_cache_image,
        )

        await set_cache_image(b"data")
        await clear_cache_image()
        assert await get_cache_image() is None

    async def test_overwrite(self):
        from nonebot_plugin_apod.config import (
            clear_cache_image,
            get_cache_image,
            set_cache_image,
        )

        await set_cache_image(b"first")
        await set_cache_image(b"second")
        assert await get_cache_image() == b"second"
        await clear_cache_image()

    async def test_get_cache_image_with_generator_singleflight(self):
        from nonebot_plugin_apod.config import (
            clear_cache_image,
            get_cache_image,
        )

        await clear_cache_image()
        call_count = 0

        async def mock_generator() -> bytes:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return b"generated_bytes"

        results = await asyncio.gather(
            *(get_cache_image(mock_generator) for _ in range(5))
        )

        assert call_count == 1
        assert results == [b"generated_bytes"] * 5
        # 验证已写入缓存
        assert await get_cache_image() == b"generated_bytes"
        await clear_cache_image()

    async def test_get_cache_image_hit_cache_skips_generator(self):
        from nonebot_plugin_apod.config import (
            clear_cache_image,
            get_cache_image,
            set_cache_image,
        )

        await clear_cache_image()
        await set_cache_image(b"existing_cache")

        called = False

        async def mock_generator() -> bytes:
            nonlocal called
            called = True
            return b"new_bytes"

        result = await get_cache_image(mock_generator)
        assert result == b"existing_cache"
        assert called is False
        await clear_cache_image()

    async def test_get_cache_image_generator_returns_none(self):
        from nonebot_plugin_apod.config import (
            clear_cache_image,
            get_cache_image,
        )

        await clear_cache_image()

        async def mock_generator() -> None:
            return None

        result = await get_cache_image(mock_generator)
        assert result is None
        assert await get_cache_image() is None
        await clear_cache_image()
