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

      * ``value = True``  → ``direction = INPUT``. If ``pull_up`` is
        True the pin enables the internal pull-up (~50 kΩ to 3.3 V) so
        the line floats up like a real switch's pull-up; otherwise pull
        is None and a host-side pull-up must supply the high level.
      * ``value = False`` → ``direction = OUTPUT`` and the line is
        driven actively to 0 V.

    Exposes the same ``.value`` getter/setter shape as
    ``digitalio.DigitalInOut`` so callers stay unchanged.
    """

    def __init__(self, pin, initial=True, pull_up=False):
        self._io = digitalio.DigitalInOut(pin)
        self._pull_up = bool(pull_up)
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
            self._io.pull = (digitalio.Pull.UP if self._pull_up else None)
        else:
            # Drive low. Disable the pull *first* (while we're still
            # in INPUT mode so the pull setter accepts the write) so
            # the internal pull-up isn't sourcing into our active
            # sink — guarantees the line reaches 0 V cleanly.
            if self._io.direction == digitalio.Direction.INPUT:
                self._io.pull = None
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
        0 V low. Stiff output; works against any host but fights
        any host pull-up the line might already have.
      * ``"simulated_pullup"`` — high state is the Pico's internal
        pull-up (~50 kΩ to 3.3 V), low state actively sinks to 0 V.
        Emulates a real mechanical encoder/switch: line idles high
        via a soft pull-up, snaps low only while pressed.
      * ``"open_drain"`` — like ``simulated_pullup`` but **without**
        the internal pull-up; the high state is fully high-Z and a
        host-side pull-up must supply the high level. Safer interop
        with 5 V hosts than ``simulated_pullup``.
    """
    mode = (drive_mode or "push_pull").strip().lower()
    if mode == "simulated_pullup":
        return _OpenDrainOutput(pin, initial=initial, pull_up=True)
    if mode == "open_drain":
        return _OpenDrainOutput(pin, initial=initial, pull_up=False)
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
        # Click protocol on A/B — see click_cw / click_ccw.
        #   "pulse_encoder"   = momentary pulse on a single line per
        #                       click (A for CW, B for CCW). XAC-style.
        #   "5_phase_encoder" = full gray-code quadrature sequence.
        self._protocol = str(config.get(
            "encoder_protocol", "pulse_encoder")).strip().lower()
        # When true, press2() (short-sip) drives the encoder shaft
        # button (BTN, GP20) instead of BTN2 (GP21). Hosts with only
        # one "select" input wire short-puff and short-sip together.
        self._fold_btn2_onto_btn = bool(config.get(
            "map_both_clicks_to_encoder_button", False))

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
            print("Encoder: A={} B={} BTN={} "
                  "(phase={:.4f}s, drive={}, protocol={})".format(
                      config["enc_a_pin"], config["enc_b_pin"],
                      config["enc_btn_pin"], self._phase_s,
                      self._drive_mode, self._protocol))
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
        """Emit one clockwise (positive) click.

        In ``5_phase_encoder`` mode this runs the full gray-code
        quadrature sequence on A+B. In ``pulse_encoder`` mode (the
        default) it just pulses the A line low like a button press
        — which is what the XAC and similar dry-contact hosts want,
        since they don't decode quadrature.
        """
        if self._protocol == "5_phase_encoder":
            self._emit_sequence(_CW_SEQ)
        else:
            self._pulse_button(self._a, "CW pulse")
        if self._verbose:
            print("Encoder: CW click")

    def click_ccw(self):
        """Emit one counter-clockwise (negative) click. See click_cw."""
        if self._protocol == "5_phase_encoder":
            self._emit_sequence(_CCW_SEQ)
        else:
            self._pulse_button(self._b, "CCW pulse")
        if self._verbose:
            print("Encoder: CCW click")

    def press(self):
        """Pulse the encoder pushbutton once.

        Blocks for ``encoder_button_press_s`` — typical AAC hosts
        debounce at ~30 ms so 50 ms gives a comfortable margin.
        """
        self._pulse_button(self._btn, "BTN")

    def press2(self):
        """Pulse the second button once.

        Normally drives BTN2 (GP21). When the config flag
        ``map_both_clicks_to_encoder_button`` is true, falls back to
        the encoder shaft button (BTN, GP20) so a host with only one
        "select" input sees both short-puff and short-sip as the
        same press. No-op if BTN2 wasn't configured and the fallback
        line is also unavailable.
        """
        if self._fold_btn2_onto_btn:
            self._pulse_button(self._btn, "BTN (mapped from BTN2)")
            return
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
