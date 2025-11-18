import json
import hashlib
from datetime import timedelta

import httpx
from nonebot.log import logger
import nonebot_plugin_localstore as store
from nonebot_plugin_apscheduler import scheduler
from nonebot import get_plugin_config, get_bot, get_bots
from nonebot_plugin_argot import Text, Image, add_argot, get_message_id
from nonebot_plugin_alconna.uniseg import MsgTarget, Target, UniMessage

from .config import Config, get_cache_image, set_cache_image, clear_cache_image
from .infopuzzle import generate_apod_image, deepl_translate_text, baidu_translate_text


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


def generate_job_id(target: MsgTarget) -> str:
    serialized_target = json.dumps(Target.dump(target), sort_keys=True)
    job_id = hashlib.md5(serialized_target.encode()).hexdigest()
    return f"send_apod_task_{job_id}"


def save_task_configs(tasks: list):
    try:
        serialized_tasks = [
            {
                "send_time": task["send_time"],
                "target": Target.dump(task["target"]),
            }
            for task in tasks
        ]
        with task_config_file.open("w", encoding="utf-8") as f:
            json.dump({"tasks": serialized_tasks}, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"保存 NASA 每日天文一图定时任务配置时发生错误：{e}")


def load_task_configs():
    if not task_config_file.exists():
        return []
    try:
        with task_config_file.open("r", encoding="utf-8") as f:
            config = json.load(f)
        tasks = [
            {"send_time": task["send_time"], "target": Target.load(task["target"])}
            for task in config.get("tasks", [])
        ]
        return tasks
    except Exception as e:
        logger.error(f"加载 NASA 每日天文一图定时任务配置时发生错误：{e}")
        return []


async def fetch_apod_data():
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


async def fetch_apod_data_by_date(date: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                NASA_API_URL,
                params={"api_key": nasa_api_key, "date": date},
            )
            data = response.json()
            return data
    except httpx.RequestError as e:
        logger.error(f"获取 NASA 指定日期天文一图数据时发生错误: {e}")
        return None


async def fetch_randomly_apod_data():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                NASA_API_URL,
                params={"api_key": nasa_api_key, "count": 1},
            )
            data = response.json()
            return data
    except httpx.RequestError as e:
        logger.error(f"获取 NASA 随机天文一图数据时发生错误: {e}")
        return None


async def send_apod(target: MsgTarget):
    logger.debug(f"主动发送目标: {target}")
    bots = get_bots()
    if target.self_id in bots:
        bot = get_bot(target.self_id)
    else:
        logger.warning("<yellow>未找到可用的机器人实例，此任务将被跳过</yellow>")
        return
    if (not apod_cache_json.exists()) and (not await fetch_apod_data()):
        await UniMessage.text("未能获取到今日的天文一图，请稍后再试。").send(
            target=target,
            bot=bot,
        )
        return
    data = json.loads(apod_cache_json.read_text())
    if data.get("media_type") != "image" or "url" not in data:
        await UniMessage.text("今日 NASA 提供的为天文视频").send(target=target, bot=bot)
        return
    if apod_infopuzzle:
        cache_image = get_cache_image() or await generate_apod_image()
        if cache_image:
            await set_cache_image(cache_image)
            message = await UniMessage.image(raw=cache_image).send(
                target=target,
                bot=bot,
            )
            await add_argot(
                message_id=get_message_id(message) or "",
                name="infopuzzle_background",
                command="原图",
                segment=Image(url=data["url"]),
                expired_at=timedelta(minutes=2),
            )
        else:
            await UniMessage.text("发送今日的天文一图失败，请稍后再试。").send(
                target=target,
                bot=bot,
            )
    else:
        explanation=data["explanation"]
        if deepl_trans:
            explanation = await deepl_translate_text(explanation)
        elif baidu_trans:
            explanation = await baidu_translate_text(explanation)
        message = await UniMessage.text("今日天文一图为").image(url=data["url"]).send(
            target=target,
            bot=bot,
        )
        await add_argot(
        message_id=get_message_id(message) or "",
        name="explanation",
        command="简介",
        segment=Text(explanation),
        expired_at=timedelta(minutes=2),
    )


def schedule_apod_task(send_time: str, target: MsgTarget):
    try:
        hour, minute = map(int, send_time.split(":"))
        job_id = generate_job_id(target)
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
        logger.info(
            "已成功设置 NASA 每日天文一图定时任务,"
            f"发送时间为 {send_time} (目标: {target})"
        )
        tasks = load_task_configs()
        tasks = [task for task in tasks if task["target"] != target]
        tasks.append({"send_time": send_time, "target": target})
        save_task_configs(tasks)
    except ValueError:
        logger.error(f"时间格式错误：{send_time}，请使用 HH:MM 格式")
        raise ValueError(f"时间格式错误：{send_time}")
    except Exception as e:
        logger.error(f"设置 NASA 每日天文一图定时任务时发生错误：{e}")


def remove_apod_task(target: MsgTarget):
    job_id = generate_job_id(target)
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
    if tasks:
        for task in tasks:
            send_time = task["send_time"]
            target = task["target"]
            if send_time and target:
                schedule_apod_task(send_time, target)
        logger.debug("已恢复所有 NASA 每日天文一图定时任务")
    else:
        logger.debug("没有找到任何 NASA 每日天文一图定时任务配置")
except Exception as e:
    logger.error(f"恢复 NASA 每日天文一图定时任务时发生错误：{e}")


@scheduler.scheduled_job("cron", hour=13, minute=0, id="clear_apod_cache")
async def clear_apod_cache():
    if apod_cache_json.exists():
        apod_cache_json.unlink()
        logger.debug("apod缓存已清除")
    else:
        logger.debug("apod缓存不存在")
    await clear_cache_image()
    logger.debug("apod图片缓存已清除")
