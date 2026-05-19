"""Quadrature encoder emulation on three GPIOs.

Drives ENC_A, ENC_B, ENC_BTN as outputs to look like a mechanical
rotary encoder with a pushbutton. Used to plug the Sip-N-Puff
directly into the T-Rex Talker's existing rotary encoder port.

Quadrature pattern for one CW click (A leads B):

    A: 1 0 0 1 1
    B: 1 1 0 0 1

CCW is the same pattern with A and B swapped. Each phase is held
for ``encoder_phase_s`` so a host polling at sub-kHz can capture
the transitions reliably.

Idle level is HIGH on all three lines, matching a typical encoder
with an internal pull-up at the host side.
"""

import time
import digitalio

from hardware_config import _pin


# Quadrature gray code — full sequence for one CW click. The first
# entry is the idle state which we restore between clicks so a host
# state machine that keys off level (rather than edge) is happy.
_CW_SEQ  = ((1, 1), (0, 1), (0, 0), (1, 0), (1, 1))
_CCW_SEQ = ((1, 1), (1, 0), (0, 0), (0, 1), (1, 1))


class _OpenDrainOutput:
    """Open-drain output that survives any CircuitPython port.

    ``digitalio.DriveMode.OPEN_DRAIN`` is supposed to do this, but in
    practice the RP2040/RP2350 CP build has been observed leaving the
    pin in a high-Z-ish state when value=False is set — so the "low"
    half of the cycle never actually pulls to 0 V. To sidestep that,
    we manage open-drain ourselves by flipping ``direction``:

      * ``value = True``  → ``direction = INPUT`` (pin is high-Z, host
        pull-up wins). Pull set to None so we never source through an
        internal pull-up either.
      * ``value = False`` → ``direction = OUTPUT`` and the line is
        driven actively to 0 V.

    Exposes the same ``.value`` getter/setter shape as
    ``digitalio.DigitalInOut`` so callers stay unchanged.
    """

    def __init__(self, pin, initial=True):
        self._io = digitalio.DigitalInOut(pin)
        self._value = None
        self.value = initial

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        v = bool(v)
        if v:
            self._io.direction = digitalio.Direction.INPUT
            self._io.pull = None
        else:
            self._io.direction = digitalio.Direction.OUTPUT
            self._io.value = False
        self._value = v

    def deinit(self):
        self._io.deinit()


def _make_push_pull(pin, initial=True):
    """Plain push-pull output: drives 0 V low and 3.3 V high."""
    io = digitalio.DigitalInOut(pin)
    io.direction = digitalio.Direction.OUTPUT
    io.value = initial
    return io


def _make_output(pin, initial=True, drive_mode="push_pull"):
    """Configure ``pin`` according to the requested drive mode.

    ``drive_mode`` is one of:
      * ``"push_pull"`` (default) — actively drives 3.3 V high and
        0 V low. Use this when the host's encoder input has no
        pull-up of its own, or whenever you want guaranteed levels
        on both edges.
      * ``"open_drain"`` — sinks to 0 V on low, floats on high. The
        host's pull-up determines the high voltage. Safer interop
        with 5 V hosts, but requires the host to have a pull-up.
    """
    mode = (drive_mode or "push_pull").strip().lower()
    if mode == "open_drain":
        return _OpenDrainOutput(pin, initial=initial)
    return _make_push_pull(pin, initial=initial)


