from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    nasa_api_key: Optional[str] = None
		default_apod_send_time: str = "13:00"