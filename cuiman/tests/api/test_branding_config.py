"""Branding participates in the existing client settings workflow."""

import os

import pytest
from pydantic_settings import SettingsConfigDict

from cuiman import Client, ClientConfig
from cuiman.api.branding import AppBranding, AppEmojiIcon, AppImageIcon


@pytest.fixture(autouse=True)
def clear_environment(monkeypatch):
    for name in os.environ:
        if name.startswith("EOZILLA_"):
            monkeypatch.delenv(name)


def test_branding_defaults_are_independent_and_not_persisted_when_empty():
    first = ClientConfig()
    second = ClientConfig()
    assert first.branding == AppBranding()
    assert "branding" not in first.to_file_dict()
    first.branding.title = "Changed"
    assert second.branding.title is None


def test_branding_profile_round_trip(tmp_path):
    path = tmp_path / "config"
    branding = AppBranding(title="Sen4CAP", icon=AppImageIcon(url="./logo.svg"))
    config = ClientConfig(branding=branding)
    config.write(path)
    restored = ClientConfig.from_file(path)
    assert restored.branding == branding
    assert restored.to_file_dict()["branding"] == {
        "title": "Sen4CAP",
        "icon": {"url": "./logo.svg"},
    }


def test_local_branding_profile_round_trip_and_source_override(tmp_path):
    profile = tmp_path / "config"
    branding = AppBranding(
        favicon=tmp_path / "favicon.svg",
        icon=AppImageIcon(path=tmp_path / "logo.svg"),
    )
    ClientConfig(branding=branding).write(profile)
    assert ClientConfig.from_file(profile).branding == branding
    overridden = ClientConfig.create(
        config_path=profile,
        branding={
            "favicon": {"url": "./favicon.svg"},
            "icon": {"url": "./logo.svg"},
        },
    )
    assert overridden.branding == AppBranding(
        favicon=AppImageIcon(url="./favicon.svg"), icon=AppImageIcon(url="./logo.svg")
    )


def test_branding_merges_profile_environment_and_keywords(tmp_path, monkeypatch):
    path = tmp_path / "config"
    ClientConfig(
        branding=AppBranding(
            title="Profile", favicon="./favicon.svg", icon=AppEmojiIcon(emoji="🦖")
        )
    ).write(path)
    monkeypatch.setenv("EOZILLA_BRANDING__TITLE", "Environment")
    monkeypatch.setenv("EOZILLA_BRANDING__ICON__URL", "./logo.svg")
    config = ClientConfig.create(config_path=path, branding={"title": "Explicit"})
    assert config.branding == AppBranding(
        title="Explicit", favicon="./favicon.svg", icon=AppImageIcon(url="./logo.svg")
    )


def test_branding_defaults_can_be_overridden_by_applications(tmp_path):
    class ApplicationConfig(ClientConfig):
        branding: AppBranding = AppBranding(
            title="Sen4CAP", icon=AppEmojiIcon(emoji="🌍")
        )

    config = ApplicationConfig.create(
        config_path=tmp_path / "missing", branding={"icon": {"url": "./logo.svg"}}
    )
    assert config.branding == AppBranding(
        title="Sen4CAP", icon=AppImageIcon(url="./logo.svg")
    )
    original = ApplicationConfig.create(config_path=tmp_path / "missing")
    snapshot = ApplicationConfig.create(config=original, branding={"title": "Override"})
    assert snapshot.branding.title == "Override"
    assert original.branding.title == "Sen4CAP"


@pytest.mark.parametrize("selection", ["implicit", "explicit", "changed"])
def test_application_branding_defaults_are_omitted_from_profiles(tmp_path, selection):
    class ApplicationConfig(ClientConfig):
        branding: AppBranding = AppBranding(
            title="Sen4CAP",
            favicon=tmp_path / "favicon.ico",
            icon=AppImageIcon(path=tmp_path / "icon.png"),
        )

    config = ApplicationConfig.new_instance()
    if selection != "implicit":
        config = ApplicationConfig.new_instance(branding=config.branding.model_copy())
    if selection == "changed":
        config.branding.title = "Custom title"

    profile = config.write(tmp_path / "config")
    saved = ApplicationConfig.read_file_data(profile)
    assert saved is not None
    if selection == "changed":
        assert saved["branding"] == config.branding.model_dump(
            mode="json", exclude_none=True
        )
    else:
        assert "branding" not in saved
    restored = ApplicationConfig.from_file(profile)
    assert restored is not None
    assert restored.branding == config.branding


def test_client_accepts_branding_setting(tmp_path):
    path = tmp_path / "branding.json"
    path.write_text('{"title":"Sen4CAP"}', encoding="utf-8")
    client = Client(
        config_path=tmp_path / "missing", branding=AppBranding.from_file(path)
    )
    assert client.config.branding.title == "Sen4CAP"


def test_application_prefix_and_dotenv_branding(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text("SEN4CAP_BRANDING__TITLE=Dotenv\n", encoding="utf-8")

    class ApplicationConfig(ClientConfig):
        model_config = SettingsConfigDict(
            env_prefix="SEN4CAP_", env_nested_delimiter="__", env_file=dotenv
        )

    config = ApplicationConfig.create(config_path=tmp_path / "missing")
    assert config.branding.title == "Dotenv"
    monkeypatch.setenv("SEN4CAP_BRANDING__TITLE", "Environment")
    assert (
        ApplicationConfig.create(config_path=tmp_path / "missing").branding.title
        == "Environment"
    )
