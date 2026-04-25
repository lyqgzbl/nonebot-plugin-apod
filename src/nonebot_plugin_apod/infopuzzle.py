import json
from io import BytesIO

import aiofiles
from PIL import Image, ImageDraw, ImageFont
from nonebot.log import logger
from nonebot import get_driver
import nonebot_plugin_localstore as store

from .config import plugin_config
from .utils import ensure_apod_data, translate_text_auto, get_httpx_client


FontLike = ImageFont.FreeTypeFont | ImageFont.ImageFont
SCALE = 2
CANVAS_WIDTH = 600 * SCALE
PADDING = 35 * SCALE
CARD_PADDING = 20 * SCALE
CONTENT_WIDTH = CANVAS_WIDTH - 2 * PADDING - 2 * CARD_PADDING
SPACING = 20 * SCALE
CORNER_RADIUS = 8 * SCALE

FONT_BASE_URL = (
    "https://raw.githubusercontent.com/"
    "TCOTC/siyuan-ttf-HarmonyOS_Sans_SC-and-Twemoji/"
    "main/HarmonyOS_Sans_Backup/HarmonyOS_SansSC/"
)
FONTS = {
    "regular": "HarmonyOS_SansSC_Regular.ttf",
    "bold": "HarmonyOS_SansSC_Bold.ttf",
}

data_dir = store.get_plugin_data_dir()
apod_cache_json = store.get_plugin_cache_file("apod.json")
dark_mode = plugin_config.apod_infopuzzle_dark_mode

THEMES = {
    False: {
        "bg": (244, 244, 244),
        "card_bg": (255, 255, 255),
        "title_color": (51, 51, 51),
        "text_color": (51, 51, 51),
        "info_color": (85, 85, 85),
    },
    True: {
        "bg": (30, 30, 30),
        "card_bg": (44, 44, 44),
        "title_color": (224, 224, 224),
        "text_color": (224, 224, 224),
        "info_color": (160, 160, 160),
    },
}

driver = get_driver()


@driver.on_startup
async def _download_fonts():
    client = get_httpx_client()
    for name, filename in FONTS.items():
        path = data_dir / filename
        if path.exists():
            continue
        url = FONT_BASE_URL + filename
        logger.info(f"正在下载 HarmonyOS Sans SC {name}...")
        try:
            resp = await client.get(url, timeout=60)
            resp.raise_for_status()
            async with aiofiles.open(path, "wb") as f:
                await f.write(resp.content)
            logger.info(f"HarmonyOS Sans SC {name} 下载完成")
        except Exception as e:
            logger.warning(f"下载 HarmonyOS Sans SC {name} 失败: {e}")


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | None:
    key = "bold" if bold else "regular"
    path = data_dir / FONTS[key]
    if path.exists():
        return ImageFont.truetype(str(path), size)
    if bold:
        regular = data_dir / FONTS["regular"]
        if regular.exists():
            return ImageFont.truetype(str(regular), size)
    return None


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: FontLike,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for char in paragraph:
            test = line + char
            if draw.textlength(test, font=font) > max_width:
                if line:
                    lines.append(line)
                line = char
            else:
                line = test
        if line:
            lines.append(line)
    return lines


def _draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: FontLike,
    y: int,
    canvas_width: int,
    fill: tuple[int, int, int],
    line_spacing: int,
) -> int:
    for line in lines:
        tw = draw.textlength(line, font=font)
        draw.text(((canvas_width - tw) / 2, y), line, fill=fill, font=font)
        y += _line_height(draw, font) + line_spacing
    return y


def _line_height(draw: ImageDraw.ImageDraw, font: FontLike) -> int:
    return int(draw.textbbox((0, 0), "测试Tg", font=font)[3])


def _round_corners(img: Image.Image, radius: int) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, *img.size), radius=radius, fill=255)
    img.putalpha(mask)
    return img


async def _fetch_image(url: str) -> Image.Image | None:
    try:
        client = get_httpx_client()
        resp = await client.get(url, timeout=20)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"下载天文图片失败: {e}")
        return None


