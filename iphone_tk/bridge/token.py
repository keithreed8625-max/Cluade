"""Where the bridge's shared secret lives between runs.

A token minted fresh on every start makes the phone's home-screen icon
single-use: the icon's URL carries the token from the run it was saved in, so
the next start rejects it and shows the "almost there" page. Remembering the
token in a small file keeps that icon working until it is deliberately rotated.

Kept out of `server.py` on purpose. This is filesystem and permission handling,
which is worth testing directly rather than through an HTTP client.
"""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path
from typing import Optional, Tuple

# Long enough that guessing it on a LAN is hopeless, short enough to retype by
# hand into a Shortcut. 18 bytes is 24 URL-safe characters.
TOKEN_BYTES = 18


def generate_token() -> str:
    """Mint a new shared secret."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def default_token_path() -> Path:
    """The per-user file the token is remembered in.

    Deliberately not inside the inbox. The inbox is a folder people open, sync
    to other machines, and empty out; a credential should not ride along with
    the photos.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
    return Path(base) / "iphone-tk" / "bridge-token"


def read_token(path: Path) -> Optional[str]:
    """Return the remembered token, or None if there is not a usable one.

    A missing, unreadable, empty, or whitespace-only file all mean the same
    thing to the caller: there is nothing to reuse, so mint a new one.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return raw.strip() or None


def write_token(path: Path, token: str) -> None:
    """Save the token with owner-only permissions.

    Created at mode 0600 rather than written and then chmod'ed, which would
    leave a window where the secret is world-readable. On Windows the mode
    argument only controls the read-only bit, so the real protection there is
    that the file sits under the user's own LOCALAPPDATA.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        stat.S_IRUSR | stat.S_IWUSR,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")


def load_or_create_token(path: Path, rotate: bool = False) -> Tuple[str, bool]:
    """Return the remembered token, creating one on first run.

    :param path: File to remember it in.
    :param rotate: Discard any saved token and mint a replacement.
    :returns: The token, and whether it is newly minted — the caller warns when
        it is, because a new token silently breaks every saved link.
    :raises OSError: The token could not be written. Callers are expected to
        carry on with a one-off token rather than refuse to start.
    """
    if not rotate:
        existing = read_token(path)
        if existing is not None:
            return existing, False

    token = generate_token()
    write_token(path, token)
    return token, True


def resolve_token(
    explicit: Optional[str] = None,
    path: Optional[Path] = None,
    rotate: bool = False,
) -> Tuple[str, str]:
    """Decide which token the bridge runs with, and how to explain that at startup.

    The phone bakes the token into its home-screen link, so whether the token
    changed is the most useful thing to say when the bridge starts: it is the
    difference between "tap the icon" and "the icon is dead, re-add it".

    Lives here rather than in the CLI so it can be tested without importing the
    USB stack, which the test environment deliberately does without.
    """
    if explicit:
        return explicit, "  Using the token passed with --token."

    path = path or default_token_path()
    # Checked before the write, so a first run can be told apart from a rotation.
    replaced = read_token(path) is not None

    try:
        token, minted = load_or_create_token(path, rotate=rotate)
    except OSError as exc:
        # An unwritable config folder must not stop the bridge from running.
        # Fall back to a throwaway token, but be explicit that it will not last.
        return generate_token(), (
            f"  Could not save a token to {path}: {exc}\n"
            "  Using a one-off token, so this link dies when the bridge restarts."
        )

    if not minted:
        return token, (
            f"  Reusing the saved token from {path}\n"
            "  An existing home-screen icon still works — no need to re-add it."
        )
    if replaced:
        return token, (
            f"  New token saved to {path}\n"
            "  The previous link is now dead — re-add this one to the home screen."
        )
    return token, (
        f"  Token saved to {path}\n"
        "  It is reused on every start, so the home-screen icon keeps working."
    )
