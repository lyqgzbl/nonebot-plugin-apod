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
