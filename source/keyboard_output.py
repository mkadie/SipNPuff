"""USB HID keyboard output for SipNPuff in keyboard-mode.

Wraps adafruit_hid.keyboard.Keyboard with the same defensive style
as MouseOutput: if HID isn't available (no `usb_hid`, adafruit_hid
not installed, or no Keyboard device enumerated), the wrapper logs
and disables itself so the rest of the firmware keeps running.

Each breath event maps to a key (or a `+`-joined combo) named in
config.txt:

    key_puff        = ENTER
    key_sip         = ESCAPE
    key_puff_repeat = UP_ARROW
    key_sip_repeat  = DOWN_ARROW
    key_double_puff = SPACE
    key_double_sip  = none

Key names are Keycode attribute names (case-insensitive), with a
few friendly aliases (SPACE, ESC, UP, DOWN, LEFT, RIGHT, CTRL,
PGUP, PGDN, DEL) and bare digits/letters. Combos press every key
in the chord then release all, e.g. ``key_puff = CONTROL+C``.

CircuitPython enables the standard USB HID composite (keyboard +
mouse + consumer-control) by default. No boot.py is required unless
the user has explicitly disabled HID.
"""


# Breath event → default key name. Arrow/Enter scheme mirrors the
# encoder semantics: held breaths scroll a list, short puff selects.
_EVENT_KEY_DEFAULTS = {
    "puff":        "ENTER",
    "sip":         "ESCAPE",
    "puff_repeat": "UP_ARROW",
    "sip_repeat":  "DOWN_ARROW",
    "double_puff": "SPACE",
    "double_sip":  "none",
    # Reverse/undo keys for optimistic_double mode: when a second puff
    # (or sip) turns an already-sent move into a select, this key is
    # tapped first to cancel that move. Typically the opposite-direction
    # key (e.g. DOWN_ARROW to undo an UP_ARROW puff). "none" = no undo.
    "puff_reverse": "none",
    "sip_reverse":  "none",
}

# Friendly spellings → Keycode attribute names. Anything not listed
# is tried verbatim (uppercased) against the Keycode class, so the
# full Keycode vocabulary (F1..F24, KEYPAD_*, etc.) works untouched.
_KEY_ALIASES = {
    "SPACE": "SPACEBAR",
    "ESC":   "ESCAPE",
    "UP":    "UP_ARROW",
    "DOWN":  "DOWN_ARROW",
    "LEFT":  "LEFT_ARROW",
    "RIGHT": "RIGHT_ARROW",
    "CTRL":  "CONTROL",
    "DEL":   "DELETE",
    "PGUP":  "PAGE_UP",
    "PGDN":  "PAGE_DOWN",
}

# Bare digits — Keycode spells them out.
_DIGIT_NAMES = ("ZERO", "ONE", "TWO", "THREE", "FOUR",
                "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")

# Spellings that mean "this event sends nothing".
_UNMAPPED = ("", "NONE", "OFF", "NO", "DISABLED", "FALSE")


def _try_import():
    """Lazy-import. Returns (Keyboard, Keycode, usb_hid), or
    (None, None, None) if the host can't speak HID.
    """
    try:
        import usb_hid
    except ImportError as e:
        print("Keyboard: usb_hid not available ({})".format(e))
        return None, None, None
    try:
        from adafruit_hid.keyboard import Keyboard
        from adafruit_hid.keycode import Keycode
    except ImportError as e:
        print("Keyboard: adafruit_hid.keyboard not installed ({})".format(e))
        return None, None, None
    return Keyboard, Keycode, usb_hid


def _resolve_key(keycode_cls, name):
    """Resolve one key name to a Keycode int, or None if unknown."""
    s = str(name).strip().upper()
    if len(s) == 1 and s.isdigit():
        s = _DIGIT_NAMES[int(s)]
    s = _KEY_ALIASES.get(s, s)
    return getattr(keycode_cls, s, None)


def _resolve_combo(keycode_cls, spec):
    """Resolve 'NAME' or 'NAME+NAME+…' to a tuple of Keycode ints.
    Returns None (unmapped) for blank/none specs or any unknown name
    in the chord — a half-resolved chord would press the wrong keys.
    """
    s = str(spec).strip()
    if s.upper() in _UNMAPPED:
        return None
    codes = []
    for part in s.split("+"):
        code = _resolve_key(keycode_cls, part)
        if code is None:
            print("Keyboard: unknown key '{}' in '{}'".format(part, s))
            return None
        codes.append(code)
    return tuple(codes)


class KeyboardOutput:
    """USB HID keyboard — small wrapper with a sensor-driver shape.

    Args:
        config: resolved runtime config dict (reads key_* entries).
        verbose: print extra debug lines.
    """

    def __init__(self, config, verbose=False):
        self._verbose = bool(verbose)
        self._keyboard = None
        self._available = False
        self._map = {}     # event name → tuple of Keycode ints, or None

        Keyboard, Keycode, usb_hid = _try_import()
        if Keyboard is None:
            return
        try:
            self._keyboard = Keyboard(usb_hid.devices)
            self._available = True
        except Exception as e:
            print("Keyboard: init failed ({})".format(e))
            self._keyboard = None
            return

        specs = []
        for event, default in sorted(_EVENT_KEY_DEFAULTS.items()):
            spec = config.get("key_" + event, default)
            self._map[event] = _resolve_combo(Keycode, spec)
            specs.append("{}={}".format(event, spec))
        print("Keyboard: HID keyboard ready, map {}".format(
            " ".join(specs)))

    @property
    def available(self):
        return self._available

    # --- Public actions ------------------------------------------

    def tap(self, event):
        """Press-and-release the key (or chord) mapped to a breath
        event. No-op when the event is unmapped or HID is down.
        """
        if not self._available:
            return
        codes = self._map.get(event)
        if codes is None:
            return
        try:
            self._keyboard.send(*codes)
            if self._verbose:
                print("Keyboard: {} -> {}".format(event, codes))
        except Exception as e:
            print("Keyboard: {} send failed ({})".format(event, e))

    def release_all(self):
        if not self._available:
            return
        try:
            self._keyboard.release_all()
        except Exception:
            pass
