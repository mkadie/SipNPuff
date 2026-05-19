"""USB HID mouse output for SipNPuff in mouse-mode.

Wraps adafruit_hid.mouse.Mouse with the same defensive style as the
LPS28 / BNO08x drivers: if HID isn't available (no `usb_hid`,
adafruit_hid not installed, or no Mouse device enumerated), the
wrapper logs and disables itself so the rest of the firmware keeps
running.

CircuitPython enables the standard USB HID composite (keyboard +
mouse + consumer-control) by default. No boot.py is required unless
the user has explicitly disabled HID.
"""


def _try_import():
    """Lazy-import. Returns the Mouse class + usb_hid module, or
    (None, None) if the host can't speak HID.
    """
    try:
        import usb_hid
    except ImportError as e:
        print("Mouse: usb_hid not available ({})".format(e))
        return None, None
    try:
        from adafruit_hid.mouse import Mouse
    except ImportError as e:
        print("Mouse: adafruit_hid.mouse not installed ({})".format(e))
        return None, None
    return Mouse, usb_hid


class MouseOutput:
    """USB HID mouse — small wrapper with a sensor-driver shape.

    Args:
        verbose: print extra debug lines.
    """

    def __init__(self, verbose=False):
        self._verbose = bool(verbose)
        self._mouse = None
        self._available = False
        self._Mouse = None     # class object — needed for button consts

        Mouse, usb_hid = _try_import()
        if Mouse is None:
            return
        try:
            self._mouse = Mouse(usb_hid.devices)
            self._Mouse = Mouse
            self._available = True
            print("Mouse: HID mouse ready")
        except Exception as e:
            print("Mouse: init failed ({})".format(e))
            self._mouse = None

    @property
    def available(self):
        return self._available

    # --- Public actions ------------------------------------------

    def move(self, dx, dy):
        """Send a (dx, dy) motion report. No-op for (0, 0) — saves
        USB traffic on idle ticks.
        """
        if not self._available:
            return
        dx_i = int(dx)
        dy_i = int(dy)
        if dx_i == 0 and dy_i == 0:
            return
        try:
            self._mouse.move(x=dx_i, y=dy_i)
        except Exception as e:
            if self._verbose:
                print("Mouse: move({},{}) failed ({})".format(dx_i, dy_i, e))

    def click_left(self):
        self._click(self._Mouse.LEFT_BUTTON, "left")

    def click_right(self):
        self._click(self._Mouse.RIGHT_BUTTON, "right")

    def click_middle(self):
        self._click(self._Mouse.MIDDLE_BUTTON, "middle")

    def scroll(self, amount):
        """Scroll wheel: positive = up, negative = down. Amount is
        passed straight to the HID report so 1 ≈ one notch on most
        OSes."""
        if not self._available or amount == 0:
            return
        try:
            self._mouse.move(wheel=int(amount))
            if self._verbose:
                print("Mouse: scroll {}".format(amount))
        except Exception as e:
            if self._verbose:
                print("Mouse: scroll failed ({})".format(e))

    def release_all(self):
        if not self._available:
            return
        try:
            self._mouse.release_all()
        except Exception:
            pass

    # --- Internals -----------------------------------------------

    def _click(self, button, label):
        if not self._available:
            return
        try:
            self._mouse.click(button)
            if self._verbose:
                print("Mouse: {} click".format(label))
        except Exception as e:
            print("Mouse: {} click failed ({})".format(label, e))
