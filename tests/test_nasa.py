def normalize_apod(*args, **kwargs):
    from nonebot_plugin_apod.nasa import normalize_apod as normalize

    return normalize(*args, **kwargs)


def plain_text(value):
    from nonebot_plugin_apod.nasa import plain_text as convert

    return convert(value)


def sample(**changes):
    return {
        "date": "2026-09-11",
        "title": "Stars &amp; Galaxies",
        "media_type": "image",
        "explanation": "<strong>Explanation:</strong> First.<p>Second &amp; last.</p>",
        "copyright": '<a href="https://example.org">Alice &amp; Bob</a>',
        "url": "https://science.nasa.gov/image-article/example/",
        "hdurl": "https://assets.science.nasa.gov/photo.jpg?w=2000&h=1000",
    } | changes


def test_normalizes_nasa_without_mutating_input():
    original = sample()
    result = normalize_apod(original, "2026-09-11", nasa=True)
    assert result["url"] == original["hdurl"]
    assert result["title"] == "Stars & Galaxies"
    assert result["explanation"] == "First. Second & last."
    assert result["copyright"] == "Alice & Bob"
    assert original["url"].startswith("https://science.nasa.gov/image-article/")


def test_missing_asset_rejected():
    assert normalize_apod(sample(hdurl=""), "2026-09-11", nasa=True) is None
    assert (
        normalize_apod(sample(hdurl="javascript:bad"), "2026-09-11", nasa=True) is None
    )


def test_video_preserves_playback_url():
    result = normalize_apod(
        sample(media_type="video", url="https://www.youtube.com/embed/test", hdurl=""),
        "2026-09-11",
        nasa=True,
    )
    assert result["url"] == "https://www.youtube.com/embed/test"


def test_video_article_preserves_video_notification():
    result = normalize_apod(sample(media_type="video"), "2026-09-11", nasa=True)
    assert result["media_type"] == "video"


def test_plain_text_ignores_scripts():
    assert plain_text("<script>bad()</script><p>Good &amp; safe</p>") == "Good & safe"


def test_announcements_removed():
    result = normalize_apod(
        sample(explanation="Explanation: Stars.<br>APOD's main NASA site is moving."),
        "2026-09-11",
        nasa=True,
    )
    assert result["explanation"] == "Stars."
