from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    apod_api_key: Optional[str] = None
    apod_default_send_time: str = "13:00"
    apod_baidu_trans: bool = False
    apod_baidu_trans_appid: Optional[int] = None
    apod_baidu_trans_api_key: Optional[str] = None
    apod_reply_is_iamge: bool = True