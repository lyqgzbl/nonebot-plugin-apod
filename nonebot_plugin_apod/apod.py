import json
import asyncio
import hashlib
from datetime import timedelta

import aiofiles
from nonebot.log import logger
import nonebot_plugin_localstore as store
from nonebot_plugin_apscheduler import scheduler
from nonebot import get_plugin_config, get_bot, get_bots, get_driver
from nonebot_plugin_argot import Text, Image, add_argot, get_message_id
from nonebot_plugin_alconna.uniseg import MsgTarget, Target, UniMessage

from .infopuzzle import generate_apod_image
from .config import Config, get_cache_image, set_cache_image, clear_cache_image
from .utils import fetch_apod_data, baidu_translate_text, deepl_translate_text


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
        async with aiofiles.open(str(task_config_file), "w", encoding="utf-8") as f:
            await f.write(json.dumps(
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
    if job:
        scheduler.remove_job(job_id)
        logger.info(f"已移除 NASA 每日天文一图定时任务 (目标: {target})")
        async with config_lock:
            tasks = await load_task_configs(locked=True)
            tasks = [task for task in tasks if task["target"] != target]
            await save_task_configs(tasks, locked=True)
    else:
        logger.info(f"未找到 NASA 每日天文一图定时任务 (目标: {target})")


async def load_task_configs(locked: bool = False) -> list[dict]:
    if not task_config_file.exists():
        return []
    async def _load():
        if not task_config_file.exists():
            return []
        async with aiofiles.open(str(task_config_file), encoding="utf-8") as f:
            content = await f.read()
        if not content.strip():
            return []
        config = json.loads(content)
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
    async with aiofiles.open(str(apod_cache_json), encoding="utf-8") as f:
        content = await f.read()
        data = json.loads(content)
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
            await save_task_configs(tasks)
    except ValueError:
        logger.error(f"时间格式错误：{send_time}，请使用 HH:MM 格式")
        raise ValueError(f"时间格式错误：{send_time}")
    except Exception as e:
        logger.error(f"设置 NASA 每日天文一图定时任务时发生错误：{e}")


async def restore_apod_tasks():
    try:
        tasks = await load_task_configs()
        if tasks:
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
