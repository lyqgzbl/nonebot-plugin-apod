import asyncio
from unittest.mock import patch


def _get_utils():
    import nonebot_plugin_apod.utils as utils

    return utils


class TestTranslateTextAuto:
    async def test_no_translator_returns_original(self):
        utils = _get_utils()
        with (
            patch.object(utils, "qwen_trans", False),
            patch.object(utils, "deepl_trans", False),
            patch.object(utils, "baidu_trans", False),
        ):
            result = await utils.translate_text_auto("hello world")
            assert result == "hello world"

    async def test_timeout_returns_original(self):
        utils = _get_utils()

        async def slow_translate(text):
            await asyncio.sleep(10)
            return "translated"

        with (
            patch.object(utils, "qwen_trans", True),
            patch.object(utils, "qwen_translate_text", slow_translate),
        ):
            result = await utils.translate_text_auto("hello", timeout=0)
            assert result == "hello"

    async def test_exception_returns_original(self):
        utils = _get_utils()

        async def failing_translate(text):
            raise RuntimeError("API error")

        with (
            patch.object(utils, "qwen_trans", True),
            patch.object(utils, "qwen_translate_text", failing_translate),
        ):
            result = await utils.translate_text_auto("hello world")
            assert result == "hello world"
            assert "Exception" not in result

    async def test_success_returns_translated(self):
        utils = _get_utils()

        async def mock_translate(text):
            return "你好世界"

        with (
            patch.object(utils, "qwen_trans", True),
            patch.object(utils, "qwen_translate_text", mock_translate),
        ):
            result = await utils.translate_text_auto("hello world")
            assert result == "你好世界"
