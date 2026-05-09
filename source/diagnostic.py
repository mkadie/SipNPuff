"""Benchtop diagnostic / calibration helper.

Streams pressure-sensor readings and classifier state to the serial
console without driving any outputs. Intended for:

  * Sanity-checking the voltage divider and decoupling
  * Picking sip/puff thresholds before flipping mode=run
  * Logging breath traces for a user-experience study

Switch to this mode by setting ``mode=diagnostic`` in /config.txt
on the CIRCUITPY drive — no code change required.

Output format (CSV-ish, one line per sample):

    diag t=12.345 raw=21345 v=1.073 sensor_v=1.610 abs=0.123 g=0.011 state=idle event=
"""

import time


def run(sensor, classifier, config, duration_s=None, display=None):
    """Stream readings until duration_s elapses (None → forever).

    Args:
        sensor: PressureSensor instance (already baseline-calibrated).
        classifier: BreathClassifier instance to display state from.
        config: runtime config dict.
        duration_s: optional cap, mostly used by automated tests.
        display: optional DisplayManager — if provided, visual
            bargraphs update in lockstep with the serial trace,
            so threshold picking can be done by eye.
    """
    poll_s = float(config.get("poll_period_s", 0.01))
    # Throttle the print to 50 Hz max — terminals don't like 200 Hz.
    print_interval = max(poll_s, 0.02)
    next_print = time.monotonic()
    t_start = time.monotonic()

    print("diag: streaming (poll={}s, print={}s)".format(poll_s, print_interval))
    print("diag: header t,raw,v,sensor_v,abs_kpa,gauge_kpa,state,event")

    event_counts = {"puff": 0, "double_puff": 0, "puff_repeat": 0,
                    "sip": 0, "sip_repeat": 0}

    try:
        while True:
            now = time.monotonic()
            if duration_s is not None and (now - t_start) >= duration_s:
                break

            raw = sensor.raw_average()
            v   = sensor.voltage(raw)
            sv  = sensor.sensor_v(raw)
            abs_p = sensor.pressure_kpa(raw)
            g_p   = abs_p - sensor.baseline_kpa
            event = classifier.poll(g_p)
            if event is not None:
                event_counts[event] = event_counts.get(event, 0) + 1

            if display is not None:
                display.update(g_p, classifier.state)

            if now >= next_print:
                next_print = now + print_interval
                print("diag t={:.3f} raw={} v={:.3f} sensor_v={:.3f} "
                      "abs={:.3f} g={:.3f} state={} event={}".format(
                          now - t_start, raw, v, sv, abs_p, g_p,
                          classifier.state, event or ""))

            time.sleep(poll_s)
    except KeyboardInterrupt:
        print("diag: interrupted")

    print("diag: event counts {}".format(event_counts))
