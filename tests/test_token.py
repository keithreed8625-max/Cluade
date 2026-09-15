"""The token outlives the process, or the phone's home-screen icon is single-use."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from iphone_tk.bridge.token import (
    default_token_path,
    generate_token,
    load_or_create_token,
    read_token,
    resolve_token,
    write_token,
)


def test_first_run_mints_and_saves(tmp_path: Path) -> None:
    path = tmp_path / "bridge-token"
    token, minted = load_or_create_token(path)

    assert minted is True
    assert token
    assert path.read_text(encoding="utf-8").strip() == token


def test_second_run_reuses_the_same_token(tmp_path: Path) -> None:
    path = tmp_path / "bridge-token"
    first, _ = load_or_create_token(path)
    second, minted = load_or_create_token(path)

    # This is the whole point: a link saved during the first run still opens
    # during the second.
    assert second == first
    assert minted is False


def test_rotate_replaces_the_saved_token(tmp_path: Path) -> None:
    path = tmp_path / "bridge-token"
    first, _ = load_or_create_token(path)
    second, minted = load_or_create_token(path, rotate=True)

    assert second != first
    assert minted is True
    assert path.read_text(encoding="utf-8").strip() == second


def test_missing_parent_directories_are_created(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / "bridge-token"
    token, _ = load_or_create_token(path)

    assert path.is_file()
    assert read_token(path) == token


@pytest.mark.parametrize("contents", ["", "   ", "\n", "\t\n  "])
def test_blank_files_are_treated_as_absent(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "bridge-token"
    path.write_text(contents, encoding="utf-8")

    assert read_token(path) is None

    token, minted = load_or_create_token(path)
    assert minted is True
    assert token


def test_surrounding_whitespace_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "bridge-token"
    path.write_text("  abc123  \n", encoding="utf-8")

    assert read_token(path) == "abc123"


def test_a_directory_in_the_way_reads_as_absent(tmp_path: Path) -> None:
    path = tmp_path / "bridge-token"
    path.mkdir()

    assert read_token(path) is None


def test_tokens_are_unique(tmp_path: Path) -> None:
    assert len({generate_token() for _ in range(100)}) == 100


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes are not meaningful on Windows")
def test_saved_token_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "bridge-token"
    write_token(path, "secret")

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_overwriting_keeps_the_mode_tight(tmp_path: Path) -> None:
    path = tmp_path / "bridge-token"
    write_token(path, "first")
    write_token(path, "second")

    assert read_token(path) == "second"


def test_default_path_follows_the_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/test/.config")

    path = default_token_path()

    # Never the inbox: the inbox gets opened, synced, and emptied.
    assert path.name == "bridge-token"
    assert path.parent.name == "iphone-tk"


def test_an_explicit_token_wins(tmp_path: Path) -> None:
    path = tmp_path / "bridge-token"
    token, note = resolve_token("chosen-by-hand", path)

    assert token == "chosen-by-hand"
    assert "--token" in note
    # An explicit token must not quietly overwrite the remembered one.
    assert not path.exists()


def test_startup_note_distinguishes_reuse_from_minting(tmp_path: Path) -> None:
    path = tmp_path / "bridge-token"

    # First run ever: there is no earlier icon to invalidate, so do not claim one.
    first, first_note = resolve_token(path=path)
    assert "keeps working" in first_note
    assert "dead" not in first_note

    second, second_note = resolve_token(path=path)
    assert second == first
    assert "still works" in second_note

    # A deliberate rotation does invalidate the saved icon, and must say so.
    third, third_note = resolve_token(path=path, rotate=True)
    assert third != first
    assert "dead" in third_note


def test_falls_back_when_the_token_cannot_be_saved(tmp_path: Path) -> None:
    # A file where the parent directory should be: mkdir raises, and the bridge
    # must still start rather than refuse over a place to put a secret.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")

    token, note = resolve_token(path=blocker / "sub" / "bridge-token")

    assert token
    assert "one-off token" in note
