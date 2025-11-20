import json
import asyncio
import hashlib
from datetime import timedelta

import aiofiles
from nonebot.log import logger
import nonebot_plugin_localstore as store
from nonebot_plugin_apscheduler import scheduler
from nonebot import get_plugin_config, get_bot, get_driver
from nonebot_plugin_argot import Text, Image, add_argot, get_message_id
from nonebot_plugin_alconna.uniseg import MsgTarget, Target, UniMessage

from .infopuzzle import generate_apod_image
from .utils import translate_text_auto, ensure_apod_data
from .config import Config, get_cache_image, set_cache_image, clear_cache_image


driver = get_driver()
config_lock = asyncio.Lock()
plugin_config = get_plugin_config(Config)
baidu_trans = plugin_config.apod_baidu_trans
deepl_trans = plugin_config.apod_deepl_trans
apod_infopuzzle = plugin_config.apod_infopuzzle
apod_cache_json = store.get_plugin_cache_file("apod.json")
task_config_file = store.get_plugin_data_file("apod_task_config.json")


@driver.on_startup
async def init_apod_tasks():
    await restore_apod_tasks()


def generate_job_id(target: MsgTarget) -> str:
    serialized_target = json.dumps(Target.dump(target), sort_keys=True)
    job_id = hashlib.md5(serialized_target.encode()).hexdigest()
    return f"send_apod_task_{job_id}"


async def save_task_configs(tasks: list, locked: bool = False):
    async def _save():
        serialized_tasks = [
            {
                "send_time": task["send_time"],
                "target": Target.dump(task["target"]),
            }
            for task in tasks
        ]
        async with aiofiles.open(task_config_file, "w", encoding="utf-8") as f:
            await f.write(
                json.dumps(
                    {"tasks": serialized_tasks},
                    ensure_ascii=False,
                    indent=4
                    )
                )
    try:
        if locked:
            await _save()
        else:
            async with config_lock:
                await _save()
    except Exception as e:
        logger.error(f"保存 NASA 每日天文一图定时任务配置时发生错误：{e}")


async def remove_apod_task(target: MsgTarget):
    job_id = generate_job_id(target)
    job = scheduler.get_job(job_id)
    if not job:
        logger.debug(f"未找到 NASA 每日天文一图定时任务 (目标: {target})")
        return
    scheduler.remove_job(job_id)
    logger.debug(f"已移除 NASA 每日天文一图定时任务 (目标: {target})")
    async with config_lock:
        tasks = await load_task_configs(locked=True)
        tasks = [task for task in tasks if task["target"] != target]
        await save_task_configs(tasks, locked=True)


async def load_task_configs(locked: bool = False) -> list[dict]:
    if not task_config_file.exists():
        return []
    async def _load():
        if not task_config_file.exists():
            return []
        async with aiofiles.open(task_config_file, encoding="utf-8") as f:
            config = json.loads(await f.read())
        return [
            {"send_time": task["send_time"], "target": Target.load(task["target"])}
            for task in config.get("tasks", [])
        ]
    try:
        if locked:
            return await _load()
        async with config_lock:
            return await _load()
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"加载或解析任务配置时发生错误：{e}，将视为空配置。")
        return []
    except Exception as e:
        logger.error(f"加载 NASA 每日天文一图定时任务配置时发生错误：{e}")
        return []


async def send_apod(target: MsgTarget):
    logger.debug(f"主动发送目标: {target}")
    try:
        bot = get_bot(target.self_id)
    except Exception:
        logger.opt(colors=True).warning("<yellow>未找到可用的机器人实例，此任务将被跳过</yellow>")
        return
    if not await ensure_apod_data():
        await UniMessage.text("未能获取到今日的天文一图，请稍后再试。").send(
            target=target,
            bot=bot,
        )
        return
    async with aiofiles.open(apod_cache_json, encoding="utf-8") as f:
        data = json.loads(await f.read())
    if data.get("media_type") != "image" or "url" not in data:
        await UniMessage.text("今日 NASA 提供的为天文视频").send(target=target, bot=bot)
        return
    if not apod_infopuzzle:
        explanation = await translate_text_auto(data["explanation"])
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
    cache_image = get_cache_image() or await generate_apod_image()
    if not cache_image:
        await UniMessage.text("发送今日的天文一图失败，请稍后再试。").send(
            target=target,
            bot=bot,
        )
        return
    await set_cache_image(cache_image)
    url = data["hdurl"] if plugin_config.apod_hd_image else data["url"]
    message = await UniMessage.image(raw=cache_image).send(
        target=target,
        bot=bot,
    )
    await add_argot(
        message_id=get_message_id(message) or "",
        name="background",
        command="原图",
        segment=Image(url=url),
        expired_at=timedelta(minutes=2),
    )


async def schedule_apod_task(send_time: str, target: MsgTarget):
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
        async with config_lock:
            tasks = await load_task_configs(locked=True)
            tasks = [task for task in tasks if task["target"] != target]
            tasks.append({"send_time": send_time, "target": target})
            await save_task_configs(tasks, locked=True)
    except ValueError:
        logger.error(f"时间格式错误：{send_time}，请使用 HH:MM 格式")
        raise ValueError(f"时间格式错误：{send_time}")
    except Exception as e:
        logger.error(f"设置 NASA 每日天文一图定时任务时发生错误：{e}")


async def restore_apod_tasks():
    try:
        tasks = await load_task_configs()
        if not tasks:
            logger.debug("没有找到任何 NASA 每日天文一图定时任务配置")
            return
        for task in tasks:
            send_time = task["send_time"]
            target = task["target"]
            if send_time and target:
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
        logger.debug("已恢复所有 NASA 每日天文一图定时任务")
    except Exception as e:
        logger.error(f"恢复 NASA 每日天文一图定时任务时发生错误：{e}")


@scheduler.scheduled_job("cron", hour=13, minute=0, id="apod_clear_cache")
async def apod_clea_cache():
    try:
        if apod_cache_json.exists():
            apod_cache_json.unlink()
            logger.debug("apod 缓存 JSON 已清除")
        else:
            logger.debug("apod 缓存 JSON 不存在")
        await clear_cache_image()
        logger.debug("apod 图片缓存已清除")
    except Exception as e:
        logger.error(f"清除 apod 缓存时发生错误：{e}")
