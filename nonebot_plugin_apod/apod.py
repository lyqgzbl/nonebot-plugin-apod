import json
import hashlib

import httpx
from nonebot.log import logger
import nonebot_plugin_localstore as store
from nonebot_plugin_apscheduler import scheduler
from nonebot import get_plugin_config, get_bot, get_bots
from nonebot_plugin_alconna.uniseg import MsgTarget, Target, UniMessage

from .infopuzzle import generate_apod_image
from .config import Config, get_cache_image, set_cache_image, clear_cache_image


# 加载配置
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


# 生成任务 ID
def generate_job_id(target: MsgTarget) -> str:
    serialized_target = json.dumps(Target.dump(target), sort_keys=True)
    job_id = hashlib.md5(serialized_target.encode()).hexdigest()
    return f"send_apod_task_{job_id}"


# 保存定时任务配置
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
        logger.info("NASA 每日天文一图定时任务配置已保存")
    except Exception as e:
        logger.error(f"保存 NASA 每日天文一图定时任务配置时发生错误：{e}")


# 加载定时任务配置
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


# 获取今日天文一图数据
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


# 发送今日天文一图
async def send_apod(target: MsgTarget):
    logger.debug(f"主动发送目标: {target}")
    bots = get_bots()
    if target.self_id in bots:
        bot = get_bot(target.self_id)
    else:
        logger.warning("<yellow>未找到可用的机器人实例，此任务将被跳过</yellow>")
        return
    if not apod_cache_json.exists() and not await fetch_apod_data():
        await UniMessage.text("未能获取到今日的天文一图，请稍后再试。").send(target=target, bot=bot)
        return
    data = json.loads(apod_cache_json.read_text())
    if data.get("media_type") != "image" or "url" not in data:
        await UniMessage.text("今日 NASA 提供的为天文视频").send(target=target, bot=bot)
        return
    if apod_infopuzzle:
        cache_image = get_cache_image() or await generate_apod_image()
        if cache_image:
            await set_cache_image(cache_image)
            await UniMessage.image(raw=cache_image).send(target=target, bot=bot)
        else:
            await UniMessage.text("发送今日的天文一图失败，请稍后再试。").send(target=target, bot=bot)
    else:
        await UniMessage.text("今日天文一图为").image(url=data["url"]).send(target=target, bot=bot)


# 设置每日天文一图定时任务
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


# 移除每日天文一图定时任务
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


# 恢复定时任务
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


# 定时清除缓存
@scheduler.scheduled_job("cron", hour=13, minute=0, id="clear_apod_cache")
async def clear_apod_cache():
    if apod_cache_json.exists():
        apod_cache_json.unlink()
        logger.debug("apod缓存已清除")
    else:
        logger.debug("apod缓存不存在")
    await clear_cache_image()
    logger.debug("apod图片缓存已清除")
