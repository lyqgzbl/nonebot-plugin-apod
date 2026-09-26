<!-- markdownlint-disable MD033 MD036 MD041 -->

<div align="center">

<a href="https://v2.nonebot.dev/store">
  <img src="https://raw.githubusercontent.com/A-kirami/nonebot-plugin-template/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo">
</a>

<p>
  <img src="https://raw.githubusercontent.com/lgc-NB2Dev/readme/main/template/plugin.svg" alt="NoneBotPluginText">
</p>

# nonebot-plugin-apod

_✨ 每日天文一图 ✨_

![License](https://img.shields.io/pypi/l/nonebot-plugin-apod)
![PyPI](https://img.shields.io/pypi/v/nonebot-plugin-apod.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)  
[![NoneBot Registry](https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin%2Fnonebot-plugin-apod)](https://registry.nonebot.dev/plugin/nonebot-plugin-apod:nonebot_plugin_apod)
[![Supported Adapters](https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin-adapters%2Fnonebot-plugin-alconna)](https://registry.nonebot.dev/plugin/nonebot-plugin-alconna:nonebot_plugin_alconna)

</div>

## 安装
使用nb-cli [推荐]
```shell
nb plugin install nonebot-plugin-apod
```
使用pip
```shell
pip install nonebot-plugin-apod
```

## 使用
命令需要加 [NoneBot 命令前缀](https://nonebot.dev/docs/appendices/config#command-start-和-command-separator) (默认为`/`)  
命令需要用户为 [SuperUsers](https://nonebot.dev/docs/appendices/config#superusers)  
使用命令`APOD`/`apod`触发插件  
命令选项`状态` 查询定时任务状态  
命令选项`关闭` 关闭定时任务  
命令选项`开启` 开启定时任务  

[以下命令无需用户为[SuperUsers](https://nonebot.dev/docs/appendices/config#superusers)]  
使用命令`今日天文一图`获取今日天文一图  
使用命令`随机天文一图`随机获得天文一图  
使用命令`指定日期天文一图`获取指定日期天文一图  


### 效果图

<details>
  <summary>点击展开</summary>

![example](https://raw.githubusercontent.com/lyqgzbl/nonebot-plugin-apod/main/example.png)

</details>

## 配置项

配置方式：直接在 NoneBot 全局配置文件中添加以下配置项即可

### apod_api_key [直连时必填]

- 类型：`str`
- 默认值：`None`
- 说明：用于获取每日天文一图的 [NASA API Key](https://api.nasa.gov/)。配置镜像地址和镜像密钥后可省略；镜像失败后的直连回退使用 `DEMO_KEY`。

### apod_default_send_time [选填]

- 类型：`str`
- 默认值：`13:00`
- 说明：每日天文一图的默认发送时间

### apod_infopuzzle [选填]

- 类型：`bool`
- 默认值：`True`
- 说明：是否将今日天文一图完整信息构造为信息拼图

### apod_infopuzzle_dark_mode [选填]

- 类型：`bool`
- 默认值：`False`
- 说明: 是否启用信息拼图的深色模式

### apod_baidu_trans [选填]

- 类型：`bool`
- 默认值：`False`
- 说明：是否使用[百度翻译](https://fanyi-api.baidu.com/)将天文一图描述翻译为中文

### apod_baidu_trans_appid [选填]

- 类型：`int`
- 默认值：`None`
- 说明：百度翻译 APP ID

### apod_baidu_trans_api_key [选填]

- 类型：`str`
- 默认值：`None`
- 说明：百度翻译 密钥

### apod_deepl_trans [选填]

- 类型：`bool`
- 默认值：`False`
- 说明：是否使用[DeepL 翻译](https://www.deepl.com/zh/products/api/)将天文一图描述翻译为中文

### apod_deepl_trans_api_key [选填]

- 类型：`str`
- 默认值：`None`
- 说明：DeepL 翻译 密钥

### apod_openai_trans [选填]

- 类型：`bool`
- 默认值：`False`
- 说明：是否使用兼容 OpenAI 接口规范的大模型（如 OpenAI / DeepSeek / Qwen / Ollama 等）将天文一图描述翻译为中文

### apod_openai_model_name [选填]

- 类型: `str | None`
- 默认值: `None`
- 说明: 使用的模型名称（如 `gpt-4o-mini`, `deepseek-chat`, `qwen-plus` 等）。若调用的接口无需传入模型参数（如部分自建代理），可保留 `None`

### apod_openai_api_key [选填]

- 类型: `str | None`
- 默认值：`None`
- 说明：OpenAI 兼容接口的 API Key / 密钥

### apod_openai_api_url [选填]

- 类型: `str`
- 默认值：`https://api.openai.com/v1`
- 说明：OpenAI 兼容接口的 Base API URL（如 DeepSeek 可填 `https://api.deepseek.com`，Qwen 可填 `https://dashscope.aliyuncs.com/compatible-mode/v1`）

> **注**：为保持向后兼容，旧版本的 `apod_qwen_trans`、`apod_qwen_mt_model_name`、`apod_qwen_mt_api_key` 和 `apod_qwen_mt_api_url` 配置项依然生效。

## NASA Science 主站迁移

直连使用 `https://science.nasa.gov/wp-json/wp/v2/apod-basic`。插件兼容对象和数组响应，严格匹配日期；集合接口未返回目标日期时，使用同端点下的 `YYMMDD` 日期路径。今日数据和缓存日期以 `America/New_York` 为准。

NASA 图片响应中的 `url` 可能指向文章页，因此插件将 `hdurl` 映射为内部图片 `url`，并将标题、说明和版权中的 HTML 转为纯文本。镜像响应的 `url` 保持不变，继续使用 apod-server 的图片缓存。视频仍提示为天文视频。

新端点的 `count=1` 实测返回最近多条记录，因此随机功能改为在 1995-06-16 至 NASA 当天之间随机选日期，再请求该日期；最多尝试三个日期。今日、指定日期和随机功能均支持镜像优先、NASA 直连回退。

镜像配置示例：

```dotenv
APOD_MIRROR_URL=https://your-apod-server.example/v1/apod
APOD_MIRROR_API_KEY=your_server_bearer_key
```

`APOD_MIRROR_URL` 是完整元数据接口地址，`APOD_MIRROR_API_KEY` 对应服务端 `API_AUTH_KEY`，不等同于 NASA API Key。启用高清原图时仍可能直接访问 NASA 图片 CDN。


### htmlrender 版本兼容

当前拼图使用 `md_to_pic` 接口，依赖限制为 `nonebot-plugin-htmlrender>=0.6.7,<0.7.0`。htmlrender 新版更改了公开接口，0.8 已移除该旧接口，不能直接升级到新版。若安装环境出现 `cannot import name 'md_to_pic'`，请在机器人项目中重新解析依赖并同步环境；使用 uv 的项目可执行：

```bash
uv add "nonebot-plugin-htmlrender>=0.6.7,<0.7.0"
uv sync
```

仅更新 APOD 源码不会自动调整已安装依赖。后续若迁移新版 htmlrender，需要同时适配渲染 API、返回值、Provider 和配置。