async def generate_apod_image() -> bytes | None:
    try:
        if not await ensure_apod_data():
            return None

        font_title = _load_font(28 * SCALE, bold=True)
        if font_title is None:
            logger.warning("缺少字体文件, 已降级为单图模式")
            return None
        font_subtitle = _load_font(26 * SCALE, bold=True)
        font_body = _load_font(20 * SCALE)
        font_info = _load_font(14 * SCALE)
        if font_subtitle is None or font_body is None or font_info is None:
            logger.warning("缺少字体文件, 已降级为单图模式")
            return None

        async with aiofiles.open(apod_cache_json, encoding="utf-8") as f:
            data = json.loads(await f.read())

        theme = THEMES[dark_mode]
        title_text = "今日天文一图"
        subtitle_text = data["title"]
        explanation = await translate_text_auto(data["explanation"])
        copyright_text = f"版权：{data.get('copyright', '无')}"
        date_text = f"日期：{data['date']}"
        image_url = data.get("url")

        tmp = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(tmp)

        title_lines = _wrap_text(draw, title_text, font_title, CONTENT_WIDTH)
        subtitle_lines = _wrap_text(draw, subtitle_text, font_subtitle, CONTENT_WIDTH)
        body_lines = _wrap_text(draw, explanation, font_body, CONTENT_WIDTH)

        title_lh = _line_height(draw, font_title)
        subtitle_lh = _line_height(draw, font_subtitle)
        body_lh = _line_height(draw, font_body)
        info_lh = _line_height(draw, font_info)

        apod_img = await _fetch_image(image_url) if image_url else None
        img_height = 0
        if apod_img:
            ratio = CONTENT_WIDTH / apod_img.width
            img_height = int(apod_img.height * ratio)
            apod_img = apod_img.resize(
                (CONTENT_WIDTH, img_height), Image.Resampling.LANCZOS
            )
            apod_img = _round_corners(apod_img, CORNER_RADIUS)

        card_content_h = (
            25 * SCALE
            + len(title_lines) * (title_lh + 4 * SCALE)
            + 25 * SCALE
            + len(subtitle_lines) * (subtitle_lh + 4 * SCALE)
            + 20 * SCALE
            + (img_height + SPACING if apod_img else 0)
            + len(body_lines) * (body_lh + 6 * SCALE)
            + 15 * SCALE
            + info_lh + 5 * SCALE
            + info_lh
        )
        card_height = 2 * CARD_PADDING + card_content_h
        canvas_height = 2 * PADDING + card_height

        canvas = Image.new("RGBA", (CANVAS_WIDTH, canvas_height), theme["bg"])
        draw = ImageDraw.Draw(canvas)

        card_x = PADDING
        card_y = PADDING
        draw.rounded_rectangle(
            [card_x, card_y, CANVAS_WIDTH - PADDING, card_y + card_height],
            radius=CORNER_RADIUS,
            fill=theme["card_bg"],
        )

        y = card_y + CARD_PADDING
        y += 25 * SCALE
        y = _draw_centered_lines(
            draw,
            title_lines,
            font_title,
            y,
            CANVAS_WIDTH,
            theme["title_color"],
            4 * SCALE,
        )
        y += 25 * SCALE

        y = _draw_centered_lines(
            draw,
            subtitle_lines,
            font_subtitle,
            y,
            CANVAS_WIDTH,
            theme["title_color"],
            4 * SCALE,
        )
        y += 20 * SCALE

        content_x = card_x + CARD_PADDING
        if apod_img:
            canvas.paste(apod_img, (content_x, y), apod_img)
            y += img_height + SPACING

        for line in body_lines:
            draw.text(
                (content_x, y),
                line,
                fill=theme["text_color"],
                font=font_body,
            )
            y += body_lh + 6 * SCALE
        y += 15 * SCALE

        draw.text(
            (content_x, y),
            copyright_text,
            fill=theme["info_color"],
            font=font_info,
        )
        y += info_lh + 5 * SCALE
        draw.text(
            (content_x, y),
            date_text,
            fill=theme["info_color"],
            font=font_info,
        )

        output = canvas.convert("RGB")
        buf = BytesIO()
        output.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.error(f"生成 NASA APOD 图片时发生错误：{e}")
        return None