class EncoderEmulator:
    """Drive A/B/BTN as a quadrature encoder + pushbutton.

    Args:
        config: variant config dict (encoder_*_pin and timing keys).
    """

    def __init__(self, config):
        self._phase_s        = float(config["encoder_phase_s"])
        self._btn_active_low = bool(config["encoder_button_active_low"])
        self._btn_press_s    = float(config["encoder_button_press_s"])
        self._verbose        = bool(config.get("verbose", False))
        # Drive mode applies to all encoder output lines (A, B, BTN,
        # BTN2). See _make_output() for the trade-offs.
        self._drive_mode     = str(config.get(
            "encoder_drive_mode", "push_pull")).strip().lower()

        self._a    = None
        self._b    = None
        self._btn  = None
        self._btn2 = None
        self._available = False

        try:
            self._a   = _make_output(_pin(config["enc_a_pin"]),
                                     initial=True,
                                     drive_mode=self._drive_mode)
            self._b   = _make_output(_pin(config["enc_b_pin"]),
                                     initial=True,
                                     drive_mode=self._drive_mode)
            self._btn = _make_output(
                _pin(config["enc_btn_pin"]),
                initial=self._btn_idle_level(),
                drive_mode=self._drive_mode,
            )
            self._available = True
            print("Encoder: A={} B={} BTN={} (phase={:.4f}s, drive={})".format(
                config["enc_a_pin"], config["enc_b_pin"],
                config["enc_btn_pin"], self._phase_s, self._drive_mode))
        except Exception as e:
            print("Encoder: init failed ({})".format(e))
            return

        # Optional second button — symmetric with the encoder shaft
        # button. Used by the dispatcher as the "short sip" output in
        # encoder mode. Same active-low / pulse-width semantics.
        btn2_name = config.get("enc_btn2_pin")
        if btn2_name:
            try:
                self._btn2 = _make_output(
                    _pin(btn2_name), initial=self._btn_idle_level(),
                    drive_mode=self._drive_mode)
                print("Encoder: BTN2={}".format(btn2_name))
            except Exception as e:
                print("Encoder: BTN2 init failed ({})".format(e))
                self._btn2 = None

    @property
    def available(self):
        """True if all three encoder GPIOs initialised."""
        return self._available

    # --- Public actions ------------------------------------------

    def click_cw(self):
        """Emit one clockwise (positive) quadrature click."""
        self._emit_sequence(_CW_SEQ)
        if self._verbose:
            print("Encoder: CW click")

    def click_ccw(self):
        """Emit one counter-clockwise (negative) quadrature click."""
        self._emit_sequence(_CCW_SEQ)
        if self._verbose:
            print("Encoder: CCW click")

    def press(self):
        """Pulse the encoder pushbutton once.

        Blocks for ``encoder_button_press_s`` — typical AAC hosts
        debounce at ~30 ms so 50 ms gives a comfortable margin.
        """
        self._pulse_button(self._btn, "BTN")

    def press2(self):
        """Pulse the second button once. No-op if BTN2 wasn't configured."""
        if self._btn2 is None:
            return
        self._pulse_button(self._btn2, "BTN2")

    def _pulse_button(self, line, label):
        if not self._available or line is None:
            return
        try:
            line.value = self._btn_pressed_level()
            time.sleep(self._btn_press_s)
            line.value = self._btn_idle_level()
            if self._verbose:
                print("Encoder: {} press".format(label))
        except Exception as e:
            print("Encoder: {} press failed ({})".format(label, e))

    # --- Internals -----------------------------------------------

    def _emit_sequence(self, seq):
        if not self._available:
            return
        try:
            for a_level, b_level in seq:
                self._a.value = bool(a_level)
                self._b.value = bool(b_level)
                time.sleep(self._phase_s)
        except Exception as e:
            print("Encoder: emit failed ({})".format(e))
            # On any I/O error, restore the idle level so the host
            # doesn't see us hung in a partial-click state.
            self._safe_idle()

    def _safe_idle(self):
        try:
            if self._a:
                self._a.value = True
            if self._b:
                self._b.value = True
            if self._btn:
                self._btn.value = self._btn_idle_level()
            if self._btn2:
                self._btn2.value = self._btn_idle_level()
        except Exception:
            pass

    def _btn_idle_level(self):
        # Active-low: idle = HIGH (line released, host pull-up wins).
        return True if self._btn_active_low else False

    def _btn_pressed_level(self):
        return False if self._btn_active_low else True
