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


def _make_output(pin, initial=True):
    io = digitalio.DigitalInOut(pin)
    io.direction = digitalio.Direction.OUTPUT
    io.value = initial
    return io


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

        self._a   = None
        self._b   = None
        self._btn = None
        self._available = False

        try:
            self._a   = _make_output(_pin(config["enc_a_pin"]),   initial=True)
            self._b   = _make_output(_pin(config["enc_b_pin"]),   initial=True)
            self._btn = _make_output(
                _pin(config["enc_btn_pin"]),
                initial=self._btn_idle_level(),
            )
            self._available = True
            print("Encoder: A={} B={} BTN={} (phase={:.4f}s)".format(
                config["enc_a_pin"], config["enc_b_pin"],
                config["enc_btn_pin"], self._phase_s))
        except Exception as e:
            print("Encoder: init failed ({})".format(e))

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
        if not self._available:
            return
        try:
            self._btn.value = self._btn_pressed_level()
            time.sleep(self._btn_press_s)
            self._btn.value = self._btn_idle_level()
            if self._verbose:
                print("Encoder: button press")
        except Exception as e:
            print("Encoder: press failed ({})".format(e))

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
        except Exception:
            pass

    def _btn_idle_level(self):
        # Active-low: idle = HIGH (line released, host pull-up wins).
        return True if self._btn_active_low else False

    def _btn_pressed_level(self):
        return False if self._btn_active_low else True
