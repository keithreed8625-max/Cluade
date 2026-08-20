# iphone-tk

Read data off an iPhone, receive things it sends, and automate it — from a
Windows PC, over USB. No Mac and no jailbreak.

Built on [pymobiledevice3](https://github.com/doronz88/pymobiledevice3), which
speaks the same protocols Finder and Xcode use.

## What works, and what does not

| You want to | Works? | How |
|---|---|---|
| Device info, battery, installed apps | Yes | USB, nothing to enable |
| Copy photos and videos off | Yes | USB, nothing to enable |
| Crash logs, live system log | Yes | USB, nothing to enable |
| Full backup (Messages, Health, app data) | Yes | USB, nothing to enable |
| Screenshots | Yes | Needs Developer Mode |
| Launch/kill apps, list processes | Yes | Needs Developer Mode |
| Spoof GPS location | Yes | Needs Developer Mode |
| Reboot / shut down | Yes | USB, nothing to enable |
| Phone sends photos/files to the PC | Yes | Wi-Fi, via a web page or Shortcut |
| **Tap, swipe, type on the screen** | **No** | Needs WebDriverAgent, which only builds and signs on a Mac |
| **Read Messages/Photos live from a running phone** | **No** | Apple sandboxes them; take a backup instead |
| **Anything wirelessly without setup** | **No** | USB, or the Shortcuts bridge |

The one that surprises people is UI automation. There is no Windows path to
synthetic touches. If you need the phone to *do* something on screen, write a
Shortcut on the phone and trigger it — the bridge in this repo is built for that.

## Install (Windows)

1. **Install Apple's USB driver.** Get **Apple Devices** from the Microsoft
   Store (or iTunes from apple.com — not the Store version). Every tool here
   talks to the phone through the Apple Mobile Device Service it installs.
2. **Install this tool.**
   ```
   py -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   ```
3. **Plug the phone in, unlock it, tap Trust.**
4. **Check it.**
   ```
   iphone-tk devices
   iphone-tk info
   ```

If `devices` finds nothing, the error tells you which of the four usual causes
to check.

### For the [dev] commands

Screenshots, app launching, and location spoofing go through Apple's developer
services, so:

1. On the phone: **Settings -> Privacy & Security -> Developer Mode -> On**,
   then reboot. (If the menu is missing, run any `iphone-tk` [dev] command once
   with the phone connected and it appears.)
2. **On iOS 17 and later only**, those services moved behind a tunnel that needs
   Administrator rights. Open a second terminal *as Administrator* and leave
   this running:
   ```
   python -m pymobiledevice3 remote tunneld
   ```

## Use

```
iphone-tk devices                          # UDIDs of connected phones
iphone-tk info                             # name, iOS, model, storage
iphone-tk battery                          # level and health
iphone-tk apps                             # installed apps (--all for Apple's)

iphone-tk media-ls                         # browse the camera roll
iphone-tk pull-media C:\photos             # copy it all off
iphone-tk pull-media C:\photos --match "\.HEIC$"
iphone-tk pull-crashes C:\crashes
iphone-tk syslog log.txt --lines 500 --contains error
iphone-tk backup C:\backup                 # slow, large, but complete

iphone-tk screenshot shot.png              # [dev]
iphone-tk launch com.apple.Maps            # [dev]
iphone-tk kill com.apple.Maps              # [dev]
iphone-tk ps                               # [dev]
iphone-tk set-location 51.5007 -0.1246     # [dev] Big Ben
iphone-tk clear-location                   # [dev] back to real GPS

iphone-tk bridge --inbox C:\inbox          # receive from the phone
```

Add `--udid <id>` when more than one phone is plugged in.

### Receiving photos from the phone

Double-click **`start-bridge.bat`** (or run `iphone-tk bridge`). It prints a
link; open it in Safari on the phone and add it to the home screen. After that,
sending photos is: tap icon, choose, send.

Nothing needs installing on the phone, and no Shortcut is required. Full
walkthrough: **[docs/send-photos.md](docs/send-photos.md)**.

The bridge is built for a home LAN: a shared token, a size cap, and an inbox
that uploads cannot escape. It has no TLS and no per-client identity, so do not
expose it to the internet.

## Notes

- **Backups are the real data extraction route.** Live access to Messages,
  Health, and app databases is sandboxed. `iphone-tk backup` gets them; expect
  it to take a while and to be roughly the size of the phone's used space.
- **Location spoofing is device-wide** and persists until you clear it, the
  phone reboots, or USB disconnects. Every app sees the fake position.
- **Nothing here bypasses a passcode or Activation Lock**, and it all requires a
  phone that is unlocked and has trusted this PC.

## Development

```
pip install -e . pytest httpx
pytest
```

The tests cover the bridge — filename sanitation, auth, size limits, upload
collisions — and run without a device attached. The device-facing code needs a
real iPhone to exercise.
