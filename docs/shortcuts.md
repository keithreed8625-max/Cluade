# Sending things from the iPhone to the PC

The phone dials out to the PC, so nothing needs to be paired or trusted for this
to work. It runs over your home Wi-Fi.

## 1. Start the bridge on the PC

```
iphone-tk bridge --inbox C:\Users\you\iphone-inbox
```

It prints a token. Copy it — the phone needs it.

## 2. Find the PC's LAN address

```
ipconfig
```

Use the **IPv4 Address** of the adapter you are actually on (usually `Wi-Fi`),
something like `192.168.1.24`. Both devices must be on the same network, and the
phone must not be on cellular.

If Windows Firewall prompts when the bridge starts, allow it on **Private**
networks. If you miss the prompt the phone will simply time out; re-allow it
under Windows Security -> Firewall -> Allow an app.

## 3. Confirm reachability from the phone

Open Safari on the iPhone and visit `http://192.168.1.24:8765/`. You should see
a small JSON blob naming the inbox. If you do not, the problem is the network or
the firewall, and no Shortcut will work until this does.

## 4. Build the Shortcut

**Send a photo or file**

1. Shortcuts -> **+** -> Add Action -> *Get Contents of URL*
2. URL: `http://192.168.1.24:8765/upload`
3. Expand **Show More**:
   - Method: `POST`
   - Headers: add `X-Token` = the token the bridge printed
   - Request Body: `Form`
   - Add field -> type **File** -> name it `file` -> value: `Shortcut Input`
4. Tap the shortcut name -> **Details** -> enable *Show in Share Sheet*, and set
   the accepted input to Images and Files.

Now Share -> your shortcut, from Photos or anywhere else, lands the file in the
inbox folder on the PC.

**Send text**

The same, but URL `.../text` and one Form field of type **Text** named `text`.
Useful with *Get Clipboard*, or with Share Sheet input from Safari to send URLs.

## 5. Make it automatic (optional)

Shortcuts -> **Automation** -> **+**:

- *When I arrive home* -> send your location as text
- *When I take a screenshot* -> upload it
- *At 9:00 PM* -> send the day's photos

Automations that upload need "Run Immediately" and, on some iOS versions, will
still ask you to confirm. That is an Apple restriction, not a bug in the bridge.

## Security

The token is the only thing protecting the inbox, and traffic is plain HTTP on
your LAN. Keep it to a network you control, and do not port-forward it.
