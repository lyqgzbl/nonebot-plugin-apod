import re
import json
import random
import hashlib
import asyncio
from datetime import datetime

import httpx
import aiofiles
from nonebot.log import logger
from nonebot import get_driver
import nonebot_plugin_localstore as store

from .config import plugin_config

nasa_api_key = plugin_config.apod_api_key
baidu_trans = plugin_config.apod_baidu_trans
deepl_trans = plugin_config.apod_deepl_trans
qwen_trans = plugin_config.apod_qwen_trans
apod_infopuzzle = plugin_config.apod_infopuzzle
NASA_API_URL = "https://api.nasa.gov/planetary/apod"
baidu_trans_appid = plugin_config.apod_baidu_trans_appid
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"
deepl_trans_api_key = plugin_config.apod_deepl_trans_api_key
baidu_trans_api_key = plugin_config.apod_baidu_trans_api_key
BAIDU_API_URL = "http://api.fanyi.baidu.com/api/trans/vip/translate"
QWEN_MT_API_URL = plugin_config.apod_qwen_mt_api_url
qwen_mt_model_name = plugin_config.apod_qwen_mt_model_name
qwen_mt_api_key = plugin_config.apod_qwen_mt_api_key
apod_cache_json = store.get_plugin_cache_file("apod.json")
task_config_file = store.get_plugin_data_file("apod_task_config.json")
mirror_url = plugin_config.apod_mirror_url
mirror_api_key = plugin_config.apod_mirror_api_key


_httpx_client: httpx.AsyncClient | None = None


def get_httpx_client() -> httpx.AsyncClient:
    global _httpx_client
    if _httpx_client is None:
        _httpx_client = httpx.AsyncClient(
            timeout=20,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )
    return _httpx_client


driver = get_driver()


@driver.on_shutdown
async def _():
    global _httpx_client
    if _httpx_client:
        await _httpx_client.aclose()


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
    return d >= datetime(1995, 6, 16) and d <= datetime.now()


async def ensure_apod_data() -> bool:
    if apod_cache_json.exists():
        return True
    return await fetch_data()


if baidu_trans and (not baidu_trans_api_key or not baidu_trans_appid):
    logger.opt(colors=True).warning(
        "<yellow>百度翻译配置项不全,百度翻译未成功启用</yellow>"
    )
    baidu_trans = False
if deepl_trans and not deepl_trans_api_key:
    logger.opt(colors=True).warning(
        "<yellow>DeepL翻译配置项不全,DeepL翻译未成功启用</yellow>"
    )
    deepl_trans = False
if qwen_trans and not qwen_mt_api_key:
    logger.opt(colors=True).warning(
        "<yellow>Qwen翻译配置项不全,Qwen翻译未成功启用</yellow>"
    )
    qwen_trans = False


async def qwen_translate_text(
    text: str,
    target_lang: str = "Chinese",
    source_lang: str = "English",
    api_key=qwen_mt_api_key,
    model_name=qwen_mt_model_name,
    api_url=QWEN_MT_API_URL,
) -> str:
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": text,
                }
            ],
            "translation_options": {
                "source_lang": source_lang,
                "target_lang": target_lang,
                "domains": (
                    "The text is from astronomy domain. Use professional astronomical "
                    "terminology and maintain scientific accuracy."
                    "Astronomy popular science article, natural Chinese style"
                ),
            },
        }
        client = get_httpx_client()
        url = api_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        resp = await client.post(
            url=url, headers=headers, json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Qwen 翻译时发生错误：{e}")
        raise


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
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        client = get_httpx_client()
        response = await client.post(BAIDU_API_URL, data=payload, headers=headers)
        result_all = response.text
        result = json.loads(result_all)
        if "trans_result" in result:
            return "\n".join([item["dst"] for item in result["trans_result"]])
        else:
            error_msg = result.get("error_msg", "未知错误")
            logger.error(f"百度翻译 API 返回错误: {error_msg}")
            raise RuntimeError(f"百度翻译失败: {error_msg}")
    except Exception as e:
        logger.error(f"百度 翻译时发生错误：{e}")
        raise


async def deepl_translate_text(
    text: str,
    target_lang: str = "ZH",
    api_key=deepl_trans_api_key,
) -> str:
    try:
        client = get_httpx_client()
        response = await client.post(
            url=DEEPL_API_URL,
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
        raise


async def translate_text_auto(text: str, timeout: int = 8) -> str:
    translate_func = (
        qwen_translate_text
        if qwen_trans
        else deepl_translate_text
        if deepl_trans
        else baidu_translate_text
        if baidu_trans
        else None
    )
    if not translate_func:
        return text
    try:
        return await asyncio.wait_for(translate_func(text), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"翻译超时（>{timeout}s），将返回原文")
    except Exception as e:
        logger.error(f"翻译服务发生错误：{e}，将返回原文")
    return text


async def fetch_apod_data() -> bool:
    try:
        client = get_httpx_client()
        response = await client.get(NASA_API_URL, params={"api_key": nasa_api_key})
        response.raise_for_status()
        data = response.json()
        async with aiofiles.open(apod_cache_json, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=4))
        return True
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error(f"获取 NASA 每日天文一图数据时发生错误: {e}")
        return False


async def fetch_apod_data_by_date(date: str) -> dict | None:
    try:
        client = get_httpx_client()
        response = await client.get(
            NASA_API_URL,
            params={"api_key": nasa_api_key, "date": date},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error(f"获取 NASA 指定日期天文一图数据时发生错误: {e}")
        return None


async def fetch_randomly_apod_data() -> dict | None:
    try:
        client = get_httpx_client()
        response = await client.get(
            NASA_API_URL,
            params={"api_key": nasa_api_key, "count": 1},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        if isinstance(data, dict):
            return data
        return None
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error(f"获取 NASA 随机天文一图数据时发生错误: {e}")
        return None


async def fetch_apod_data_from_mirror(url: str, api_key: str) -> bool:
    try:
        client = get_httpx_client()
        headers = {"Authorization": f"Bearer {api_key}"}
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        async with aiofiles.open(apod_cache_json, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=4))
        logger.debug("成功通过镜像获取天文一图数据")
        return True
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error(f"通过镜像获取天文一图数据时发生错误: {e}")
        return False


async def fetch_apod_data_by_date_from_mirror(
    url: str, api_key: str, date: str
) -> dict | None:
    try:
        client = get_httpx_client()
        headers = {"Authorization": f"Bearer {api_key}"}
        response = await client.get(
            url,
            headers=headers,
            params={"date": date},
        )
        response.raise_for_status()
        data = response.json()
        return data
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error(f"通过镜像获取指定日期天文一图数据时发生错误: {e}")
        return None


async def fetch_data() -> bool:
    if mirror_url and mirror_api_key:
        ok = await fetch_apod_data_from_mirror(mirror_url, mirror_api_key)
        if ok:
            return True
        logger.warning("镜像获取失败, 回退到 NASA API")
    ok = await fetch_apod_data()
    return ok
