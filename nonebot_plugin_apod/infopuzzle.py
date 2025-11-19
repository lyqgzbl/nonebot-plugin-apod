import json
from pathlib import Path

from nonebot.log import logger
from nonebot import get_plugin_config
import nonebot_plugin_localstore as store
from nonebot_plugin_htmlrender import md_to_pic

from .config import Config
from .utils import deepl_translate_text, baidu_translate_text, fetch_apod_data

plugin_config = get_plugin_config(Config)
baidu_trans = plugin_config.apod_baidu_trans
deepl_trans = plugin_config.apod_deepl_trans
infopuzzle_mode = plugin_config.apod_infopuzzle_dark_mode
apod_cache_json = store.get_plugin_cache_file("apod.json")


async def apod_json_to_md(apod_json):
    title = apod_json["title"]
    explanation = apod_json["explanation"]
    url = apod_json["url"]
    copyright = apod_json.get("copyright", "无")
    date = apod_json["date"]
    if deepl_trans:
        explanation = await deepl_translate_text(explanation)
    elif baidu_trans:
        explanation = await baidu_translate_text(explanation)
    return f"""<div class="container">
    <h1>今日天文一图</h1>
    <h2>{title}</h2>

    <div class="image-container">
        <img src="{url}" alt="APOD">
    </div>

    <p class="explanation">{explanation}</p>

    <div class="info">
        <p><strong>版权：</strong> {copyright}</p>
        <p><strong>日期：</strong> {date}</p>
    </div>
</div>
"""


async def generate_apod_image():
    try:
        if not apod_cache_json.exists():
            data = await fetch_apod_data()
            if not data:
                return None
        else:
            data = json.loads(apod_cache_json.read_text())
        md_content = await apod_json_to_md(data)
        css_file = (
                Path(__file__).parent
                / "css"
                / ("dark.css" if infopuzzle_mode else "light.css")
            )
        img_bytes = await md_to_pic(md_content, width=600, css_path=str(css_file))
        return img_bytes
    except Exception as e:
        logger.error(f"生成 NASA APOD 图片时发生错误：{e}")
        return None
