import re
import json

from nonebot.rule import Rule
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot import require, get_plugin_config
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_htmlrender")
require("nonebot_plugin_apscheduler")
import nonebot_plugin_localstore as store
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_alconna import Args, Match, Option, Alconna, CommandMeta, on_alconna
from nonebot_plugin_alconna.uniseg import Target, UniMessage, MsgTarget

from .config import Config, get_cache_image, set_cache_image
from .apod import remove_apod_task, schedule_apod_task, fetch_apod_data, generate_apod_image, generate_job_id


#插件元数据
__plugin_meta__ = PluginMetadata(
    name="每日天文一图",
    description="定时发送 NASA 每日提供的天文图片",
    usage="/apod 状态; /apod 关闭; /apod 开启 13:30",
    type="application",
    homepage="https://github.com/lyqgzbl/nonebot-plugin-apod",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)


#加载配置
plugin_config = get_plugin_config(Config)
apod_infopuzzle = plugin_config.apod_infopuzzle
apod_cache_json = store.get_plugin_cache_file("apod.json")
task_config_file = store.get_plugin_data_file("apod_task_config.json")


#检查NASA API密钥是否配置
if not plugin_config.apod_api_key:
    logger.opt(colors=True).warning("<yellow>缺失必要配置项 'apod_api_key'，已禁用该插件</yellow>")
def is_enable() -> Rule:
    def _rule() -> bool:
        return bool(plugin_config.apod_api_key)
    return Rule(_rule)


#定义指令apod
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
    rule=is_enable(),
    aliases={"APOD"},
    permission=SUPERUSER,
    use_cmd_start=True,
)


#定义指令今日天文一图
apod = on_alconna(
    Alconna(
        "今日天文一图",
        meta=CommandMeta(
            description="获取今日天文一图",
            example="/今日天文一图",
        ),
    ),
    rule=is_enable(),
    use_cmd_start=True,
)


#检查时间格式是否正确
def is_valid_time_format(time_str: str) -> bool:
    if not re.match(r"^\d{1,2}:\d{2}$", time_str):
        return False
    try:
        hour, minute = map(int, time_str.split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except ValueError:
        return False


#处理指令今日天文一图
@apod.handle()
async def apod_handle():
    if not apod_cache_json.exists() and not await fetch_apod_data():
        await apod.finish("获取今日天文一图失败请稍后再试")
    data = json.loads(apod_cache_json.read_text())
    if data.get("media_type") != "image" or "url" not in data:
        await apod.finish("今日 NASA 提供的为天文视频")
    if apod_infopuzzle:
        cache_image = get_cache_image() or await generate_apod_image()
        if cache_image:
            await set_cache_image(cache_image)
            await UniMessage.image(raw=cache_image).send(reply_to=True)
        else:
            await apod.finish("发送今日的天文一图失败")
    else:
        await UniMessage.text("今日天文一图为").image(url=data["url"]).send(reply_to=True)


#处理指令apod status
@apod_setting.assign("status")
async def apod_status(event, target: MsgTarget):
    if not task_config_file.exists():
        await apod_setting.finish("NASA 每日天文一图定时任务未开启")
    try:
        with task_config_file.open("r", encoding="utf-8") as f:
            config = json.load(f)
        tasks = config.get("tasks", [])
    except Exception as e:
        await apod_setting.finish(f"加载任务配置时发生错误：{e}")
    if not tasks:
        await apod_setting.finish("NASA 每日天文一图定时任务未开启")
    current_target = target
    for task in tasks:
        target_data = task["target"]
        data_target = Target.load(target_data)
        if data_target == current_target:
            send_time = task["send_time"]
            job_id = generate_job_id(target)
            job = scheduler.get_job(job_id)
            if job:
                next_run = (
                    job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                    if job.next_run_time else "未知"
                )
                await apod_setting.finish(f"NASA 每日天文一图定时任务已开启 | 下次发送时间: {next_run}")
            else:
                await apod_setting.finish("NASA 每日天文一图定时任务未开启")
    await apod_setting.finish("NASA 每日天文一图定时任务未开启")


#处理指令apod stop
@apod_setting.assign("stop")
async def apod_stop(target: MsgTarget):
    remove_apod_task(target)
    await apod_setting.finish("已关闭 NASA 每日天文一图定时任务")


#处理指令apod start
@apod_setting.assign("start")
async def apod_start(send_time: Match[str], target: MsgTarget):
    if send_time.available:
        time = send_time.result
        if not is_valid_time_format(time):
            await apod_setting.send("时间格式不正确,请使用 HH:MM 格式")
        try:
            schedule_apod_task(time, target)
            await apod_setting.send(f"已开启 NASA 每日天文一图定时任务,发送时间为 {time}")
        except Exception as e:
            logger.error(f"设置 NASA 每日天文一图定时任务时发生错误:{e}")
            await apod_setting.finish("设置 NASA 每日天文一图定时任务时发生错误")
    else:
        default_time = plugin_config.apod_default_send_time
        schedule_apod_task(default_time, target)
        await apod_setting.finish(f"已开启 NASA 每日天文一图定时任务,默认发送时间为 {default_time}")
