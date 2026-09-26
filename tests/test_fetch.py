import json
from datetime import date

import pytest

import httpx
import respx


SAMPLE_APOD = {
    "title": "Test Nebula",
    "explanation": "A beautiful nebula.",
    "url": "https://apod.nasa.gov/image.jpg",
    "hdurl": "https://apod.nasa.gov/image_hd.jpg",
    "date": "2023-10-01",
    "media_type": "image",
}


@pytest.fixture(autouse=True)
def fixed_date(monkeypatch):
    utils = _get_utils()
    monkeypatch.setattr(utils, "nasa_today", lambda: date(2023, 10, 1))
    monkeypatch.setattr(utils.random, "randint", lambda low, high: high)
    monkeypatch.setattr(utils, "mirror_url", None)
    monkeypatch.setattr(utils, "mirror_api_key", None)


def _get_utils():
    import nonebot_plugin_apod.utils as utils

    return utils


class TestFetchApodDataByDate:
    @respx.mock
    async def test_returns_dict_response(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(
            return_value=httpx.Response(200, json=SAMPLE_APOD)
        )
        result = await utils.fetch_apod_data_by_date("2023-10-01")
        assert result is not None
        assert result["title"] == "Test Nebula"

    @respx.mock
    async def test_returns_list_response(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(
            return_value=httpx.Response(200, json=[SAMPLE_APOD])
        )
        result = await utils.fetch_apod_data_by_date("2023-10-01")
        assert result is not None
        assert result["title"] == "Test Nebula"

    @respx.mock
    async def test_returns_none_on_empty_list(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{utils.NASA_API_URL}/231001").mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await utils.fetch_apod_data_by_date("2023-10-01")
        assert result is None

    @respx.mock
    async def test_returns_none_on_http_error(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        result = await utils.fetch_apod_data_by_date("2023-10-01")
        assert result is None

    @respx.mock
    async def test_returns_none_on_request_error(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(side_effect=httpx.ConnectError("fail"))
        result = await utils.fetch_apod_data_by_date("2023-10-01")
        assert result is None


class TestFetchRandomlyApodData:
    @respx.mock
    async def test_returns_first_from_list(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(
            return_value=httpx.Response(200, json=[SAMPLE_APOD])
        )
        result = await utils.fetch_randomly_apod_data()
        assert result is not None
        assert result["title"] == "Test Nebula"

    @respx.mock
    async def test_returns_dict_directly(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(
            return_value=httpx.Response(200, json=SAMPLE_APOD)
        )
        result = await utils.fetch_randomly_apod_data()
        assert result is not None
        assert result["title"] == "Test Nebula"

    @respx.mock
    async def test_returns_none_on_empty_list(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{utils.NASA_API_URL}/231001").mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await utils.fetch_randomly_apod_data()
        assert result is None

    @respx.mock
    async def test_returns_none_on_http_error(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        result = await utils.fetch_randomly_apod_data()
        assert result is None


class TestFetchApodData:
    @respx.mock
    async def test_success_returns_true(self, tmp_path, monkeypatch):
        utils = _get_utils()
        cache_file = tmp_path / "apod.json"
        monkeypatch.setattr(utils, "apod_cache_json", cache_file)
        respx.get(utils.NASA_API_URL).mock(
            return_value=httpx.Response(200, json=SAMPLE_APOD)
        )
        result = await utils.fetch_apod_data()
        assert result is True
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["title"] == "Test Nebula"

    @respx.mock
    async def test_http_error_returns_false(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(
            return_value=httpx.Response(500, text="error")
        )
        result = await utils.fetch_apod_data()
        assert result is False

    @respx.mock
    async def test_connect_error_returns_false(self):
        utils = _get_utils()
        respx.get(utils.NASA_API_URL).mock(side_effect=httpx.ConnectError("fail"))
        result = await utils.fetch_apod_data()
        assert result is False


@respx.mock
async def test_date_collection_selects_exact_match():
    utils = _get_utils()
    route = respx.get(utils.NASA_API_URL).mock(
        return_value=httpx.Response(
            200, json=[dict(SAMPLE_APOD, date="2023-10-02"), SAMPLE_APOD]
        )
    )
    result = await utils.fetch_apod_data_by_date("2023-10-01")
    assert result["date"] == "2023-10-01"
    assert result["url"] == SAMPLE_APOD["hdurl"]
    assert route.calls.last.request.url.params["date"] == "2023-10-01"


@respx.mock
async def test_date_route_when_collection_ignores_filter():
    utils = _get_utils()
    respx.get(utils.NASA_API_URL).mock(
        return_value=httpx.Response(200, json=[dict(SAMPLE_APOD, date="2026-09-26")])
    )
    detail = respx.get(f"{utils.NASA_API_URL}/231001").mock(
        return_value=httpx.Response(200, json=SAMPLE_APOD)
    )
    result = await utils.fetch_apod_data_by_date("2023-10-01")
    assert result["date"] == "2023-10-01"
    assert detail.called


@respx.mock
async def test_wrong_detail_date_rejected():
    utils = _get_utils()
    wrong = dict(SAMPLE_APOD, date="2023-10-02")
    respx.get(utils.NASA_API_URL).mock(return_value=httpx.Response(200, json=[wrong]))
    respx.get(f"{utils.NASA_API_URL}/231001").mock(
        return_value=httpx.Response(200, json=wrong)
    )
    assert await utils.fetch_apod_data_by_date("2023-10-01") is None


@respx.mock
async def test_malformed_today_does_not_overwrite_cache(tmp_path, monkeypatch):
    utils = _get_utils()
    cache = tmp_path / "apod.json"
    cache.write_text("existing")
    monkeypatch.setattr(utils, "apod_cache_json", cache)
    respx.get(utils.NASA_API_URL).mock(return_value=httpx.Response(200, text="<html>"))
    assert await utils.fetch_apod_data() is False
    assert cache.read_text() == "existing"


@respx.mock
async def test_mirror_keeps_local_image_url():
    utils = _get_utils()
    mirror = "https://mirror.example/v1/apod"
    record = dict(SAMPLE_APOD, url="https://mirror.example/static/apod/2023-10-01.jpg")
    route = respx.get(mirror).mock(return_value=httpx.Response(200, json=record))
    result = await utils.fetch_apod_data_by_date_from_mirror(
        mirror, "secret", "2023-10-01"
    )
    assert result["url"] == record["url"]
    assert route.calls.last.request.headers["Authorization"] == "Bearer secret"


@respx.mock
async def test_random_uses_sampled_date_and_mirror(monkeypatch):
    utils = _get_utils()
    mirror = "https://mirror.example/v1/apod"
    monkeypatch.setattr(utils, "mirror_url", mirror)
    monkeypatch.setattr(utils, "mirror_api_key", "secret")
    route = respx.get(mirror).mock(return_value=httpx.Response(200, json=SAMPLE_APOD))
    result = await utils.fetch_randomly_apod_data()
    assert result["date"] == "2023-10-01"
    assert route.calls.last.request.url.params["date"] == "2023-10-01"
    assert "count" not in route.calls.last.request.url.params


@respx.mock
async def test_random_failures_are_bounded():
    utils = _get_utils()
    route = respx.get(utils.NASA_API_URL).mock(
        return_value=httpx.Response(503, text="unavailable")
    )
    assert await utils.fetch_randomly_apod_data() is None
    assert route.call_count == 3


@respx.mock
async def test_wrong_mirror_date_rejected():
    utils = _get_utils()
    mirror = "https://mirror.example/v1/apod"
    respx.get(mirror).mock(
        return_value=httpx.Response(200, json=dict(SAMPLE_APOD, date="2023-10-02"))
    )
    result = await utils.fetch_apod_data_by_date_from_mirror(
        mirror, "secret", "2023-10-01"
    )
    assert result is None
