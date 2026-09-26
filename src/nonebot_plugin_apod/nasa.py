"""Normalize NASA Science data to the plugin's existing APOD contract."""

import re
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

NASA_API_URL = "https://science.nasa.gov/wp-json/wp/v2/apod-basic"


def nasa_today() -> date:
    return datetime.now(ZoneInfo("America/New_York")).date()


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag in {"p", "br", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        if tag in {"p", "div"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    parser = _Text()
    parser.feed(value)
    return " ".join("".join(parser.parts).split())


def valid_media(
    value: object, permalink: object = None, *, allow_article: bool = False
) -> bool:
    if (
        not isinstance(value, str)
        or not value.strip()
        or (not allow_article and value == permalink)
    ):
        return False
    try:
        url = urlsplit(value)
        return (
            url.scheme in {"http", "https"}
            and bool(url.hostname)
            and url.username is None
            and not (
                not allow_article
                and url.hostname == "science.nasa.gov"
                and url.path.startswith("/image-article/")
            )
        )
    except ValueError:
        return False


def normalize_apod(payload: object, expected_date: str, *, nasa: bool) -> dict | None:
    records = payload if isinstance(payload, list) else [payload]
    for record in records:
        if not isinstance(record, dict) or record.get("date") != expected_date:
            continue
        result = _normalize_record(record, nasa=nasa)
        if result is not None:
            return result
    return None


def _normalize_record(record: dict, *, nasa: bool) -> dict | None:
    kind = record.get("media_type")
    media = record.get("hdurl") if nasa and kind == "image" else record.get("url")
    if kind not in {"image", "video"} or not valid_media(
        media, record.get("permalink"), allow_article=kind == "video"
    ):
        return None
    title = plain_text(record.get("title")) if nasa else record.get("title")
    explanation = record.get("explanation")
    if nasa:
        explanation = plain_text(explanation)
        explanation = re.sub(r"^Explanation:\s*", "", explanation, flags=re.I)
        explanation = re.split(
            r"APOD['’]s (?:email for image submissions|main NASA site)"
            r"|Tomorrow['’]s picture:",
            explanation,
            maxsplit=1,
            flags=re.I,
        )[0].strip()
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(explanation, str) or not explanation.strip():
        return None
    result = dict(record, title=title, explanation=explanation, url=media)
    if nasa:
        result["copyright"] = plain_text(record.get("copyright"))
        result["service_version"] = "v1"
        result.pop("basic_html", None)
    if kind == "image" and not valid_media(result.get("hdurl")):
        result["hdurl"] = media
    return result
