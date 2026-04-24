import pytest
import nonebot
from nonebug import NONEBOT_INIT_KWARGS


def pytest_configure(config: pytest.Config):
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~none",
        "apod_api_key": "TEST_NASA_KEY",
        "apod_default_send_time": "13:00",
        "apod_hd_image": False,
        "apod_baidu_trans": False,
        "apod_deepl_trans": False,
        "apod_qwen_trans": False,
        "apod_infopuzzle": True,
    }


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(after_nonebot_init):
    nonebot.require("nonebot_plugin_apod")
