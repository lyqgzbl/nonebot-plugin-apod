import json
from unittest.mock import patch, AsyncMock

SAMPLE_APOD = {
    "title": "Test Nebula",
    "explanation": "A beautiful nebula in space.",
    "url": "https://apod.nasa.gov/image.jpg",
    "date": "2023-10-01",
}


def _get_infopuzzle():
    import nonebot_plugin_apod.infopuzzle as infopuzzle

    return infopuzzle


class TestApodJsonToMd:
    async def test_html_escape(self):
        infopuzzle = _get_infopuzzle()
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
            result = await infopuzzle.apod_json_to_md(data)
            assert "&lt;script&gt;" in result
            assert "<script>" not in result
            assert "A &amp; B &lt;Corp&gt;" in result

    async def test_copyright_default(self):
        infopuzzle = _get_infopuzzle()
        data = {**SAMPLE_APOD}
        with patch(
            "nonebot_plugin_apod.infopuzzle.translate_text_auto",
            new_callable=AsyncMock,
            return_value="translated",
        ):
            result = await infopuzzle.apod_json_to_md(data)
            assert "无" in result

    async def test_contains_all_fields(self):
        infopuzzle = _get_infopuzzle()
        data = {**SAMPLE_APOD, "copyright": "NASA"}
        with patch(
            "nonebot_plugin_apod.infopuzzle.translate_text_auto",
            new_callable=AsyncMock,
            return_value="一个美丽的星云",
        ):
            result = await infopuzzle.apod_json_to_md(data)
            assert "Test Nebula" in result
            assert "2023-10-01" in result
            assert "https://apod.nasa.gov/image.jpg" in result
            assert "一个美丽的星云" in result
            assert "NASA" in result


class TestGenerateApodImage:
    async def test_returns_bytes_on_success(self, tmp_path, monkeypatch):
        infopuzzle = _get_infopuzzle()
        cache_file = tmp_path / "apod.json"
        cache_file.write_text(json.dumps(SAMPLE_APOD))

        monkeypatch.setattr(infopuzzle, "apod_cache_json", cache_file)

        with (
            patch.object(
                infopuzzle,
                "ensure_apod_data",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "nonebot_plugin_apod.infopuzzle.md_to_pic",
                new_callable=AsyncMock,
                return_value=b"fake_png_bytes",
            ),
            patch(
                "nonebot_plugin_apod.infopuzzle.translate_text_auto",
                new_callable=AsyncMock,
                return_value="translated",
            ),
        ):
            res = await infopuzzle.generate_apod_image()
            assert res == b"fake_png_bytes"
