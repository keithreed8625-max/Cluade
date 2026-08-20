"""The endpoint the phone sends to.

Run it on the PC. The phone can either open the page in Safari and pick photos,
or POST from a Shortcut — both hit the same /upload route.

Scope note: this listens on your local network in the clear. It is built for a
home LAN — a shared token, size limits, and an inbox that writes cannot escape.
Do not port-forward it to the internet; there is no TLS and no per-client
identity, so anyone who learns the token can write files into the inbox.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated, Any, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from .page import help_page, upload_page
from .store import Inbox, constant_time_match

# Refuse anything larger; a 4K video would otherwise sit entirely in memory.
MAX_UPLOAD_BYTES = 256 * 1024 * 1024


def generate_token() -> str:
    """Make a token short enough to retype into Shortcuts, long enough to matter."""
    return secrets.token_urlsafe(18)


def create_app(inbox_dir: Path, token: str) -> FastAPI:
    """Build the ASGI app.

    :param inbox_dir: Where uploads land.
    :param token: Shared secret; every request must present it.
    """
    inbox = Inbox(inbox_dir)
    app = FastAPI(title="iphone-tk bridge", docs_url=None, redoc_url=None)

    def check(supplied: Optional[str]) -> None:
        # Accept the token in a header or, for Shortcuts' simpler actions, a form field.
        if not constant_time_match(supplied, token):
            raise HTTPException(status_code=401, detail="Bad or missing token.")

    @app.get("/", response_class=HTMLResponse)
    async def home(t: Annotated[Optional[str], Query()] = None) -> HTMLResponse:
        """The page the phone opens in Safari.

        The token rides in the query string so that bookmarking the link — or
        adding it to the home screen — carries the credential with it.
        """
        if constant_time_match(t, token):
            return HTMLResponse(upload_page(token))
        return HTMLResponse(help_page(), status_code=401)

    @app.get("/status")
    async def status() -> dict[str, Any]:
        """Machine-readable health check."""
        return {
            "service": "iphone-tk bridge",
            "inbox": str(inbox.root),
            "items": len(inbox.list_items()),
        }

    @app.post("/text")
    async def receive_text(
        text: Annotated[str, Form()],
        x_token: Annotated[Optional[str], Header()] = None,
        token_field: Annotated[Optional[str], Form(alias="token")] = None,
    ) -> JSONResponse:
        """Receive a note, a clipboard, a URL — anything textual."""
        check(x_token or token_field)
        item = inbox.write_text(text)
        return JSONResponse({"saved": item.path.name, "bytes": item.size})

    @app.post("/upload")
    async def receive_file(
        file: Annotated[UploadFile, File()],
        x_token: Annotated[Optional[str], Header()] = None,
        token_field: Annotated[Optional[str], Form(alias="token")] = None,
    ) -> JSONResponse:
        """Receive a photo, video, or document from the Share Sheet."""
        check(x_token or token_field)

        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Upload exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            )

        item = inbox.write_bytes(file.filename, data, kind="upload")
        return JSONResponse({"saved": item.path.name, "bytes": item.size})

    return app


async def serve_async(
    inbox_dir: Path, token: str, host: str = "0.0.0.0", port: int = 8765
) -> None:
    """Run the bridge until interrupted, inside the caller's event loop.

    The CLI is already running under `asyncio.run`, so this must not use
    `uvicorn.run` — that opens a second event loop and fails outright.
    """
    import uvicorn

    config = uvicorn.Config(
        create_app(inbox_dir, token), host=host, port=port, log_level="info"
    )
    await uvicorn.Server(config).serve()


def serve(inbox_dir: Path, token: str, host: str = "0.0.0.0", port: int = 8765) -> None:
    """Blocking entry point for running the bridge on its own."""
    import asyncio

    asyncio.run(serve_async(inbox_dir, token, host=host, port=port))


def detect_lan_ip() -> Optional[str]:
    """Find the address the phone should use to reach this PC.

    Opens a UDP socket toward a public address and reads back which local
    interface the OS picked. No packet is actually sent, and it needs no
    internet connection — it only consults the routing table.
    """
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        address: str = probe.getsockname()[0]
        return address if not address.startswith("127.") else None
    except OSError:
        return None
    finally:
        probe.close()
