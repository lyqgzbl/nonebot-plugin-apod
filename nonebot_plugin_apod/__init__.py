import json

import aiofiles
from nonebot.rule import Rule
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot import require, get_plugin_config
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_argot")
require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_htmlrender")
require("nonebot_plugin_apscheduler")
import nonebot_plugin_localstore as store
from nonebot_plugin_argot import Image, Text
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_argot.extension import ArgotExtension
from nonebot_plugin_alconna.uniseg import UniMessage, MsgTarget
from nonebot_plugin_alconna import Args, Match, Option, Alconna, CommandMeta, on_alconna

from .config import Config, get_cache_image, set_cache_image
from .apod import (
    generate_job_id,
    remove_apod_task,
    schedule_apod_task,
    generate_apod_image,
)
from .utils import (
    ensure_apod_data,
    translate_text_auto,
    is_valid_date_format,
    is_valid_time_format,
    fetch_apod_data_by_date,
    fetch_randomly_apod_data,
)


__plugin_meta__ = PluginMetadata(
    name="每日天文一图",
    description="定时发送 NASA 每日提供的天文图片",
    usage="/apod 状态; /apod 关闭; /apod 开启 13:30",
    type="application",
    homepage="https://github.com/lyqgzbl/nonebot-plugin-apod",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={
        "author": "lyqgzbl <admin@lyqgzbl.com>",
        "version": "1.0.9",
    },
)


plugin_config = get_plugin_config(Config)
apod_infopuzzle = plugin_config.apod_infopuzzle
default_time = plugin_config.apod_default_send_time
apod_cache_json = store.get_plugin_cache_file("apod.json")
task_config_file = store.get_plugin_data_file("apod_task_config.json")


if not plugin_config.apod_api_key:
    logger.opt(colors=True).warning(
        "<yellow>缺失必要配置项 'apod_api_key'，已禁用该插件</yellow>"
    )
def is_enable() -> Rule:
    def _rule() -> bool:
        return bool(plugin_config.apod_api_key)
    return Rule(_rule)


apod_setting = on_alconna(
    Alconna(
        "apod",
        Option("状态|status"),
        Option("关闭|stop"),
        Option("开启|start", Args["send_time?#每日一图发送时间", str]),
        meta=CommandMeta(
            compact=True,
            description="NASA 每日天文图片设置",
            usage=__plugin_meta__.usage,
            example=(
                "/apod 状态\n"
                "/apod 关闭\n"
                "/apod 开启 13:30"
            ),
        ),
    ),
    block=True,
    priority=10,
    rule=is_enable(),
    aliases={"APOD"},
    use_cmd_start=True,
    permission=SUPERUSER,
)


apod_command = on_alconna(
    Alconna(
        "今日天文一图",
        meta=CommandMeta(
            description="获取今日天文一图",
            example=(
                "/今日天文一图"
            ),
        ),
    ),
    block=True,
    priority=10,
    rule=is_enable(),
    use_cmd_start=True,
    extensions=[ArgotExtension()],
)


randomly_apod_command = on_alconna(
    Alconna(
        "随机天文一图",
        meta=CommandMeta(
            compact=True,
            description="获取随机天文一图",
            example="/随机天文一图",
        ),
    ),
    block=True,
    priority=10,
    rule=is_enable(),
    use_cmd_start=True,
    extensions=[ArgotExtension()],
)


date_apod_command = on_alconna(
    Alconna(
        "指定日期天文一图",
        Args["date#指定日期，格式为YYYY-MM-DD", str],
        meta=CommandMeta(
            compact=True,
            description="获取指定日期天文一图",
            usage="/指定日期天文一图 <YYYY-MM-DD>",
            example="/指定日期天文一图 2023-10-01",
        ),
    ),
    block=True,
    priority=10,
    rule=is_enable(),
    use_cmd_start=True,
    extensions=[ArgotExtension()],
)


