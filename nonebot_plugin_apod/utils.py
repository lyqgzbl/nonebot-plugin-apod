import re
import json
import random
import hashlib
from datetime import datetime

import httpx
from nonebot.log import logger
from nonebot import get_plugin_config
import nonebot_plugin_localstore as store

from .config import Config

plugin_config = get_plugin_config(Config)
nasa_api_key = plugin_config.apod_api_key
baidu_trans = plugin_config.apod_baidu_trans
deepl_trans = plugin_config.apod_deepl_trans
apod_infopuzzle = plugin_config.apod_infopuzzle
NASA_API_URL = "https://api.nasa.gov/planetary/apod"
baidu_trans_appid = plugin_config.apod_baidu_trans_appid
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"
deepl_trans_api_key = plugin_config.apod_deepl_trans_api_key
baidu_trans_api_key = plugin_config.apod_baidu_trans_api_key
BAIDU_API_URL = "http://api.fanyi.baidu.com/api/trans/vip/translate"
apod_cache_json = store.get_plugin_cache_file("apod.json")
task_config_file = store.get_plugin_data_file("apod_task_config.json")


def is_valid_time_format(time_str: str) -> bool:
    if not re.match(r"^\d{1,2}:\d{2}$", time_str):
        return False
    try:
        hour, minute = map(int, time_str.split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except ValueError:
        return False


def is_valid_date_format(date_str: str) -> bool:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False
    return d > datetime(1995, 6, 16)


if baidu_trans:
    if not baidu_trans_api_key or not baidu_trans_appid:
        logger.opt(colors=True).warning("<yellow>百度翻译配置项不全,百度翻译未成功启用</yellow>")
        baidu_trans = False
if deepl_trans:
    if not deepl_trans_api_key:
        logger.opt(colors=True).warning("<yellow>DeepL翻译配置项不全,DeepL翻译未成功启用</yellow>")
        deelp_trans = False


async def baidu_translate_text(
        query,
        from_lang="auto",
        to_lang="zh",
        appid=baidu_trans_appid,
        api_key=baidu_trans_api_key,
    ) -> str:
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


async def translate_text_auto(text: str) -> str:
    if deelp_trans:
        return await deepl_translate_text(text)
    elif baidu_trans:
        return await baidu_translate_text(text)
    return text


async def fetch_apod_data() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(NASA_API_URL, params={"api_key": nasa_api_key})
            response.raise_for_status()
            data = response.json()
            apod_cache_json.write_text(json.dumps(data, indent=4))
            return True
    except httpx.RequestError as e:
        logger.error(f"获取 NASA 每日天文一图数据时发生错误: {e}")
        return False


async def fetch_apod_data_by_date(date: str) -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                NASA_API_URL,
                params={"api_key": nasa_api_key, "date": date},
            )
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return None
    except httpx.RequestError as e:
        logger.error(f"获取 NASA 指定日期天文一图数据时发生错误: {e}")
        return None


async def fetch_randomly_apod_data() -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                NASA_API_URL,
                params={"api_key": nasa_api_key, "count": 1},
            )
            data = response.json()
            return data[0]
    except httpx.RequestError as e:
        logger.error(f"获取 NASA 随机天文一图数据时发生错误: {e}")
        return None
