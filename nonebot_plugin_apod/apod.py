import json
import random
import hashlib

import httpx
from nonebot.log import logger
import nonebot_plugin_localstore as store
from nonebot import get_plugin_config, get_bot
from nonebot_plugin_htmlrender import md_to_pic
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_saa import Text, Image, PlatformTarget, MessageFactory

from .config import Config, get_cache_image, set_cache_image, clear_cache_image


# 加载配置
plugin_config = get_plugin_config(Config)
nasa_api_key = plugin_config.apod_api_key
baidu_trans = plugin_config.apod_baidu_trans
NASA_API_URL = "https://api.nasa.gov/planetary/apod"
apod_is_reply_image = plugin_config.apod_reply_is_iamge
baidu_trans_appid = plugin_config.apod_baidu_trans_appid
baidu_trans_api_key = plugin_config.apod_baidu_trans_api_key
BAIDU_API_URL = "http://api.fanyi.baidu.com/api/trans/vip/translate"
apod_cache_json = store.get_plugin_cache_file("apod.json")
task_config_file = store.get_plugin_data_file("apod_task_config.json")


# 保存定时任务配置
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


# 加载定时任务配置
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
async def send_apod(target: PlatformTarget):
    if not apod_cache_json.exists():
        success = await fetch_apod_data()
        if not success:
            await Text("未能获取到今日的天文一图，请稍后再试。").send_to(target, bot=get_bot())
            return
    data = json.loads(apod_cache_json.read_text())
    cache_image = get_cache_image()
    if data.get("media_type") == "image" and "url" in data:
        if apod_is_reply_image:
            if cache_image is None:
                cache_image = await generate_apod_image()
                await set_cache_image(cache_image)
                if not cache_image:
                    await Text("发送今日的天文一图失败，请稍后再试。").send_to(target, bot=get_bot())
                    return
            await Image(cache_image).send_to(target, bot=get_bot())
        else:
            url = data["url"]
            await MessageFactory([Text("今日天文一图为"), Image(url)]).send_to(target, bot=get_bot())
    else:
        await Text("今日 NASA 提供的为天文视频").send_to(target, bot=get_bot())

# 设置每日天文一图定时任务
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


# 移除每日天文一图定时任务
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


# 翻译天文一图描述
async def translate_text(query, from_lang="auto", to_lang="zh", appid=baidu_trans_appid, api_key=baidu_trans_api_key):
    try:
        salt = random.randint(32768, 65536)
        sign = hashlib.md5(f"{appid}{query}{salt}{api_key}".encode()).hexdigest()
        payload = {
            "appid": appid,
            "q": query,
            "from": from_lang,
            "to": to_lang,
            "salt": salt,
            "sign": sign,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(BAIDU_API_URL, data=payload, headers=headers)
            result_all = response.text
            result = json.loads(result_all)
            if "trans_result" in result:
                return "\n".join([item["dst"] for item in result["trans_result"]])
            else:
                return f"Error: {result.get('error_msg', '未知错误')}"
    except Exception as e:
        logger.error(f"翻译时发生错误：{e}")
        return f"Exception occurred: {str(e)}"


# 将天文一图 JSON 文件转换为 Markdown
async def apod_json_to_md(apod_json):
    title = apod_json["title"]
    explanation = apod_json["explanation"]
    url = apod_json["url"]
    copyright = apod_json.get("copyright", "无")
    date = apod_json["date"]
    if baidu_trans:
        explanation = await translate_text(explanation)
    return f"""<h1 style="text-align:center;">今日天文一图</h1>

<h2 style="text-align:center;">{title}</h2>

<div style="text-align:center;">
    <img src="{url}" alt="APOD" style="max-width:100%; height:auto;">
</div>

<p style="text-align:center;">{explanation}</p>

<p style="text-align:left;">  版权：   {copyright}</p>
<p style="text-align:left;">  日期：   {date}</p>
"""

# 生成天文一图图片
async def generate_apod_image():
    try:
        if not apod_cache_json.exists():
            data = await fetch_apod_data()
            if not data:
                return None
        else:
            data = json.loads(apod_cache_json.read_text())
        md_content = await apod_json_to_md(data)
        img_bytes = await md_to_pic(md_content, width=800)
        return img_bytes
    except Exception as e:
        logger.error(f"生成 NASA APOD 图片时发生错误：{e}")
        return None


# 恢复定时任务
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
