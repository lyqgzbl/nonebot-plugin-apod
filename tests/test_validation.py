import pytest
from datetime import datetime


class TestIsValidTimeFormat:
    @pytest.fixture(autouse=True)
    def _load(self):
        from nonebot_plugin_apod.utils import is_valid_time_format

        self.is_valid_time_format = is_valid_time_format

    @pytest.mark.parametrize(
        "time_str",
        ["0:00", "9:30", "13:00", "23:59", "12:05"],
    )
    def test_valid_times(self, time_str):
        assert self.is_valid_time_format(time_str) is True

    @pytest.mark.parametrize(
        "time_str",
        ["24:00", "25:00", "12:60", "23:61", "-1:00"],
    )
    def test_out_of_range(self, time_str):
        assert self.is_valid_time_format(time_str) is False

    @pytest.mark.parametrize(
        "time_str",
        ["", "abc", "12", "12:00:00", ":30", "12:"],
    )
    def test_invalid_format(self, time_str):
        assert self.is_valid_time_format(time_str) is False


class TestIsValidDateFormat:
    @pytest.fixture(autouse=True)
    def _load(self):
        from nonebot_plugin_apod.utils import is_valid_date_format

        self.is_valid_date_format = is_valid_date_format

    def test_first_apod_date(self):
        assert self.is_valid_date_format("1995-06-16") is True

    def test_date_before_first_apod(self):
        assert self.is_valid_date_format("1995-06-15") is False

    def test_normal_date(self):
        assert self.is_valid_date_format("2023-10-01") is True

    def test_future_date(self):
        assert self.is_valid_date_format("2099-01-01") is False

    def test_today(self):
        today = datetime.now().strftime("%Y-%m-%d")
        assert self.is_valid_date_format(today) is True

    @pytest.mark.parametrize(
        "date_str",
        ["", "abc", "2023/10/01", "10-01-2023", "2023-13-01", "2023-02-30"],
    )
    def test_invalid_format(self, date_str):
        assert self.is_valid_date_format(date_str) is False
