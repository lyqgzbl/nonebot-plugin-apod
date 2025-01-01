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
[![Supported Adapters](https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin-adapters%2Fnonebot-plugin-send-anything-anywhere)](https://registry.nonebot.dev/plugin/nonebot-plugin-send-anything-anywhere:nonebot_plugin_saa)

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

## 配置项

配置方式：直接在 NoneBot 全局配置文件中添加以下配置项即可

### apod_api_key [必填]

- 类型：`str`
- 默认值：`None`
- 说明：用于获取每日天文一图的 NASA API Key

### apod_default_send_time [选填]

- 类型：`str`
- 默认值：`13:00`
- 说明：每日天文一图的默认发送时间