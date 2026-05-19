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

        # --- Adaptive release ---------------------------------------
        # Instead of using a static puff_off / sip_off threshold for
        # release, scale the release point with the breath's peak
        # depth past on-threshold. Result: a deep sip releases sooner
        # during its ramp-back than a shallow one, so deliberate taps
        # don't sit in-state long enough to be classified as scrolls.
        #
        # release_threshold = peak +/- max(min_gap, fraction*(on - peak))
        #
        # Worked example (sip, user's spec):
        #   sip_on = -0.10, peak = -0.25, fraction = 0.5, min_gap = 0.05
        #   release = -0.25 + max(0.05, 0.5*(-0.10 - -0.25))
        #           = -0.25 + max(0.05, 0.075)
        #           = -0.175    ← user's example checks out
        self._adaptive_release = bool(config.get(
            "adaptive_release_enabled", True))
        self._adaptive_fraction = float(config.get(
            "adaptive_release_fraction", 0.5))
        self._adaptive_min_gap = float(config.get(
            "adaptive_release_min_gap_kpa", 0.05))

        self._hold_repeat   = float(config["hold_to_repeat_s"])
        # Per-direction hold-to-repeat thresholds. If unset, both fall
        # back to the symmetric hold_to_repeat_s value. Useful when one
        # direction of the breath is physically slower than the other —
        # a longer sip threshold gives the user more time to release a
        # tap before it gets classified as the start of a scroll.
        self._puff_hold_repeat = float(config.get(
            "puff_hold_to_repeat_s", self._hold_repeat))
        self._sip_hold_repeat  = float(config.get(
            "sip_hold_to_repeat_s",  self._hold_repeat))
        self._rate_min  = float(config["repeat_min_hz"])
        self._rate_max  = float(config["repeat_max_hz"])
        self._rate_full = float(config["repeat_full_scale_kpa"])
        # Linear scale factor applied to the magnitude-in-kPa before
        # clamping to [min_hz, max_hz]. With the default factor of 1.0
        # the mapping is intentionally 1:1 — 1 kPa → 1 Hz, 10 kPa →
        # 10 Hz. Bump above 1.0 to make scrolling faster per kPa of
        # effort; drop below 1.0 for finer control on strong breaths.
        self._rate_factor = float(config.get("repeat_rate_factor", 1.0))
        # TODO: logarithmic mapping option. Some users may want a
        # curve that's steep near the on-threshold (so a light puff
        # already moves) but plateaus toward the max so very hard
        # puffs don't race. Plan: repeat_rate_curve = "linear"
        # (current) | "logarithmic". Log curve sketch:
        #     hz = min_hz + (max_hz - min_hz)
        #            * log(mag/min_kpa) / log(full_kpa/min_kpa)
        # with mag clamped at >=min_kpa so the log stays defined.
        self._rate_curve = str(config.get(
            "repeat_rate_curve", "linear")).strip().lower()
        self._verbose   = bool(config.get("verbose", False))

        self._state = _IDLE
        self._t_state_entered = time.monotonic()
        self._t_pending_until = 0.0   # deadline for double detection
        self._t_next_repeat   = 0.0   # next time a *_repeat tick is due
        self._double_consumed = False
        # Tracks whether the current breath crossed into hold-to-repeat
        # territory. If it did, we treat the release as the natural end
        # of a scroll and suppress the single-event emission — otherwise
        # every sustained puff/sip would end with a spurious "select".
        self._repeat_emitted  = False
        # Signed peak (most positive for puff, most negative for sip)
        # reached during the current PUFF_ON / SIP_ON. Resets on entry.
        self._peak_kpa        = 0.0
        # Set in PUFF_PEND / SIP_PEND once pressure has fully crossed
        # back over the on-threshold — only then do we accept the next
        # transition as a double-event. Needed because the adaptive
        # release threshold sits *between* peak and on-threshold, so
        # entering PEND with pressure still past on-threshold should
        # NOT immediately re-fire a double.
        self._pend_released   = False

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

    # --- Adaptive release helpers -------------------------------

    def _puff_release_threshold(self):
        """Pressure value below which puff is considered released.
        Adaptive when enabled — scales with how strongly the user
        actually puffed — so deeper puffs release faster.
        """
        if not self._adaptive_release:
            return self._puff_off
        gap = max(self._adaptive_min_gap,
                  self._adaptive_fraction * (self._peak_kpa - self._puff_on))
        return self._peak_kpa - gap

    def _sip_release_threshold(self):
        if not self._adaptive_release:
            return self._sip_off
        gap = max(self._adaptive_min_gap,
                  self._adaptive_fraction * (self._sip_on - self._peak_kpa))
        return self._peak_kpa + gap

    def _poll_puff_pending(self, p_kpa, now):
        # With adaptive release, we enter PEND while pressure is still
        # *above* puff_on — wait for it to fully cross back below
        # puff_on before treating a new puff as a double.
        if not self._pend_released and p_kpa < self._puff_on:
            self._pend_released = True
        elif self._pend_released and p_kpa >= self._puff_on:
            self._enter(_PUFF_ON, now, double_pending=True)
            return "double_puff"
        # Window expired → fire the single puff we held back.
        if now >= self._t_pending_until:
            self._enter(_IDLE, now)
            return "puff"
        return None

    def _poll_sip_pending(self, p_kpa, now):
        # Symmetric: wait for full release past sip_on before
        # accepting a re-trigger as a double-sip.
        if not self._pend_released and p_kpa > self._sip_on:
            self._pend_released = True
        elif self._pend_released and p_kpa <= self._sip_on:
            self._enter(_SIP_ON, now, double_pending=True)
            return "double_sip"
        if now >= self._t_pending_until:
            self._enter(_IDLE, now)
            return "sip"
        return None

    def _poll_puff_on(self, p_kpa, now):
        # Track peak depth (signed) — drives the adaptive release.
        if p_kpa > self._peak_kpa:
            self._peak_kpa = p_kpa

        release_threshold = self._puff_release_threshold()
        if p_kpa < release_threshold:
            # If we entered PUFF_ON as the second half of a double-puff,
            # the event was already emitted — just go idle.
            if self._double_consumed:
                self._enter(_IDLE, now)
                return None
            # If repeats already fired during this breath, treat the
            # release as the natural end of a scroll. Skip the
            # pending/single emission so we don't queue a spurious
            # "select" after every long scroll.
            if self._repeat_emitted:
                self._enter(_IDLE, now)
                return None
            self._t_pending_until = now + self._double_puff_window
            self._enter(_PUFF_PEND, now)
            return None

        # Still held — once past puff_hold_to_repeat_s, emit ticks at
        # a pressure-scaled rate.
        held = now - self._t_state_entered
        if held >= self._puff_hold_repeat and now >= self._t_next_repeat:
            self._t_next_repeat = now + self._tick_period(p_kpa)
            self._repeat_emitted = True
            return "puff_repeat"
        return None

    def _poll_sip_on(self, p_kpa, now):
        if p_kpa < self._peak_kpa:
            self._peak_kpa = p_kpa

        release_threshold = self._sip_release_threshold()
        if p_kpa > release_threshold:
            # Same double-consumed dance as the puff path.
            if self._double_consumed:
                self._enter(_IDLE, now)
                return None
            # Suppress the single-event on release if we already
            # scrolled (see _poll_puff_on for rationale).
            if self._repeat_emitted:
                self._enter(_IDLE, now)
                return None
            self._t_pending_until = now + self._double_sip_window
            self._enter(_SIP_PEND, now)
            return None

        held = now - self._t_state_entered
        if held >= self._sip_hold_repeat and now >= self._t_next_repeat:
            self._t_next_repeat = now + self._tick_period(-p_kpa)
            self._repeat_emitted = True
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
        # Fresh breath → repeat-tracking + peak tracking reset so a
        # long scroll followed by a short tap still gets the tap event,
        # and the adaptive release threshold is computed from the
        # *current* breath only.
        if new_state in (_PUFF_ON, _SIP_ON):
            self._repeat_emitted = False
            self._peak_kpa = 0.0
        # PEND entry needs a fresh "has pressure crossed back over the
        # on-threshold yet?" flag — see _poll_*_pending.
        if new_state in (_PUFF_PEND, _SIP_PEND):
            self._pend_released = False

    def _tick_period(self, magnitude_kpa):
        """Return seconds-per-tick for a held breath at this magnitude.

        Default rule: ``rate_hz = magnitude_kpa * repeat_rate_factor``,
        with the magnitude clamped to ``repeat_full_scale_kpa`` from
        above and the rate clamped to ``[repeat_min_hz, repeat_max_hz]``
        on both ends.

        With the shipping defaults (factor 1.0, full-scale 10 kPa,
        min/max 1/10 Hz) this gives a clean 1:1 mapping: 1 kPa pulses
        once a second, 10 kPa pulses ten times a second, and anything
        above 10 kPa is clamped to 10 Hz.
        """
        mag = max(0.0, min(self._rate_full, magnitude_kpa))
        if self._rate_curve == "logarithmic":
            # Sketch only — see __init__ TODO. Falls through to linear.
            pass
        hz = mag * self._rate_factor
        if hz < self._rate_min:
            hz = self._rate_min
        elif hz > self._rate_max:
            hz = self._rate_max
        return 1.0 / hz
