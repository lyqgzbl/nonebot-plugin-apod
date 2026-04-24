import json

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
