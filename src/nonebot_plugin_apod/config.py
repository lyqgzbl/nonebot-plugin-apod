from collections.abc import Awaitable, Callable
from pydantic import BaseModel

from nonebot import get_plugin_config

from .singleflight import SingleFlight


class Config(BaseModel):
    apod_api_key: str | None = None
    apod_default_send_time: str = "13:00"
    apod_hd_image: bool = False
    apod_baidu_trans: bool = False
    apod_baidu_trans_appid: int | None = None
    apod_baidu_trans_api_key: str | None = None
    apod_infopuzzle: bool = True
    apod_infopuzzle_dark_mode: bool = False
    apod_deepl_trans: bool = False
    apod_deepl_trans_api_key: str | None = None
    apod_openai_trans: bool = False
    apod_openai_model_name: str | None = None
    apod_openai_api_key: str | None = None
    apod_openai_api_url: str = "https://api.openai.com/v1"
    # 向后兼容配置项
    apod_qwen_trans: bool = False
    apod_qwen_mt_model_name: str = "qwen-mt-flash"
    apod_qwen_mt_api_key: str | None = None
    apod_qwen_mt_api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    apod_mirror_url: str | None = None
    apod_mirror_api_key: str | None = None


plugin_config = get_plugin_config(Config)


# 缓存天文一图图片
cache_image: bytes | None = None
cache_flight: SingleFlight[bytes | None] = SingleFlight()
cache_lock = cache_flight


# 获取缓存图片
async def get_cache_image(
    generator: Callable[[], Awaitable[bytes | None]] | None = None,
) -> bytes | None:
    global cache_image
    if cache_image is not None:
        return cache_image

    if generator is None:
        return None

    async def _generate_and_cache() -> bytes | None:
        global cache_image
        if cache_image is not None:
            return cache_image
        img = await generator()
        if img:
            cache_image = img
        return img

    return await cache_flight.do("apod_image", _generate_and_cache)


# 设置缓存图片
async def set_cache_image(image: bytes | None):
    global cache_image
    cache_image = image


# 清除缓存图片
async def clear_cache_image():
    global cache_image
    cache_image = None
