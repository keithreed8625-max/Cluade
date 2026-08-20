"""Where uploads land, and the rules that keep them inside the inbox.

This module deliberately has no web framework in it: the filename and path
handling is where the security-relevant bugs live, so it is written as plain
functions that can be tested directly.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Windows reserves these regardless of extension; a file named CON.txt is unwritable.
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# Anything outside this set is replaced. Excludes the path separators and the
# characters Windows rejects outright: <>:"/\|?*
_ALLOWED = re.compile(r"[^A-Za-z0-9._ -]")

MAX_STEM = 80


def safe_filename(raw: Optional[str], fallback_ext: str = ".bin") -> str:
    """Reduce a client-supplied filename to something safe to join onto a directory.

    Guarantees the result contains no path separators, no parent references, and
    no Windows-reserved name — so `inbox / safe_filename(x)` always stays inside
    `inbox`, whatever the phone (or anything else on the network) sends.
    """
    candidate = (raw or "").strip()

    # Take the last path component under both separators before anything else,
    # so "../../etc/passwd" and "..\\..\\windows\\x" both collapse to a leaf.
    candidate = candidate.replace("\\", "/").rsplit("/", 1)[-1]

    # Normalize away lookalike Unicode that could reintroduce separators.
    candidate = unicodedata.normalize("NFKC", candidate)
    candidate = _ALLOWED.sub("_", candidate)

    # Strip leading dots so "..", ".", and dotfiles cannot appear.
    candidate = candidate.lstrip(". ")
    # Windows silently drops trailing dots and spaces; do it explicitly instead.
    candidate = candidate.rstrip(". ")

    if not candidate:
        return f"upload-{secrets.token_hex(4)}{fallback_ext}"

    stem, dot, ext = candidate.rpartition(".")
    if not dot:
        stem, ext = candidate, fallback_ext.lstrip(".")

    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"{stem}_file"

    stem = stem[:MAX_STEM] or f"upload-{secrets.token_hex(4)}"
    return f"{stem}.{ext}" if ext else stem


def timestamped(name: str, moment: Optional[datetime] = None) -> str:
    """Prefix a name with a sortable UTC timestamp so uploads never collide."""
    moment = moment or datetime.now(timezone.utc)
    return f"{moment.strftime('%Y%m%d-%H%M%S')}-{name}"


@dataclass(frozen=True)
class InboxItem:
    """One thing the phone sent."""

    path: Path
    kind: str
    size: int


class Inbox:
    """A directory that receives uploads, with every write forced to stay inside it."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, filename: str) -> Path:
        """Join an already-sanitized filename and verify it did not escape."""
        target = (self.root / filename).resolve()
        # Defence in depth: even if safe_filename regressed, refuse to write out.
        if target.parent != self.root:
            raise ValueError(f"Refusing to write outside the inbox: {filename!r}")
        return target

    def _unique(self, filename: str) -> Path:
        """Resolve to a path that does not exist yet.

        The timestamp prefix only has one-second resolution, so a Shortcut
        sharing several photos at once would otherwise overwrite its own
        uploads. Suffix with a counter until the name is free.
        """
        target = self._resolve(filename)
        if not target.exists():
            return target

        stem, dot, ext = filename.rpartition(".")
        if not dot:
            stem, ext = filename, ""
        for counter in range(1, 1000):
            candidate = f"{stem}-{counter}{'.' + ext if ext else ''}"
            target = self._resolve(candidate)
            if not target.exists():
                return target
        # Pathological: fall back to a random name rather than dropping the upload.
        return self._resolve(f"{stem}-{secrets.token_hex(4)}{'.' + ext if ext else ''}")

    def write_bytes(self, filename: Optional[str], data: bytes, kind: str = "file") -> InboxItem:
        target = self._unique(timestamped(safe_filename(filename)))
        target.write_bytes(data)
        return InboxItem(path=target, kind=kind, size=len(data))

    def write_text(self, text: str, kind: str = "text", suffix: str = ".txt") -> InboxItem:
        target = self._unique(timestamped(safe_filename(f"note{suffix}")))
        target.write_text(text, encoding="utf-8")
        return InboxItem(path=target, kind=kind, size=len(text.encode("utf-8")))

    def list_items(self) -> list[Path]:
        return sorted(p for p in self.root.iterdir() if p.is_file())


def constant_time_match(supplied: Optional[str], expected: str) -> bool:
    """Compare tokens without leaking their contents through timing."""
    if not supplied:
        return False
    return secrets.compare_digest(supplied, expected)
