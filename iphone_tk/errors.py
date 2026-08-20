"""Errors that carry a fix, not just a failure."""


class IphoneTkError(Exception):
    """Base error. The message is shown to the user verbatim, so write it as advice."""


class NoDeviceError(IphoneTkError):
    """No iPhone is reachable over USB."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            (detail + "\n\n" if detail else "")
            + "No iPhone found over USB. Check, in order:\n"
            "  1. The phone is plugged in with a data cable (charge-only cables carry no data).\n"
            "  2. The phone is unlocked and you tapped 'Trust This Computer'.\n"
            "  3. Apple Devices (Microsoft Store) or iTunes is installed — it supplies the\n"
            "     Apple Mobile Device Service that all USB access on Windows goes through.\n"
            "  4. That service is running: services.msc -> 'Apple Mobile Device Service'."
        )


class TrustError(IphoneTkError):
    """The device is visible but not paired."""

    def __init__(self) -> None:
        super().__init__(
            "The iPhone is connected but not trusted by this PC.\n"
            "Unlock the phone, then tap 'Trust' on the prompt and re-run.\n"
            "If no prompt appears: Settings -> General -> Transfer or Reset iPhone ->\n"
            "Reset -> Reset Location & Privacy, then reconnect."
        )


class DeveloperModeError(IphoneTkError):
    """A DVT/automation feature was used without Developer Mode."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            (detail + "\n\n" if detail else "")
            + "This command needs Developer Mode on the iPhone.\n"
            "  Settings -> Privacy & Security -> Developer Mode -> On, then reboot the phone.\n"
            "If that menu is missing, connect the phone once while a developer tool is\n"
            "running (this toolkit counts) and it will appear.\n\n"
            "On iOS 17 and later you must ALSO have a tunnel running, in a separate\n"
            "Administrator terminal:\n"
            "  python -m pymobiledevice3 remote tunneld\n"
            "Leave it open and re-run this command."
        )
