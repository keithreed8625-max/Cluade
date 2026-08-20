"""The upload page the phone opens in Safari.

Deliberately one self-contained string: no build step, no external assets, and
nothing to fetch, so it loads instantly on a phone and works with no internet
connection — only the LAN link to the PC.
"""

from __future__ import annotations

import html

_STYLE = """
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 1.25rem; padding: 1.5rem;
    font: 17px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #f2f2f7; color: #1c1c1e;
  }
  @media (prefers-color-scheme: dark) {
    body { background: #000; color: #f2f2f7; }
    .card { background: #1c1c1e !important; }
    .hint { color: #8e8e93 !important; }
  }
  .card {
    background: #fff; border-radius: 18px; padding: 1.5rem;
    width: 100%; max-width: 420px; text-align: center;
  }
  h1 { font-size: 1.25rem; margin: 0 0 .25rem; }
  .hint { color: #6c6c70; font-size: .9rem; margin: 0 0 1.25rem; }
  label.button, button {
    display: block; width: 100%; padding: 1rem;
    font-size: 1.05rem; font-weight: 600; font-family: inherit;
    border: none; border-radius: 14px; cursor: pointer;
    background: #007aff; color: #fff; margin-bottom: .75rem;
  }
  button:disabled { opacity: .5; }
  input[type=file] { display: none; }
  #status { min-height: 1.5rem; font-size: .95rem; }
  .ok { color: #34c759; } .err { color: #ff3b30; }
  ul { text-align: left; font-size: .9rem; padding-left: 1.2rem; }
"""

_SCRIPT = """
  const picker = document.getElementById('picker');
  const send = document.getElementById('send');
  const status = document.getElementById('status');
  const token = document.body.dataset.token;

  picker.addEventListener('change', () => {
    const n = picker.files.length;
    status.textContent = n ? `${n} item${n > 1 ? 's' : ''} ready` : '';
    status.className = '';
    send.disabled = !n;
  });

  send.addEventListener('click', async () => {
    send.disabled = true;
    let done = 0;
    const total = picker.files.length;
    for (const file of picker.files) {
      status.textContent = `Sending ${done + 1} of ${total}...`;
      status.className = '';
      const body = new FormData();
      body.append('file', file);
      body.append('token', token);
      try {
        const res = await fetch('/upload', { method: 'POST', body });
        if (!res.ok) throw new Error(await res.text());
        done++;
      } catch (err) {
        status.textContent = 'Failed: ' + err.message;
        status.className = 'err';
        send.disabled = false;
        return;
      }
    }
    status.textContent = `Sent ${done} item${done > 1 ? 's' : ''} to your PC`;
    status.className = 'ok';
    picker.value = '';
  });
"""


def upload_page(token: str) -> str:
    """The page shown when the link carries a valid token."""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>Send to PC</title>
<style>{_STYLE}</style>
</head>
<body data-token="{html.escape(token, quote=True)}">
  <div class="card">
    <h1>Send to PC</h1>
    <p class="hint">Pick photos and they land on your computer.</p>
    <label class="button" for="picker">Choose photos</label>
    <input id="picker" type="file" multiple accept="image/*,video/*">
    <button id="send" disabled>Send</button>
    <div id="status"></div>
  </div>
<script>{_SCRIPT}</script>
</body></html>"""


def help_page() -> str:
    """The page shown when the link has no token, so the URL alone is not enough."""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Send to PC</title>
<style>{_STYLE}</style>
</head>
<body>
  <div class="card">
    <h1>Almost there</h1>
    <p class="hint">The bridge is running, but this link has no token.</p>
    <ul>
      <li>Look at the terminal window on your PC.</li>
      <li>It prints a full link ending in <code>?t=...</code></li>
      <li>Open that link on this phone instead.</li>
    </ul>
  </div>
</body></html>"""
