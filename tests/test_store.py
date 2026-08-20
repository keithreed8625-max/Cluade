"""Filename sanitation is the security boundary of the bridge, so it gets real tests."""

from pathlib import Path

import pytest

from iphone_tk.bridge.store import Inbox, constant_time_match, safe_filename, timestamped


@pytest.mark.parametrize(
    "hostile",
    [
        "../../etc/passwd",
        "..\\..\\Windows\\System32\\drivers\\etc\\hosts",
        "/absolute/path.txt",
        "C:\\Windows\\evil.exe",
        "....//....//x.txt",
        "..",
        ".",
        "",
        "   ",
    ],
)
def test_traversal_attempts_collapse_to_a_leaf_name(hostile: str) -> None:
    result = safe_filename(hostile)
    assert "/" not in result
    assert "\\" not in result
    assert not result.startswith(".")
    assert ".." not in result


def test_windows_reserved_names_are_escaped() -> None:
    assert safe_filename("CON.txt") == "CON_file.txt"
    assert safe_filename("lpt1.log").lower().startswith("lpt1_file")


def test_ordinary_names_survive_intact() -> None:
    assert safe_filename("IMG_0421.HEIC") == "IMG_0421.HEIC"
    assert safe_filename("my note-2.txt") == "my note-2.txt"


def test_long_names_are_truncated_but_keep_their_extension() -> None:
    result = safe_filename("a" * 300 + ".png")
    assert result.endswith(".png")
    assert len(result) < 120


def test_unicode_lookalikes_cannot_reintroduce_separators() -> None:
    # NFKC folds the fullwidth solidus; it must not survive as a real separator.
    assert "/" not in safe_filename("a\uff0f..\uff0fb.txt")


def test_timestamp_prefix_is_sortable() -> None:
    from datetime import datetime, timezone

    moment = datetime(2026, 8, 20, 13, 45, 1, tzinfo=timezone.utc)
    assert timestamped("x.txt", moment) == "20260820-134501-x.txt"


def test_inbox_writes_stay_inside_the_root(tmp_path: Path) -> None:
    inbox = Inbox(tmp_path / "inbox")
    item = inbox.write_bytes("../../escape.txt", b"data")
    assert item.path.parent == inbox.root
    assert item.path.read_bytes() == b"data"
    assert item.size == 4


def test_inbox_never_overwrites_within_the_same_second(tmp_path: Path) -> None:
    """A Shortcut sharing several photos at once must not lose any of them."""
    inbox = Inbox(tmp_path / "inbox")
    items = [inbox.write_bytes("IMG.HEIC", f"photo-{i}".encode()) for i in range(5)]

    paths = {item.path for item in items}
    assert len(paths) == 5, "uploads collided and overwrote each other"
    assert len(inbox.list_items()) == 5
    assert {p.read_bytes() for p in paths} == {f"photo-{i}".encode() for i in range(5)}


def test_inbox_text_notes_also_stay_distinct(tmp_path: Path) -> None:
    inbox = Inbox(tmp_path / "inbox")
    first, second = inbox.write_text("one"), inbox.write_text("two")
    assert first.path != second.path
    assert first.path.read_text() == "one"
    assert second.path.read_text() == "two"


def test_resolve_rejects_a_name_that_escapes(tmp_path: Path) -> None:
    inbox = Inbox(tmp_path / "inbox")
    with pytest.raises(ValueError):
        inbox._resolve("../outside.txt")


def test_token_comparison_rejects_empty_and_wrong() -> None:
    assert constant_time_match("secret", "secret")
    assert not constant_time_match("wrong", "secret")
    assert not constant_time_match(None, "secret")
    assert not constant_time_match("", "secret")
