"""Minimal ST7735(R) driver for the 1.8" 128x160 SPI LCD.

We had to write this because both adafruit_st7735r and
adafruit_st7789 produced broken output (mostly white with sporadic
colored dots and a strip near the FFC connector) on the specific
1.8" clone wired to this prototype. The panel responds to the SPI
bus but rejects parts of the adafruit init sequences. This module
controls every byte of the init manually so we can iterate on a
known-good sequence without fighting library defaults.

The class is intentionally small: it does not implement displayio,
it does not register with the displayio singleton, and its
public API is just enough to render solid fills and the
sip-and-puff status UI.

Public API:
    fill_color(rgb565)           — fill the visible area
    fill_rect(x, y, w, h, color) — solid rectangle
    show_test_pattern(period_s)  — cycles R, G, B, W full-screen
    width / height               — pixels (after rotation)

Pin assignment is taken from the variant config dict — same SPI1
pinout as the adafruit driver path (J2 connector).
"""

import time
import busio
import digitalio


# --- ST7735(R) command set (subset we use) -----------------------
_SWRESET = 0x01
_SLPOUT  = 0x11
_INVOFF  = 0x20
_INVON   = 0x21
_DISPOFF = 0x28
_DISPON  = 0x29
_CASET   = 0x2A
_RASET   = 0x2B
_RAMWR   = 0x2C
_MADCTL  = 0x36
_COLMOD  = 0x3A
_FRMCTR1 = 0xB1
_FRMCTR2 = 0xB2
_FRMCTR3 = 0xB3
_INVCTR  = 0xB4
_PWCTR1  = 0xC0
_PWCTR2  = 0xC1
_PWCTR3  = 0xC2
_PWCTR4  = 0xC3
_PWCTR5  = 0xC4
_VMCTR1  = 0xC5
_GMCTRP1 = 0xE0
_GMCTRN1 = 0xE1

# MADCTL bits
_MADCTL_MY   = 0x80   # row order
_MADCTL_MX   = 0x40   # column order
_MADCTL_MV   = 0x20   # row/col exchange (rotation)
_MADCTL_ML   = 0x10   # vertical refresh order
_MADCTL_BGR  = 0x08   # color order: 0=RGB, 1=BGR
_MADCTL_MH   = 0x04   # horizontal refresh order


