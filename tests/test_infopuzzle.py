from unittest.mock import AsyncMock, patch


SAMPLE_APOD = {
    "title": "Test Nebula",
    "explanation": "A beautiful nebula in space.",
    "url": "https://apod.nasa.gov/image.jpg",
    "date": "2023-10-01",
}


class TestApodJsonToMd:
    async def test_html_escape(self):
        from nonebot_plugin_apod.infopuzzle import apod_json_to_md

        data = {
            **SAMPLE_APOD,
            "title": "<script>alert('xss')</script>",
            "copyright": "A & B <Corp>",
        }
        with patch(
            "nonebot_plugin_apod.infopuzzle.translate_text_auto",
            new_callable=AsyncMock,
            return_value="translated text",
        ):
            result = await apod_json_to_md(data)
            assert "&lt;script&gt;" in result
            assert "<script>" not in result
            assert "A &amp; B &lt;Corp&gt;" in result

    async def test_copyright_default(self):
        from nonebot_plugin_apod.infopuzzle import apod_json_to_md

        data = {**SAMPLE_APOD}
        with patch(
            "nonebot_plugin_apod.infopuzzle.translate_text_auto",
            new_callable=AsyncMock,
            return_value="translated",
        ):
            result = await apod_json_to_md(data)
            assert "无" in result

    async def test_contains_all_fields(self):
        from nonebot_plugin_apod.infopuzzle import apod_json_to_md

        data = {**SAMPLE_APOD, "copyright": "NASA"}
        with patch(
            "nonebot_plugin_apod.infopuzzle.translate_text_auto",
            new_callable=AsyncMock,
            return_value="一个美丽的星云",
        ):
            result = await apod_json_to_md(data)
            assert "Test Nebula" in result
            assert "2023-10-01" in result
            assert "https://apod.nasa.gov/image.jpg" in result
            assert "一个美丽的星云" in result
            assert "NASA" in result
