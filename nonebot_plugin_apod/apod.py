import re
import json
import httpx

from nonebot import get_plugin_config
from nonebot.log import logger
from nonebot_plugin_localstore as store
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_saa import SaaTarget, Text

from .config import Config


plugin_config = get_plugin_config(Config)
NASA_API_URL = "https://api.nasa.gov/planetary/apod"
NASA_API_KEY = plugin_config.nasa_api_key


def save_task_config(send_time: str, target: SaaTarget):
    data_file = store.get_plugin_data_file("task_config.json")
    config = {'send_time': send_time}
    data_file.write_text(json.dumps(config))


def load_task_config():
    data_file = store.get_plugin_data_file("task_config.json")
    try:
        config = json.loads(data_file.read_text())
        return config.get('send_time')
    except FileNotFoundError:
        return None


def is_valid_time_format(time_str: str) -> bool:
    return bool(re.match(r"^\d{1,2}:\d{2}$", time_str))


async def fetch_apod_data():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(NASA_API_URL, params={"api_key": NASA_API_KEY})
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"获取 NASA 每日一图数据时发生错误: {e}")
        return None


async def send_apod(target: SaaTarget):
    apod_data = await fetch_apod_data()
    if apod_data:
        url = apod_data.get("url")
        message = f"今日天文图片：{url}"
        await Text(message).send_to(target)
    else:
        await Text("无法获取今天的天文图片。").send_to(target)


def schedule_apod_task(send_time: str, target: SaaTarget):
    try:
        hour, minute = map(int, send_time.split(":"))
        scheduler.add_job(
            func=send_apod,
            trigger="cron",
            hour=hour,
            minute=minute,
            id="send_apod_task",
            max_instances=1,
            replace_existing=True,
        )
        logger.info(f"已成功设置 NASA 每日天文一图定时任务，发送时间为 {send_time}")
        save_task_config(send_time)
    except ValueError:
        logger.error(f"时间格式错误：{send_time}，请使用 HH:MM 格式")


def remove_apod_task():
    job = scheduler.get_job("send_apod_task")
    if job:
        job.remove()
        logger.info("已移除 NASA 每日天文一图定时任务")


send_time = load_task_config()
if send_time:
    schedule_apod_task(send_time)