import json
import httpx
import datetime

from nonebot.log import logger
import nonebot_plugin_localstore as store
from nonebot import get_plugin_config, get_bot
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_saa import Text, Image, PlatformTarget

from .config import Config

plugin_config = get_plugin_config(Config)
NASA_API_URL = "https://api.nasa.gov/planetary/apod"
NASA_API_KEY = plugin_config.apod_api_key
apod_cache_image = store.get_plugin_cache_file("apod_image")
task_config_file = store.get_plugin_data_file("apod_task_config.json")


def save_task_configs(tasks: list):
    try:
        serialized_tasks = [
            {"send_time": task["send_time"], "target": task["target"].dict()} for task in tasks
        ]
        with task_config_file.open("w", encoding="utf-8") as f:
            json.dump({"tasks": serialized_tasks}, f, ensure_ascii=False, indent=4)
        logger.info("NASA 每日天文一图定时任务配置已保存")
    except Exception as e:
        logger.error(f"保存 NASA 每日天文一图定时任务配置时发生错误：{e}")


def load_task_configs():
    if not task_config_file.exists():
        return []
    try:
        with task_config_file.open("r", encoding="utf-8") as f:
            config = json.load(f)
        tasks = [
            {"send_time": task["send_time"], "target": PlatformTarget.deserialize(task["target"])}
            for task in config.get("tasks", [])
        ]
        return tasks
    except Exception as e:
        logger.error(f"加载 NASA 每日天文一图定时任务配置时发生错误：{e}")
        return []


async def fetch_apod_data() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(NASA_API_URL, params={"api_key": NASA_API_KEY})
            response.raise_for_status()
            data = response.json()
            if data.get("media_type") == "image" and "url" in data:
                image_url = data["url"]
                image_response = await client.get(image_url)
                image_response.raise_for_status()
                apod_cache_image.write_bytes(image_response.content)
                return True
            else:
                return False
    except httpx.RequestError as e:
        logger.error(f"获取 NASA 每日天文一图数据时发生错误: {e}")
        return False


async def send_apod(target: PlatformTarget):
    apod_is_image = await fetch_apod_data()
    if apod_is_image:
        try:
            await Text("今日天文一图为").send_to(target, bot=get_bot())
            await Image(str(apod_cache_image)).send_to(target, bot=get_bot())
        except Exception as e:
            logger.error(f"发送 NASA 每日天文一图时发生错误：{e}")
            await Text("发送 NASA 每日天文一图时发生错误").send_to(target, bot=get_bot())


def schedule_apod_task(send_time: str, target: PlatformTarget):
    try:
        hour, minute = map(int, send_time.split(":"))
        job_id = f"send_apod_task_{target.dict()}"
        scheduler.add_job(
            func=send_apod,
            trigger="cron",
            args=[target],
            hour=hour,
            minute=minute,
            id=job_id,
            max_instances=1,
            replace_existing=True,
        )
        logger.info(f"已成功设置 NASA 每日天文一图定时任务，发送时间为 {send_time} (目标: {target})")
        tasks = load_task_configs()
        tasks = [task for task in tasks if task["target"] != target]
        tasks.append({"send_time": send_time, "target": target})
        save_task_configs(tasks)
    except ValueError:
        logger.error(f"时间格式错误：{send_time}，请使用 HH:MM 格式")
        raise ValueError(f"时间格式错误：{send_time}")
    except Exception as e:
        logger.error(f"设置 NASA 每日天文一图定时任务时发生错误：{e}")


def remove_apod_task(target: PlatformTarget):
    job_id = f"send_apod_task_{target.dict()}"
    job = scheduler.get_job(job_id)
    if job:
        job.remove()
        logger.info(f"已移除 NASA 每日天文一图定时任务 (目标: {target})")
        tasks = load_task_configs()
        tasks = [task for task in tasks if task["target"] != target]
        save_task_configs(tasks)
    else:
        logger.info(f"未找到 NASA 每日天文一图定时任务 (目标: {target})")


try:
    tasks = load_task_configs()
    for task in tasks:
        send_time = task["send_time"]
        target = task["target"]
        if send_time and target:
            schedule_apod_task(send_time, target)
    logger.debug("已恢复所有 NASA 每日天文一图定时任务")
except Exception as e:
    logger.error(f"恢复 NASA 每日天文一图定时任务时发生错误：{e}")