def rgb565(r, g, b):
    """Pack 8-bit-per-channel RGB into a 16-bit RGB565 value."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


# Common 16-bit colors — easier than calling rgb565() everywhere.
COLOR_BLACK = 0x0000
COLOR_WHITE = 0xFFFF
COLOR_RED   = 0xF800
COLOR_GREEN = 0x07E0
COLOR_BLUE  = 0x001F
COLOR_GRAY  = 0x8410
COLOR_ORANGE = 0xFC00


class MiniST7735:
    """Direct-control ST7735(R) 1.8" 128x160 SPI driver.

    Args:
        config: variant config dict (display_*_pin keys, etc.)
        verbose: extra diagnostic prints during init.
    """

    def __init__(self, config, verbose=False):
        self._verbose = bool(verbose)
        self._available = False

        # Resolve pin objects — same J2 pinout as the adafruit path.
        from hardware_config import _pin
        self._sclk = _pin(config["display_sck_pin"])
        self._mosi = _pin(config["display_mosi_pin"])
        self._miso = _pin(config.get("display_miso_pin"))
        self._cs   = digitalio.DigitalInOut(_pin(config["display_cs_pin"]))
        self._cs.direction  = digitalio.Direction.OUTPUT
        self._cs.value      = True
        self._dc   = digitalio.DigitalInOut(_pin(config["display_dc_pin"]))
        self._dc.direction  = digitalio.Direction.OUTPUT
        self._dc.value      = False
        rst_pin = config.get("display_reset_pin")
        if rst_pin is not None:
            self._rst = digitalio.DigitalInOut(_pin(rst_pin))
            self._rst.direction = digitalio.Direction.OUTPUT
            self._rst.value     = True
        else:
            self._rst = None

        # Backlight on (always-on for this driver — we don't dim).
        bl_pin = config.get("display_backlight_pin")
        self._bl = None
        if bl_pin is not None:
            try:
                self._bl = digitalio.DigitalInOut(_pin(bl_pin))
                self._bl.direction = digitalio.Direction.OUTPUT
                self._bl.value = True
            except Exception as e:
                print("MiniST7735: backlight pin {} unavailable ({})".format(
                    bl_pin, e))

        # Native panel size for the 1.8" 128x160. After MADCTL.MV is
        # set (rotation 90/270), width and height swap.
        self._native_w = int(config.get("display_width", 128))
        self._native_h = int(config.get("display_height", 160))
        rotation = int(config.get("display_rotation", 0))
        self._rotation = rotation
        if rotation in (90, 270):
            self.width  = self._native_h
            self.height = self._native_w
        else:
            self.width  = self._native_w
            self.height = self._native_h

        # Tab offsets from config — try (0,0) first if unsure.
        self._colstart = int(config.get("display_colstart", 0))
        self._rowstart = int(config.get("display_rowstart", 0))
        self._bgr      = bool(config.get("display_bgr", False))
        self._invert   = bool(config.get("display_invert", False))

        # SPI bus.
        baudrate = int(config.get("display_baudrate", 4_000_000))
        self._spi = busio.SPI(clock=self._sclk, MOSI=self._mosi,
                              MISO=self._miso)
        while not self._spi.try_lock():
            pass
        self._spi.configure(baudrate=baudrate, polarity=0, phase=0)
        self._spi.unlock()
        self._baudrate = baudrate

        try:
            self._hardware_reset()
            self._init_panel()
            self._available = True
            print("MiniST7735: ready (rot={} {}x{} col_off={} row_off={} "
                  "bgr={} inv={} baud={})".format(
                      rotation, self.width, self.height,
                      self._colstart, self._rowstart,
                      self._bgr, self._invert, baudrate))
        except Exception as e:
            print("MiniST7735: init failed ({})".format(e))

    @property
    def available(self):
        return self._available

    # --- Drawing ------------------------------------------------

    def fill_color(self, color):
        """Fill the entire visible area with one RGB565 color."""
        self.fill_rect(0, 0, self.width, self.height, color)

    def fill_rect(self, x, y, w, h, color):
        """Solid-color rectangle in screen coords."""
        if not self._available:
            return
        if w <= 0 or h <= 0:
            return
        x2 = x + w - 1
        y2 = y + h - 1
        if x < 0 or y < 0 or x2 >= self.width or y2 >= self.height:
            # Clip silently — the layout code can be loose without
            # crashing the device.
            x  = max(0, x)
            y  = max(0, y)
            x2 = min(self.width  - 1, x2)
            y2 = min(self.height - 1, y2)
            if x2 < x or y2 < y:
                return
        self._set_window(x, y, x2, y2)
        # Pixel buffer for one row, sent multiple times. 32 bytes
        # at a time is the safe ceiling we found on the OLED bus;
        # SPI handles long writes fine, but keep chunks reasonable.
        n = (x2 - x + 1) * (y2 - y + 1)
        chunk = bytearray(64)
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        for i in range(0, len(chunk), 2):
            chunk[i]   = hi
            chunk[i+1] = lo
        self._dc.value = True
        self._cs.value = False
        try:
            full = n // 32
            rem  = n % 32
            while not self._spi.try_lock():
                pass
            try:
                for _ in range(full):
                    self._spi.write(chunk)
                if rem:
                    self._spi.write(chunk, end=rem * 2)
            finally:
                self._spi.unlock()
        finally:
            self._cs.value = True

    def show_test_pattern(self, dwell_s=0.5):
        """Cycle the screen through R, G, B, W solid fills.

        Useful for confirming the panel is responding and the color
        order is correct. Total time ≈ 4 * dwell_s.
        """
        for color, name in (
            (COLOR_RED,   "RED"),
            (COLOR_GREEN, "GREEN"),
            (COLOR_BLUE,  "BLUE"),
            (COLOR_WHITE, "WHITE"),
        ):
            print("MiniST7735: test {} (0x{:04X})".format(name, color))
            self.fill_color(color)
            time.sleep(dwell_s)

    # --- Init internals -----------------------------------------

    def _hardware_reset(self):
        """Pulse the RESET pin (low for 1ms, then high) and wait."""
        if self._rst is None:
            return
        self._rst.value = True
        time.sleep(0.005)
        self._rst.value = False
        time.sleep(0.005)
        self._rst.value = True
        time.sleep(0.150)   # the panel needs ~120 ms after reset

    def _write_cmd(self, cmd, data=None, delay_ms=0):
        """Send command byte (DC=0) and optional data bytes (DC=1)."""
        self._cs.value = False
        try:
            while not self._spi.try_lock():
                pass
            try:
                self._dc.value = False
                self._spi.write(bytes([cmd]))
                if data:
                    self._dc.value = True
                    self._spi.write(bytes(data))
            finally:
                self._spi.unlock()
        finally:
            self._cs.value = True
        if delay_ms:
            time.sleep(delay_ms / 1000.0)

    def _init_panel(self):
        # Software reset for good measure even if we did a hardware
        # reset — clears latched state from a prior failed init.
        self._write_cmd(_SWRESET, delay_ms=150)
        self._write_cmd(_SLPOUT,  delay_ms=120)

        # Frame rate (dot inversion mode, 1-line inversion).
        # Values from Adafruit's reference R-tab init.
        self._write_cmd(_FRMCTR1, [0x05, 0x3C, 0x3C])
        self._write_cmd(_FRMCTR2, [0x05, 0x3C, 0x3C])
        self._write_cmd(_FRMCTR3, [0x05, 0x3C, 0x3C, 0x05, 0x3C, 0x3C])
        self._write_cmd(_INVCTR,  [0x03])

        # Power control sequence — same values as Adafruit reference.
        self._write_cmd(_PWCTR1, [0xA2, 0x02, 0x84])
        self._write_cmd(_PWCTR2, [0xC5])
        self._write_cmd(_PWCTR3, [0x0A, 0x00])
        self._write_cmd(_PWCTR4, [0x8A, 0x2A])
        self._write_cmd(_PWCTR5, [0x8A, 0xEE])
        self._write_cmd(_VMCTR1, [0x0E])

        # Inversion: panel default is sometimes inverted, so force
        # whichever the user asked for via display_invert.
        self._write_cmd(_INVON if self._invert else _INVOFF)

        # MADCTL — picks orientation + RGB/BGR. We construct the
        # byte from rotation + bgr flag rather than using a fixed
        # value, so the tab offsets in the user config don't need
        # to change when rotation changes.
        madctl = 0
        if self._bgr:
            madctl |= _MADCTL_BGR
        if self._rotation == 0:
            madctl |= _MADCTL_MX | _MADCTL_MY
        elif self._rotation == 90:
            madctl |= _MADCTL_MY | _MADCTL_MV
        elif self._rotation == 180:
            pass  # MX=MY=0
        elif self._rotation == 270:
            madctl |= _MADCTL_MX | _MADCTL_MV
        self._write_cmd(_MADCTL, [madctl])

        # 16-bit / pixel.
        self._write_cmd(_COLMOD, [0x05])

        # Gamma curves — these come from the Adafruit reference.
        # Mostly cosmetic; wrong values don't break the panel, just
        # tint colors slightly.
        self._write_cmd(_GMCTRP1, [
            0x02, 0x1c, 0x07, 0x12, 0x37, 0x32, 0x29, 0x2d,
            0x29, 0x25, 0x2B, 0x39, 0x00, 0x01, 0x03, 0x10,
        ])
        self._write_cmd(_GMCTRN1, [
            0x03, 0x1d, 0x07, 0x06, 0x2E, 0x2C, 0x29, 0x2D,
            0x2E, 0x2E, 0x37, 0x3F, 0x00, 0x00, 0x02, 0x10,
        ])

        # Set the active drawing window to the full visible area
        # so the first fill_color() call covers everything.
        self._set_window(0, 0, self.width - 1, self.height - 1)

        self._write_cmd(_DISPON, delay_ms=100)

    def _set_window(self, x0, y0, x1, y1):
        """Limit subsequent RAM writes to the rect [x0..x1, y0..y1]."""
        cx0 = x0 + self._colstart
        cx1 = x1 + self._colstart
        ry0 = y0 + self._rowstart
        ry1 = y1 + self._rowstart
        self._write_cmd(_CASET, [cx0 >> 8, cx0 & 0xFF,
                                 cx1 >> 8, cx1 & 0xFF])
        self._write_cmd(_RASET, [ry0 >> 8, ry0 & 0xFF,
                                 ry1 >> 8, ry1 & 0xFF])
        self._write_cmd(_RAMWR)
