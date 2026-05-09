"""Breath event state machine.

Consumes baseline-zeroed kPa readings and emits high-level events:

    "puff"        — single puff release (puff that did NOT pair with another)
    "double_puff" — two puffs within double_puff_window_s
    "puff_repeat" — repeating tick while a puff is held past hold_to_repeat_s
    "sip"         — single sip release (sip that did NOT pair with another)
    "double_sip"  — two sips within double_sip_window_s
    "sip_repeat"  — repeating tick while a sip is held

The classifier is single-threaded and non-blocking: call poll(p_kpa)
on every loop iteration and act on whatever event string it returns
(or None if nothing has happened). It uses time.monotonic() for all
timing so a missed loop tick just delays an event slightly — it does
not lose state.

Hysteresis: we use separate ON/OFF thresholds per direction so a
breath sitting right at the threshold can't chatter the state.
"""

import time


# Internal state values for the breath finite-state machine.
_IDLE      = "idle"
_PUFF_ON   = "puff_on"
_SIP_ON    = "sip_on"
# Pending states: one breath just ended, waiting to see if a second
# arrives within the double window. If it does → "double_*". If the
# window expires → emit the single-breath event we held back.
_PUFF_PEND = "puff_pend"
_SIP_PEND  = "sip_pend"


class BreathClassifier:
    """Pressure → breath-event finite-state machine.

    Args:
        config: variant config dict (thresholds and timings).
    """

    def __init__(self, config):
        self._puff_on  = float(config["puff_on_kpa"])
        self._puff_off = float(config["puff_off_kpa"])
        self._sip_on   = float(config["sip_on_kpa"])
        self._sip_off  = float(config["sip_off_kpa"])

        self._double_puff_window = float(config["double_puff_window_s"])
        # Sip window defaults to the puff value if not specified, so
        # older configs still work.
        self._double_sip_window  = float(config.get(
            "double_sip_window_s", config["double_puff_window_s"]))
        self._hold_repeat   = float(config["hold_to_repeat_s"])
        self._rate_min  = float(config["repeat_min_hz"])
        self._rate_max  = float(config["repeat_max_hz"])
        self._rate_full = float(config["repeat_full_scale_kpa"])
        self._verbose   = bool(config.get("verbose", False))

        self._state = _IDLE
        self._t_state_entered = time.monotonic()
        self._t_pending_until = 0.0   # deadline for double detection
        self._t_next_repeat   = 0.0   # next time a *_repeat tick is due
        self._double_consumed = False

    # --- Public API ----------------------------------------------

    def poll(self, p_kpa):
        """Advance the state machine and return an event string or None.

        Args:
            p_kpa: current baseline-zeroed pressure in kPa.

        Returns:
            One of "puff", "double_puff", "puff_repeat", "sip",
            "double_sip", "sip_repeat", or None.
        """
        now = time.monotonic()

        if self._state == _IDLE:
            return self._poll_idle(p_kpa, now)

        if self._state == _PUFF_PEND:
            return self._poll_puff_pending(p_kpa, now)

        if self._state == _SIP_PEND:
            return self._poll_sip_pending(p_kpa, now)

        if self._state == _PUFF_ON:
            return self._poll_puff_on(p_kpa, now)

        if self._state == _SIP_ON:
            return self._poll_sip_on(p_kpa, now)

        # Defensive: unknown state shouldn't happen, drop to idle.
        self._enter(_IDLE, now)
        return None

    @property
    def state(self):
        """Current internal state string — useful for diagnostic output."""
        return self._state

    # --- State handlers ------------------------------------------

    def _poll_idle(self, p_kpa, now):
        if p_kpa >= self._puff_on:
            self._enter(_PUFF_ON, now)
        elif p_kpa <= self._sip_on:
            self._enter(_SIP_ON, now)
        return None

    def _poll_puff_pending(self, p_kpa, now):
        # Second puff arrived inside the window → double-puff.
        if p_kpa >= self._puff_on:
            self._enter(_PUFF_ON, now, double_pending=True)
            return "double_puff"
        # Window expired → fire the single puff we held back.
        if now >= self._t_pending_until:
            self._enter(_IDLE, now)
            return "puff"
        return None

    def _poll_sip_pending(self, p_kpa, now):
        # Second sip arrived inside the window → double-sip.
        if p_kpa <= self._sip_on:
            self._enter(_SIP_ON, now, double_pending=True)
            return "double_sip"
        # Window expired → fire the single sip we held back.
        if now >= self._t_pending_until:
            self._enter(_IDLE, now)
            return "sip"
        return None

    def _poll_puff_on(self, p_kpa, now):
        # Released? Decide whether to emit immediately or wait for
        # a possible second puff.
        if p_kpa < self._puff_off:
            # If we entered PUFF_ON as the second half of a double-puff,
            # the event was already emitted — just go idle.
            if self._double_consumed:
                self._enter(_IDLE, now)
                return None
            self._t_pending_until = now + self._double_puff_window
            self._enter(_PUFF_PEND, now)
            return None

        # Still held — once past hold_to_repeat_s, emit ticks at
        # a pressure-scaled rate.
        held = now - self._t_state_entered
        if held >= self._hold_repeat and now >= self._t_next_repeat:
            self._t_next_repeat = now + self._tick_period(p_kpa)
            return "puff_repeat"
        return None

    def _poll_sip_on(self, p_kpa, now):
        if p_kpa > self._sip_off:
            # Same double-consumed dance as the puff path.
            if self._double_consumed:
                self._enter(_IDLE, now)
                return None
            self._t_pending_until = now + self._double_sip_window
            self._enter(_SIP_PEND, now)
            return None

        held = now - self._t_state_entered
        if held >= self._hold_repeat and now >= self._t_next_repeat:
            self._t_next_repeat = now + self._tick_period(-p_kpa)
            return "sip_repeat"
        return None

    # --- Internals -----------------------------------------------

    def _enter(self, new_state, now, double_pending=False):
        if self._verbose and new_state != self._state:
            print("Breath: {} -> {}".format(self._state, new_state))
        self._state = new_state
        self._t_state_entered = now
        self._t_next_repeat = now + self._hold_repeat
        # Latched flag: when entering PUFF_ON / SIP_ON as the second
        # half of a double event, suppress the "single" emission on
        # release.
        self._double_consumed = double_pending

    def _tick_period(self, magnitude_kpa):
        """Return seconds-per-tick for a held breath at this magnitude.

        Linearly maps |kPa| over [puff_on_kpa, repeat_full_scale_kpa]
        to [repeat_min_hz, repeat_max_hz]. Clamped at both ends so a
        very hard breath doesn't produce a divide-by-zero.
        """
        mag = max(self._puff_on, min(self._rate_full, magnitude_kpa))
        span = self._rate_full - self._puff_on
        if span <= 0:
            hz = self._rate_max
        else:
            frac = (mag - self._puff_on) / span
            hz = self._rate_min + frac * (self._rate_max - self._rate_min)
        if hz <= 0:
            hz = self._rate_min
        return 1.0 / hz