@apod_command.handle()
async def apod_command_handle():
    if not await ensure_apod_data():
        await apod_command.finish("获取今日天文一图失败请稍后再试")
    async with aiofiles.open(apod_cache_json, encoding="utf-8") as f:
        data = json.loads(await f.read())
    if data.get("media_type") != "image" or "url" not in data:
        await apod_command.finish("今日 NASA 提供的为天文视频")
    if not apod_infopuzzle:
        explanation = await translate_text_auto(data["explanation"])
        await UniMessage.text("今日天文一图为").image(url=data["url"]).finish(
            reply_to=True,
            argot={
                "name": "explanation",
                "segment": Text(explanation),
                "command": "简介",
                "expired_at": 360,
            },
        )
    cache_image = get_cache_image() or await generate_apod_image()
    if not cache_image:
        await apod_command.finish("发送今日的天文一图失败")
    await set_cache_image(cache_image)
    url = data["hdurl"] if plugin_config.apod_hd_image else data["url"]
    await UniMessage.image(raw=cache_image).send(
        reply_to=True,
        argot={
            "name": "background",
            "segment": Image(url=url),
            "command": "原图",
            "expired_at": 360,
        }
    )


@apod_setting.assign("status")
async def apod_status(target: MsgTarget):
    job_id = generate_job_id(target)
    job = scheduler.get_job(job_id)
    if not job:
        await apod_setting.finish("NASA 每日天文一图定时任务未开启")
    next_run = (
        job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        if job.next_run_time else "未知"
    )
    await apod_setting.finish(
        f"NASA 每日天文一图定时任务已开启 | 下次发送时间: {next_run}"
    )


@apod_setting.assign("stop")
async def apod_stop(target: MsgTarget):
    await remove_apod_task(target)
    await apod_setting.finish("已关闭 NASA 每日天文一图定时任务")


@apod_setting.assign("start")
async def apod_start(send_time: Match[str], target: MsgTarget):
    if not send_time.available:
        await schedule_apod_task(default_time, target)
        await apod_setting.finish(
            f"已开启 NASA 每日天文一图定时任务,默认发送时间为 {default_time}"
        )
    time = send_time.result
    if not is_valid_time_format(time):
        await apod_setting.finish("时间格式不正确,请使用 HH:MM 格式")
    try:
        await schedule_apod_task(time, target)
        await apod_setting.finish(
            f"已开启 NASA 每日天文一图定时任务,发送时间为 {time}"
        )
    except Exception as e:
        logger.error(f"设置 NASA 每日天文一图定时任务时发生错误:{e}")
        await apod_setting.finish("设置 NASA 每日天文一图定时任务时发生错误")


@randomly_apod_command.handle()
async def randomly_apod_command_handle():
    data = await fetch_randomly_apod_data()
    if not data:
        await randomly_apod_command.finish("获取随机天文一图失败,请稍后再试。")
    if data.get("media_type") != "image" or "url" not in data:
        await randomly_apod_command.finish("随机到了天文视频")
    explanation = await translate_text_auto(data["explanation"])
    await UniMessage.image(url=data["url"]).send(
        reply_to=True,
        argot={
            "name": "randomly_apod_explanation",
            "segment": Text(explanation),
            "command": "简介",
            "expired_at": 360,
        },
    )


@date_apod_command.handle()
async def date_apod_command_handle(date: str):
    if not is_valid_date_format(date):
        await date_apod_command.finish("日期格式不正确," \
        "请使用 YYYY-MM-DD 格式," \
        "且日期需要在 1995-06-16 之后")
    data = await fetch_apod_data_by_date(date=date)
    if not data:
        await date_apod_command.finish("获取指定日期天文一图失败,请稍后再试。")
    if data.get("media_type") != "image" or "url" not in data:
        await date_apod_command.finish("指定日期的天文一图为视频")
    explanation = await translate_text_auto(data["explanation"])
    await UniMessage.image(url=data["url"]).send(
        reply_to=True,
        argot={
            "name": "date_apod_explanation",
            "segment": Text(explanation),
            "command": "简介",
            "expired_at": 360,
        },
    )
