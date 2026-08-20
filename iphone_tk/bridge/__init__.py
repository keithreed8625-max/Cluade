"""Goal 2: let the phone send things to the PC.

The phone cannot be dialled into, but it can dial out. A Shortcut on the phone
POSTs to this server over your local Wi-Fi; the server writes what arrives into
an inbox folder. That inverts the connection direction and sidesteps every
pairing and entitlement problem.
"""

from .store import Inbox, InboxItem, safe_filename

__all__ = ["Inbox", "InboxItem", "safe_filename"]
