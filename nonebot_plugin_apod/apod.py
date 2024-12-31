import datetime
import httpx
import json
import nonebot_plugin_localstore as store

from nonebot import get_plugin_config
from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_saa import Text, SaaTarget
from .config import Config


plugin_config = get_plugin_config(Config)
NASA_API_URL = "https://api.nasa.gov/planetary/apod"
NASA_API_KEY = plugin_config.nasa_api_key
task_config_file = store.get_plugin_data_file("apod_task_config.json")


def save_task_config(send_time: str, target: SaaTarget):
    try:
        config = {
            "send_time": send_time,
            "target": target.dict() if target else None,
        }
        with task_config_file.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        logger.info("NASA 每日天文一图定时任务配置已保存")
    except Exception as e:
        logger.error(f"保存 NASA 每日天文一图定时任务配置时发生错误：{e}")


def load_task_config():
    if not task_config_file.exists():
        return None, None
    try:
        with task_config_file.open("r", encoding="utf-8") as f:
            config = json.load(f)
        send_time = config.get("send_time")
        target_data = config.get("target")
        target = SaaTarget.parse_obj(target_data) if target_data else None
        return send_time, target
    except Exception as e:
        logger.error(f"加载 NASA 每日天文一图定时任务配置时发生错误：{e}")
        return None, None


async def fetch_apod_data():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(NASA_API_URL, params={"api_key": NASA_API_KEY})
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"获取 NASA 每日天文一图数据时发生错误: {e}")
        return None


async def send_apod(target: SaaTarget):
    apod_data = await fetch_apod_data()
    if apod_data:
        title = apod_data.get("title", "NASA APOD")
        url = apod_data.get("url")
        try:
            from nonebot_plugin_saa import Image
            await Image(url).send_to(target)
            await Text(f"链接：{url}").send_to(target)
        except Exception as e:
                logger.error(f"发送 NASA 每日天文一图时发生错误：{e}")
            await Text("发送 NASA 每日天文一图时发生错误").send_to(target)
    else:
        logger.error("无法获取今天的天文图片")
        await Text("无法获取今天的天文图片。").send_to(target)


def schedule_apod_task(send_time: str, target: SaaTarget):
    try:
        hour, minute = map(int, send_time.split(":"))
        scheduler.add_job(
            func=send_apod,
            trigger="cron",
            args=[target],
            hour=hour,
            minute=minute,
            id="send_apod_task",
            max_instances=1,
            replace_existing=True,
        )
        logger.info(f"已成功设置 NASA 每日天文一图定时任务，发送时间为 {send_time}")
        save_task_config(send_time, target)
    except ValueError:
        logger.error(f"时间格式错误：{send_time}，请使用 HH:MM 格式")
        raise ValueError(f"时间格式错误：{send_time}")
    except Exception as e:
        logger.error(f"设置 NASA 每日天文一图定时任务时发生错误：{e}")


def remove_apod_task():
    job = scheduler.get_job("send_apod_task")
    if job:
        job.remove()
        logger.info("已移除 NASA 每日天文一图定时任务")
        if task_config_file.exists():
            task_config_file.unlink()
            logger.info("已删除 NASA 每日天文一图定时任务配置")
    else:
        logger.info("未找到 NASA 每日天文一图定时任务")


try:
    send_time, target = load_task_config()
    if send_time and target:
        schedule_apod_task(send_time, target)
        logger.debug("已恢复 NASA 每日天文一图定时任务")
except Exception as e:
    logger.error(f"恢复 NASA 每日天文一图定时任务时发生错误：{e}")