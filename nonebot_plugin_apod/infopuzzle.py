import json
import random
import hashlib
from pathlib import Path

import httpx
from nonebot.log import logger
from nonebot import get_plugin_config
import nonebot_plugin_localstore as store
from nonebot_plugin_htmlrender import md_to_pic

from .config import Config


# 加载配置
plugin_config = get_plugin_config(Config)
baidu_trans = plugin_config.apod_baidu_trans
deepl_trans = plugin_config.apod_deepl_trans
infopuzzle_mode = plugin_config.apod_infopuzzle_dark_mode
baidu_trans_appid = plugin_config.apod_baidu_trans_appid
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"
deepl_trans_api_key = plugin_config.apod_deepl_trans_api_key
baidu_trans_api_key = plugin_config.apod_baidu_trans_api_key
BAIDU_API_URL = "http://api.fanyi.baidu.com/api/trans/vip/translate"
apod_cache_json = store.get_plugin_cache_file("apod.json")


# 翻译配置检查
if baidu_trans:
    if not baidu_trans_api_key or not baidu_trans_appid:
        logger.opt(colors=True).warning("<yellow>百度翻译配置项不全,百度翻译未成功启用</yellow>")
        baidu_trans = False
if deepl_trans:
    if not deepl_trans_api_key:
        logger.opt(colors=True).warning("<yellow>DeepL翻译配置项不全,DeepL翻译未成功启用</yellow>")
        deelp_trans = False


# 百度翻译天文一图描述
async def baidu_translate_text(
        query,
        from_lang="auto",
        to_lang="zh",
        appid=baidu_trans_appid,
        api_key=baidu_trans_api_key,
    ):
    try:
        salt = random.randint(32768, 65536)
        sign = hashlib.md5(f"{appid}{query}{salt}{api_key}".encode()).hexdigest()
        payload = {
            "appid": appid,
            "q": query,
            "from": from_lang,
            "to": to_lang,
            "salt": salt,
            "sign": sign,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(BAIDU_API_URL, data=payload, headers=headers)
            result_all = response.text
            result = json.loads(result_all)
            if "trans_result" in result:
                return "\n".join([item["dst"] for item in result["trans_result"]])
            else:
                return f"Error: {result.get('error_msg', '未知错误')}"
    except Exception as e:
        logger.error(f"百度 翻译时发生错误：{e}")
        return f"Exception occurred: {str(e)}"


# DeepL 翻译天文一图描述
async def deepl_translate_text(
        text: str,
        target_lang: str = "ZH",
        api_key=deepl_trans_api_key,
    ) -> str:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DEEPL_API_URL,
                headers={
                    "Authorization": f"DeepL-Auth-Key {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": [text],
                    "target_lang": target_lang,
                },
            )
            response.raise_for_status()
            result = response.json()
            return result["translations"][0]["text"]
    except Exception as e:
        logger.error(f"DeepL 翻译时发生错误：{e}")
        return f"Exception occurred: {str(e)}"


# 将天文一图 JSON 文件转换为 Markdown
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


# 生成天文一图图片
async def generate_apod_image():
    from .apod import fetch_apod_data
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
