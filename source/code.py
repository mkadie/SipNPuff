"""T-Rex Sip-N-Puff entry point.

CircuitPython runs code.py at boot. Keep this file minimal — all
real logic lives in sip_puff_device.SipPuffDevice. To change
thresholds or switch into diagnostic mode, edit /config.txt on
the CIRCUITPY drive (no reflashing required).
"""

from sip_puff_device import SipPuffDevice


SipPuffDevice().run()
