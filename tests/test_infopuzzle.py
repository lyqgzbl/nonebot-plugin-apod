from unittest.mock import patch, AsyncMock
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def _get_infopuzzle():
    import nonebot_plugin_apod.infopuzzle as infopuzzle

    return infopuzzle


class TestWrapText:
    def test_chinese_wrap(self):
        infopuzzle = _get_infopuzzle()
        img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default(16)
        text = "这是一段很长的中文文本用于测试自动换行功能是否正常工作"
        lines = infopuzzle._wrap_text(draw, text, font, max_width=100)
        assert len(lines) > 1
        assert "".join(lines) == text

    def test_preserves_newline(self):
        infopuzzle = _get_infopuzzle()
        img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default(16)
        text = "第一行\n第二行"
        lines = infopuzzle._wrap_text(draw, text, font, max_width=500)
        assert len(lines) == 2
        assert lines[0] == "第一行"
        assert lines[1] == "第二行"

    def test_empty_string(self):
        infopuzzle = _get_infopuzzle()
        img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default(16)
        lines = infopuzzle._wrap_text(draw, "", font, max_width=500)
        assert lines == [""]

    def test_single_char_per_line(self):
        infopuzzle = _get_infopuzzle()
        img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default(16)
        lines = infopuzzle._wrap_text(draw, "ABC", font, max_width=1)
        assert len(lines) == 3


class TestLoadFont:
    def test_missing_font_returns_none(self, tmp_path, monkeypatch):
        infopuzzle = _get_infopuzzle()
        monkeypatch.setattr(infopuzzle, "data_dir", tmp_path)
        result = infopuzzle._load_font(16)
        assert result is None

    def test_missing_bold_falls_back_to_regular(self, tmp_path, monkeypatch):
        infopuzzle = _get_infopuzzle()
        # copy a real font structure: only regular exists
        monkeypatch.setattr(infopuzzle, "data_dir", tmp_path)
        # no font files -> returns None
        result = infopuzzle._load_font(16, bold=True)
        assert result is None


class TestRoundCorners:
    def test_output_is_rgba(self):
        infopuzzle = _get_infopuzzle()
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        result = infopuzzle._round_corners(img, 10)
        assert result.mode == "RGBA"
        assert result.size == (100, 100)

    def test_corner_pixel_transparent(self):
        infopuzzle = _get_infopuzzle()
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        result = infopuzzle._round_corners(img, 20)
        # top-left corner should be transparent
        pixel = result.getpixel((0, 0))
        assert isinstance(pixel, tuple)
        assert pixel[3] == 0


class TestGenerateApodImage:
    async def test_returns_none_without_font(self, tmp_path, monkeypatch):
        infopuzzle = _get_infopuzzle()
        monkeypatch.setattr(infopuzzle, "data_dir", tmp_path)
        with patch.object(
            infopuzzle,
            "ensure_apod_data",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await infopuzzle.generate_apod_image()
            assert result is None

    async def test_returns_png_bytes(self, tmp_path, monkeypatch):
        infopuzzle = _get_infopuzzle()

        monkeypatch.setattr(
            infopuzzle,
            "_load_font",
            lambda size, bold=False: ImageFont.load_default(size),
        )

        monkeypatch.setattr(
            infopuzzle,
            "ensure_apod_data",
            AsyncMock(return_value=True),
        )

        cache_file = tmp_path / "apod.json"
        import json

        cache_file.write_text(
            json.dumps(
                {
                    "title": "Test Nebula",
                    "explanation": "A beautiful nebula.",
                    "url": "https://example.com/img.jpg",
                    "date": "2023-10-01",
                    "media_type": "image",
                }
            )
        )
        monkeypatch.setattr(infopuzzle, "apod_cache_json", cache_file)

        monkeypatch.setattr(
            infopuzzle,
            "translate_text_auto",
            AsyncMock(return_value="A beautiful nebula."),
        )

        small_img = Image.new("RGB", (100, 80), (0, 0, 255))
        monkeypatch.setattr(
            infopuzzle,
            "_fetch_image",
            AsyncMock(return_value=small_img),
        )

        result = await infopuzzle.generate_apod_image()
        assert result is not None
        assert isinstance(result, bytes)
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

        img = Image.open(BytesIO(result))
        assert img.format == "PNG"
        assert img.width == 1200
