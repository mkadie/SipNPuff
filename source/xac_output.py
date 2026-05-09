"""Xbox Adaptive Controller dry-contact outputs.

Drives two independent PC817 optocouplers — one per breath direction:

    Puff_enable -> 220R -> PC817 anode (default GP1)
    Sip_enable  -> 220R -> PC817 anode (default GP0)

The opto's emitter/collector pair is wired to a 3.5 mm mono jack so
the XAC sees a momentary switch closure with no electrical bridge
back to the Pico. Each direction maps to a separate XAC input, so
sip and puff can be assigned to different game-pad buttons.

A typical AAC / XAC host expects a momentary closure of ~30–100 ms.
The default ``xac_pulse_s`` is 50 ms; tune in config.txt if a
specific host needs longer. ``xac_active_low`` flips the polarity
without requiring re-wiring on the PCB.
"""

import time
import digitalio

from hardware_config import _pin


def _make_output(pin, initial):
    io = digitalio.DigitalInOut(pin)
    io.direction = digitalio.Direction.OUTPUT
    io.value = initial
    return io


class XacOutput:
    """Two opto-isolated dry-contact outputs to the XAC, one per breath
    direction.

    Args:
        config: variant config dict.
    """

    def __init__(self, config):
        self._active_low = bool(config["xac_active_low"])
        self._pulse_s    = float(config["xac_pulse_s"])
        # Gap between the two pulses of a double-tap event. The host
        # needs to see the line return to idle long enough to register
        # two distinct closures rather than one held button.
        self._double_gap_s = float(config.get("xac_double_gap_s", 0.05))
        self._verbose    = bool(config.get("verbose", False))

        idle = self._idle_level()

        self._puff = None
        self._sip  = None
        # Per-line availability — if one pin is already claimed (e.g.
        # by SPI0 or UART0), the other still works.
        self._puff_ok = False
        self._sip_ok  = False

        puff_pin = config["xac_puff_pin"]
        sip_pin  = config["xac_sip_pin"]

        try:
            self._puff = _make_output(_pin(puff_pin), idle)
            self._puff_ok = True
        except Exception as e:
            print("XAC: puff init failed on {} ({})".format(puff_pin, e))

        try:
            self._sip = _make_output(_pin(sip_pin), idle)
            self._sip_ok = True
        except Exception as e:
            print("XAC: sip init failed on {} ({})".format(sip_pin, e))

        if self._puff_ok or self._sip_ok:
            print("XAC: puff={}({}) sip={}({}) (active_{})".format(
                puff_pin, "ok" if self._puff_ok else "FAIL",
                sip_pin,  "ok" if self._sip_ok  else "FAIL",
                "low" if self._active_low else "high"))

    @property
    def available(self):
        """True if at least one optocoupler GPIO initialised."""
        return self._puff_ok or self._sip_ok

    # --- Public actions ------------------------------------------

    def pulse_puff(self):
        """Momentary closure on the PUFF jack."""
        if self._puff_ok:
            self._pulse(self._puff, "puff")

    def pulse_sip(self):
        """Momentary closure on the SIP jack."""
        if self._sip_ok:
            self._pulse(self._sip, "sip")

    def pulse_puff_double(self):
        """Two rapid closures on the PUFF jack — host sees a double-tap.

        Total elapsed time is roughly 2*xac_pulse_s + xac_double_gap_s
        (~150 ms with defaults). This blocks the main loop, but double
        events are rare and intentional, so the cost is acceptable.
        """
        if self._puff_ok:
            self._pulse_double(self._puff, "puff")

    def pulse_sip_double(self):
        """Two rapid closures on the SIP jack — host sees a double-tap."""
        if self._sip_ok:
            self._pulse_double(self._sip, "sip")

    def all_release(self):
        """Force both outputs to idle. Call before exit / on error."""
        idle = self._idle_level()
        try:
            if self._puff_ok and self._puff is not None:
                self._puff.value = idle
            if self._sip_ok and self._sip is not None:
                self._sip.value = idle
        except Exception:
            pass

    # --- Internals -----------------------------------------------

    def _pulse(self, line, label):
        if line is None:
            return
        try:
            line.value = self._asserted_level()
            time.sleep(self._pulse_s)
            line.value = self._idle_level()
            if self._verbose:
                print("XAC: {} pulse".format(label))
        except Exception as e:
            print("XAC: {} pulse failed ({})".format(label, e))
            self.all_release()

    def _pulse_double(self, line, label):
        if line is None:
            return
        try:
            asserted = self._asserted_level()
            idle     = self._idle_level()
            line.value = asserted
            time.sleep(self._pulse_s)
            line.value = idle
            time.sleep(self._double_gap_s)
            line.value = asserted
            time.sleep(self._pulse_s)
            line.value = idle
            if self._verbose:
                print("XAC: {} double-pulse".format(label))
        except Exception as e:
            print("XAC: {} double-pulse failed ({})".format(label, e))
            self.all_release()

    def _asserted_level(self):
        return False if self._active_low else True

    def _idle_level(self):
        return True if self._active_low else False
