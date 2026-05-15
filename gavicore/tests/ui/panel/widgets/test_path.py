#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from types import SimpleNamespace

from gavicore.ui.panel.widgets.path import FilesystemPathInput


def test_local_relative_current_directory_completions_keep_prefix(
    tmp_path, monkeypatch
):
    (tmp_path / "my-requests").mkdir()
    (tmp_path / "other.txt").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    widget = FilesystemPathInput()

    completions = widget._compute_completions("./")

    assert "./my-requests/" in completions
    assert "./other.txt" in completions


def test_local_relative_directory_completions_keep_prefix(tmp_path, monkeypatch):
    request_dir = tmp_path / "my-requests"
    request_dir.mkdir()
    (request_dir / "request.json").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    widget = FilesystemPathInput()

    completions = widget._compute_completions("./my-requests/")

    assert "./my-requests/request.json" in completions


def test_local_relative_partial_completions_keep_prefix(tmp_path, monkeypatch):
    (tmp_path / "my-requests").mkdir()
    monkeypatch.chdir(tmp_path)

    widget = FilesystemPathInput()

    completions = widget._compute_completions("./my")

    assert "./my-requests/" in completions


def test_local_relative_partial_without_dot_slash_matches_input(tmp_path, monkeypatch):
    (tmp_path / "my-requests").mkdir()
    monkeypatch.chdir(tmp_path)

    widget = FilesystemPathInput()

    completions = widget._compute_completions("my")

    assert f"my-requests{os.sep}" in completions


def test_local_directory_mode_excludes_files(tmp_path, monkeypatch):
    (tmp_path / "my-requests").mkdir()
    (tmp_path / "request.json").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    widget = FilesystemPathInput(mode="directory")

    completions = widget._compute_completions("./")

    assert "./my-requests/" in completions
    assert "./request.json" not in completions


def test_local_hidden_paths_require_dot_prefix(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("", encoding="utf-8")
    (tmp_path / "regular.txt").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    widget = FilesystemPathInput()

    assert "./.env" not in widget._compute_completions("./")
    assert "./.env" in widget._compute_completions("./.e")


def test_local_absolute_directory_completions_keep_absolute_prefix(tmp_path):
    request_dir = tmp_path / "my-requests"
    request_dir.mkdir()
    (request_dir / "request.json").write_text("", encoding="utf-8")
    prefix = str(request_dir) + os.sep

    widget = FilesystemPathInput()

    completions = widget._compute_completions(prefix)

    assert str(request_dir / "request.json") in completions


def test_remote_completions_use_remote_paths():
    widget = FilesystemPathInput(protocol="memory", must_exist=False)
    widget.filesystem.mkdir("/requests")
    widget.filesystem.touch("/requests/request.json")
    widget.filesystem.touch("/other.txt")

    completions = widget._compute_completions("/requests/")

    assert "/requests/request.json" in completions


def test_input_change_keeps_previous_options_when_no_new_completions(
    tmp_path, monkeypatch
):
    (tmp_path / "my-requests").mkdir()
    monkeypatch.chdir(tmp_path)
    widget = FilesystemPathInput()

    widget._on_input_change(SimpleNamespace(new="./"))
    first_completions = widget._autocomplete.options

    widget._on_input_change(SimpleNamespace(new="./missing"))

    assert first_completions == widget._autocomplete.options
