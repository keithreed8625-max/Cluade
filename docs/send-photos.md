# Sending photos from your iPhone to your PC

Two ways. The first needs nothing installed on the phone.

---

## The easy way: a home screen icon

### One-time setup

**1. Start the bridge on the PC.**

Double-click `start-bridge.bat` in this folder. The first run takes a minute
while it sets itself up; after that it starts immediately.

If Windows Firewall asks, tick **Private networks** and allow it. If you miss
that prompt, the phone will just time out.

**2. It prints a link.** Something like:

```
http://192.168.1.24:8765/?t=kR3nQ8vLx2mBp7wY
```

**3. Open that link in Safari on your iPhone.** Type it in, or send it to
yourself however is easiest — you only do this once.

You should see a **Send to PC** page.

**4. Tap the Share button in Safari, then "Add to Home Screen."**

Now there is an icon on your home screen.

### Every time after that

1. Make sure `start-bridge.bat` is running on the PC
2. Tap the icon on your phone
3. **Choose photos** → pick them → **Send**

They appear in the `photos` folder next to `start-bridge.bat`. You can select
several at once.

---

## The other way: the Share Sheet

More setup, but then you can send straight from Photos without opening anything.

1. Shortcuts app → **+** → Add Action → *Get Contents of URL*
2. URL: the `http://...` part of your link, but ending in `/upload`
3. **Show More**:
   - Method: `POST`
   - Headers: `X-Token` = the part of your link after `?t=`
   - Request Body: `Form`
   - Add field → type **File** → name `file` → value `Shortcut Input`
4. Tap the shortcut's name → **Details** → turn on *Show in Share Sheet*

Now: Photos → Share → your shortcut.

---

## When it does not work

**The phone cannot load the page at all**
- Is `start-bridge.bat` still running? The window must stay open.
- Is the phone on Wi-Fi rather than cellular? Check in Settings.
- Same Wi-Fi network as the PC? Guest networks are usually isolated.
- Windows Firewall: Windows Security → Firewall → Allow an app.

**"Almost there" page**
Your link is missing the `?t=...` part, or carries a token that is no longer
current. Copy the whole line from the terminal and re-add it.

The token is saved between runs, so a working icon stays working. It only
changes if you pass `--new-token`, or if the saved token file is deleted.
Startup prints which of the two happened.

**The PC's address changed**
Home routers hand out new addresses periodically. Restart the bridge; it prints
the current one.

---

## Is this safe?

It only works on your own Wi-Fi — nothing is exposed to the internet, and no
photo passes through anyone else's server. The `?t=` token stops other devices
on your network from uploading.

That token is kept in a file readable only by your Windows account
(`%LOCALAPPDATA%\iphone-tk\bridge-token`), not in the photo folder. Delete it,
or run with `--new-token`, and every saved link stops working.

It is plain HTTP on your LAN, so use it on a network you control. Do not set up
port forwarding for it.
