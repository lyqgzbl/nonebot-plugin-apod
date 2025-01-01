from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    apod_api_key: Optional[str] = None
    apod_default_send_time: str = "13:00"