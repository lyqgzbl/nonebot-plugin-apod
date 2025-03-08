from typing import Optional
from asyncio import Lock
from pydantic import BaseModel


class Config(BaseModel):
    apod_api_key: Optional[str] = None
    apod_default_send_time: str = "13:00"
    apod_baidu_trans: bool = False
    apod_baidu_trans_appid: Optional[int] = None
    apod_baidu_trans_api_key: Optional[str] = None
    apod_reply_is_iamge: bool = True


# 缓存天文一图图片
cache_image = None
cache_lock = Lock()

# 获取缓存图片
def get_cache_image():
    return cache_image

# 设置缓存图片
async def set_cache_image(image):
    global cache_image
    async with cache_lock:
        cache_image = image

# 清除缓存图片
async def clear_cache_image():
    global cache_image
    async with cache_lock:
        cache_image = None