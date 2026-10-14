#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path

import pytest
from pydantic import ValidationError

from cuiman.app import AppBranding, AppEmojiIcon, AppImageIcon


@pytest.mark.parametrize("value", [{"emoji": "🦖"}, {"url": "./logo.svg"}])
def test_branding_accepts_json_icon_alternatives(value):
    branding = AppBranding.model_validate({"icon": value})
    assert isinstance(branding.icon, (AppEmojiIcon, AppImageIcon))
    assert branding.model_dump(mode="json", exclude_none=True) == {"icon": value}


@pytest.mark.parametrize(
    "value",
    [
        {"title": ""},
        {"title": 42},
        {"favicon": ""},
        {"favicon": False},
        {"icon": {}},
        {"icon": "🦖"},
        {"icon": {"emoji": ""}},
        {"icon": {"url": ""}},
        {"icon": {"emoji": "🦖", "url": "./logo.svg"}},
        {"icon": {"url": "./logo.svg", "accessToken": "secret"}},
        {"auth": {"access_token": "secret"}},
        {"api_url": "https://processing.test"},
    ],
)
def test_branding_rejects_invalid_fields_and_credentials(value):
    with pytest.raises(ValidationError):
        AppBranding.model_validate(value)


@pytest.mark.parametrize("as_string", [False, True])
def test_branding_from_file_loads_utf8_and_preserves_relative_assets(
    tmp_path, as_string
):
    path = tmp_path / "branding.json"
    path.write_text(
        '{"title":"Sen4CAP","favicon":"./favicon.svg","icon":{"emoji":"🌍"}}',
        encoding="utf-8",
    )
    assert AppBranding.from_file(str(path) if as_string else path) == AppBranding(
        title="Sen4CAP", favicon="./favicon.svg", icon=AppEmojiIcon(emoji="🌍")
    )


def test_branding_from_file_expands_home(tmp_path, monkeypatch):
    path = tmp_path / "branding.json"
    path.write_text('{"title":"Sen4CAP"}', encoding="utf-8")
    monkeypatch.setattr(Path, "expanduser", lambda self: path)
    assert AppBranding.from_file("~/branding.json").title == "Sen4CAP"


@pytest.mark.parametrize("content", ['{"title":', '{"title":42}', "[]"])
def test_branding_from_file_propagates_validation_errors(tmp_path, content):
    path = tmp_path / "branding.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValidationError):
        AppBranding.from_file(path)


def test_branding_from_file_propagates_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        AppBranding.from_file(tmp_path / "missing.json")


def test_branding_omits_unspecified_and_null_fields():
    assert (
        AppBranding(title=None, favicon=None, icon=None).model_dump(
            mode="json", exclude_none=True
        )
        == {}
    )
