import re

from nonebot import require, get_plugin_config
from nonebot.rule import Rule
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_saa")
require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_saa import SaaTarget, enable_auto_select_bot
from nonebot_plugin_alconna import Args, Match, Option, Alconna, CommandMeta, on_alconna

from .config import Config
from .apod import send_apod, remove_apod_task, schedule_apod_task


__plugin_meta__ = PluginMetadata(
    name="每日天文一图",
    description="定时发送 NASA 每日提供的天文图片",
    usage="/apod 状态; /apod 关闭; /apod 开启 13:30",
    type="application",
    homepage="https://github.com/lyqgzbl/nonebot-plugin-apod",
    config=Config,
    supported_adapters=inherit_supported_adapters(
		"nonebot_plugin_alconna", "nonebot_plugin_saa"
    ),
)


enable_auto_select_bot()
plugin_config = get_plugin_config(Config)
if not plugin_config.nasa_api_key:
    logger.opt(colors=True).warning("<yellow>缺失必要配置项 'nasa_api_key'，已禁用该插件</yellow>")
def is_enable() -> Rule:
    def _rule() -> bool:
        return bool(plugin_config.nasa_api_key)
    return Rule(_rule)


apod = on_alconna(
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
    rule=is_enable(),
    aliases={"APOD"},
    permission=SUPERUSER,
    use_cmd_start=True,
)


def is_valid_time_format(time_str: str) -> bool:
    if not re.match(r"^\d{1,2}:\d{2}$", time_str):
        return False
    try:
        hour, minute = map(int, time_str.split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except ValueError:
        return False


@apod.assign("status")
async def apod_status():
    job = scheduler.get_job("send_apod_task")
    if job:
        next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "未知"
        await apod.finish(f"NASA 每日天文一图定时任务已开启,下次发送时间为 {next_run}")
    await apod.finish(" NASA 每日天文一图定时任务未开启")


@apod.assign("stop")
async def apod_stop():
    remove_apod_task()
    await apod.finish("已关闭 NASA 每日天文一图定时任务")


@apod.assign("start")
async def apod_start(send_time: Match[str], target: SaaTarget):
    if send_time.available:
        time = send_time.result
        if not is_valid_time_format(time):
            await apod.send("时间格式不正确,请使用 HH:MM 格式")
        try:
            schedule_apod_task(time, target)
            await apod.send(f"已开启 NASA 每日天文一图定时任务,发送时间为 {time}")
        except Exception as e:
            logger.error(f"设置 NASA 每日天文一图定时任务时发生错误:{e}")
            await apod.finish("设置 NASA 每日天文一图定时任务时发生错误")
    else:
        default_time = plugin_config.default_apod_send_time
        schedule_apod_task(default_time, target)
        await apod.finish(f"已开启 NASA 每日天文一图定时任务,默认发送时间为 {default_time}")