"""Status display abstraction for the Sip-N-Puff device.

Supports five controllers, picked via ``display_controller`` (or a
``display_preset`` from hardware_config.DISPLAY_PRESETS):

    Controller   Bus    Typical panel              Notes
    -----------  -----  -------------------------  --------------------
    st7735r      SPI    1.8" 128x160 / 1.44" / 0.96"  TFT, color
    st7789       SPI    1.3"-2.4" IPS              TFT, color
    ili9341      SPI    2.2"-3.2" 240x320          TFT, color
    gc9a01       SPI    1.28" 240x240 round        TFT, color
    ssd1306      I2C    0.96"/1.3" 128x64 OLED     Monochrome, J1 connector

The SPI panels share the J2 wiring (Section 10.5 of the project doc):

    SCK  -> GP10        DC   -> GP14
    MOSI -> GP11        RST  -> GP15
    MISO -> GP12        LED  -> GP16   (PWM backlight; tie 3V3 if unused)
    CS   -> GP13

The I2C panel (SSD1306) uses J1:

    SCL  -> GP5
    SDA  -> GP4
    VCC  -> 3V3
    GND  -> GND

The display is opt-in via ``display_enabled``. If the hardware is
missing or the driver library isn't installed, the manager silently
disables itself so the device keeps running without a screen.

Layout adapts to screen size:

    color LCD (160x128 after rot=270):     OLED (128x64):
    +------------------------------+       +-------------------+
    | T-Rex Sip-N-Puff   state:    |       | state:idle        |
    |                              |       | P: +0.42 kPa      |
    | P: +0.42 kPa                 |       | P [###--------]   |
    | PUFF [######-------]   0.42  |       | S [-----------]   |
    | SIP  [-----------]    0.00   |       +-------------------+
    +------------------------------+
"""

import time

from hardware_config import _pin


# Controllers that render in monochrome — selects a different layout
# and skips the (color-only) R/G/B/W self-test.
_MONO_CONTROLLERS = ("ssd1306",)


class DisplayManager:
    """Status display for the breath-classifier output.

    Args:
        config: variant config dict from hardware_config.load_config().
        thresholds: dict with keys ``puff_on``, ``sip_on``, ``full_scale``
            so the bargraphs can scale and draw the threshold tick.
            Pulled from the BreathClassifier config at construction.
    """

    def __init__(self, config, thresholds, i2c=None):
        # Optional shared I2C bus, used by the SSD1306 path so that
        # the LPS28 and the OLED can coexist on GP4/GP5.
        self._shared_i2c = i2c
        self._enabled = bool(config.get("display_enabled", False))
        self._update_period = 1.0 / max(1.0, float(
            config.get("display_update_hz", 10)))
        self._verbose = bool(config.get("verbose", False))

        self._puff_on   = float(thresholds["puff_on"])
        self._sip_on    = float(thresholds["sip_on"])
        self._full_scale = float(thresholds["full_scale"])

        # Geometry — set by _build_scene() based on actual panel size.
        self._bar_x = 0
        self._bar_w = 1
        self._bar_h = 1

        self._available = False
        self._is_mono = False
        self._display = None
        self._backlight = None
        self._pressure_label = None
        self._state_label = None
        # MPX5010DP (analog differential) — primary sensor.
        self._puff_value_label = None
        self._sip_value_label = None
        self._puff_fill_rect = None
        self._sip_fill_rect = None
        # LPS28 (I2C absolute) — secondary sensor, gauge-zeroed swings
        # are much smaller than the MPX so the LPS bars use their own
        # full-scale (display_lps_full_scale_kpa, default 0.1 kPa).
        self._lps_puff_value_label = None
        self._lps_sip_value_label = None
        self._lps_puff_fill_rect = None
        self._lps_sip_fill_rect = None
        self._lps_full_scale = 0.1
        self._t_next_update = 0.0
        self._last_rendered = None

        # Event-indicator boxes at the bottom of the screen. Four
        # named slots: "up", "down", "puff_click", "sip_click". The
        # dispatcher calls flash(name) on every dispatched event;
        # this module decides visibility:
        #   * Click boxes (puff_click / sip_click): solid for
        #     ``_box_solid_s`` after the event, then off.
        #   * Stream boxes (up / down): visibility *toggles* with
        #     each event so the user sees one flip per signal. After
        #     ``_box_solid_s`` of silence the box goes off regardless
        #     of its current parity.
        self._box_rects        = {}     # name -> vectorio.Rectangle
        self._box_last_event   = {}     # name -> time.monotonic()
        self._box_flash_count  = {}     # name -> running event count
        for _name in ("up", "down", "puff_click", "sip_click"):
            self._box_last_event[_name]  = -1.0e9
            self._box_flash_count[_name] = 0
        # Click boxes (puff_click / sip_click) latch on for this long.
        self._box_click_on_s   = 1.0
        # Up/Down toggle per event; the box must go off if no new
        # event arrives within this window so the user can see it
        # "stop" once they release the breath. Also: the toggle
        # naturally yields ~50% off-time at any event rate the
        # refresh loop can keep up with.
        self._box_stream_off_s = 0.5

        if not self._enabled:
            print("Display: disabled by config")
            return

        self._init_display(config)

    @property
    def available(self):
        """True if the display initialised and is being driven."""
        return self._available

    # --- Init ----------------------------------------------------

    def _init_display(self, config):
        controller = str(config.get("display_controller", "st7735r")).lower()
        self._is_mono = controller in _MONO_CONTROLLERS

        # The custom mini ST7735 path is its own animal — bypass the
        # adafruit driver chain entirely and just run a continuous
        # R/G/B/W test cycle so we can confirm the panel hardware
        # works at all. UI rendering on top of MiniST7735 isn't
        # implemented yet; the test cycle is the whole point.
        if controller == "mini_st7735":
            try:
                # Release any prior displayio claim on the SPI/CS pins
                # so MiniST7735 can take over cleanly.
                import displayio
                displayio.release_displays()
                from mini_st7735 import MiniST7735
                drv = MiniST7735(config, verbose=self._verbose)
                if drv.available:
                    self._display = drv
                    self._available = False  # no UI rendering yet
                    print("MiniST7735: running test pattern; UI rendering "
                          "via mini driver not implemented")
                    drv.show_test_pattern(dwell_s=0.8)
                    drv.fill_color(0x0000)  # leave the screen black
                else:
                    print("MiniST7735: driver reported not-available")
            except Exception as e:
                print("MiniST7735: load failed ({})".format(e))
                try:
                    import traceback
                    traceback.print_exception(e)
                except Exception:
                    pass
            return

        # All controllers share these imports. Driver imports are
        # branched below so a missing library only matters when the
        # user actually picked that controller.
        try:
            import busio
            import displayio
            import terminalio
            import digitalio
            import vectorio
            from adafruit_display_text.label import Label
            from adafruit_display_shapes.rect import Rect
        except ImportError as e:
            print("Display: core libs missing ({}) — install via "
                  "circup: adafruit_display_text "
                  "adafruit_display_shapes".format(e))
            return

        try:
            displayio.release_displays()
            if controller == "ssd1306":
                ok = self._init_i2c_panel(config, controller, busio,
                                          displayio, digitalio)
            else:
                ok = self._init_spi_panel(config, controller, busio,
                                          displayio, digitalio)
            if not ok:
                return

            # --- Boot self-test (color panels only) ---
            if not self._is_mono and bool(config.get(
                    "display_test_pattern", False)):
                self._self_test(displayio)

            # --- Build static scene ---
            self._build_scene(displayio, terminalio, Label, Rect,
                              vectorio, config)
            self._available = True

            res_w = self._display.width
            res_h = self._display.height
            print("Display: {} ready ({}x{}, mono={})".format(
                controller.upper(), res_w, res_h, self._is_mono))
        except Exception as e:
            print("Display: init failed ({})".format(e))
            try:
                import traceback
                traceback.print_exception(e)
            except Exception:
                pass
            self._available = False

    def _init_spi_panel(self, config, controller, busio, displayio, digitalio):
        try:
            from fourwire import FourWire
            if controller == "st7789":
                from adafruit_st7789 import ST7789 as _Driver
            elif controller == "ili9341":
                from adafruit_ili9341 import ILI9341 as _Driver
            elif controller == "gc9a01":
                from gc9a01 import GC9A01 as _Driver
            elif controller == "st7735r":
                from adafruit_st7735r import ST7735R as _Driver
            else:
                print("Display: unknown SPI controller '{}', using "
                      "st7735r".format(controller))
                from adafruit_st7735r import ST7735R as _Driver
                controller = "st7735r"
        except ImportError as e:
            print("Display: SPI driver missing for '{}' ({}) — install "
                  "via circup: adafruit_st7735r adafruit_st7789 "
                  "adafruit_ili9341 gc9a01".format(controller, e))
            return False

        spi = busio.SPI(
            clock=_pin(config["display_sck_pin"]),
            MOSI=_pin(config["display_mosi_pin"]),
            MISO=_pin(config.get("display_miso_pin")),
        )
        bus = FourWire(
            spi,
            command=_pin(config["display_dc_pin"]),
            chip_select=_pin(config["display_cs_pin"]),
            reset=_pin(config["display_reset_pin"]),
            baudrate=int(config["display_baudrate"]),
        )

        width  = int(config["display_width"])
        height = int(config["display_height"])
        rotation = int(config["display_rotation"])
        colstart = int(config.get("display_colstart", 0))
        rowstart = int(config.get("display_rowstart", 0))
        bgr      = bool(config.get("display_bgr", False))
        invert   = bool(config.get("display_invert", False))

        kw = dict(width=width, height=height, rotation=rotation)
        if controller == "st7735r":
            # Mirror the known-working init from
            # documents/thermister_code.py (cheap1_8display branch):
            # only width/height/rotation are passed and the library's
            # built-in colstart/rowstart/bgr/invert defaults are kept.
            # Overriding those defaults with stale config guesses is
            # what was producing the all-white-with-color-dots failure.
            pass
        elif controller == "st7789":
            kw["colstart"] = colstart
            kw["rowstart"] = rowstart
            kw["bgr"] = bgr
        elif controller == "ili9341":
            if bgr:
                kw["bgr"] = True
        # gc9a01: no offset/bgr/invert kwargs.

        self._display = _Driver(bus, **kw)
        print("Display: {} on SPI {}x{} rot={} kwargs={} baud={}".format(
            controller.upper(), width, height, rotation,
            {k: kw[k] for k in kw if k not in ("width", "height", "rotation")},
            int(config["display_baudrate"])))

        # Backlight is SPI-only (OLED panels self-emit).
        bl_name = config.get("display_backlight_pin")
        if bl_name:
            try:
                self._backlight = digitalio.DigitalInOut(_pin(bl_name))
                self._backlight.direction = digitalio.Direction.OUTPUT
                self._backlight.value = True
            except Exception as e:
                print("Display: backlight pin {} unavailable ({})".format(
                    bl_name, e))
        return True

    def _enable_internal_pullups(self, digitalio, sda, scl):
        """Force a clean HIGH idle state on SDA + SCL.

        Empirical finding on RP2350 / CP 10.2.0: a previous failed
        ``busio.I2C`` attempt can leave the I2C state machine holding
        SDA/SCL low even after the constructor raised. The simple
        "configure as input + Pull.UP" trick isn't strong enough to
        unstick that.

        Push-pull driving HIGH for 50 ms forces a clean line state,
        charges any bus capacitance, and lets a real external pull-up
        on a powered I2C device take over once we drop back to input.
        Then ``busio.I2C``'s 10 µs sample sees a healthy HIGH and the
        constructor goes through.
        """
        for pin in (sda, scl):
            io = digitalio.DigitalInOut(pin)
            io.direction = digitalio.Direction.OUTPUT
            io.value = True
            time.sleep(0.05)
            io.direction = digitalio.Direction.INPUT
            io.pull = digitalio.Pull.UP
            time.sleep(0.001)
            io.deinit()

    def _init_i2c_panel(self, config, controller, busio, displayio, digitalio):
        # We do NOT use adafruit_ssd1306 or adafruit_displayio_ssd1306.
        # Both layered drivers wedge on this hardware (RP2350 +
        # busio.I2C + multi-device bus) — diagnosed across many
        # iterations. Instead we use a tiny inline driver that:
        #   1. issues one single contiguous init writeto (which works)
        #   2. holds the bus lock and chunks frame writes to 32 bytes
        #      per I2C transaction (the empirical "no clock-stretch
        #      stall" limit on this board)
        try:
            import adafruit_framebuf
        except ImportError as e:
            print("Display: framebuf lib missing ({}) — install via "
                  "circup: adafruit_framebuf".format(e))
            return False

        addr = int(config.get("display_i2c_address", 0x3C))
        freq = int(config.get("display_i2c_frequency", 400_000))

        # Prefer the shared bus that sip_puff_device handed in — keeps
        # the LPS28 and the OLED on a single busio.I2C instance.
        if self._shared_i2c is not None:
            i2c = self._shared_i2c
            i2c_kind = "shared"
        else:
            sda = _pin(config["display_i2c_sda_pin"])
            scl = _pin(config["display_i2c_scl_pin"])
            # busio.I2C samples SDA/SCL and refuses to come up if either
            # reads LOW. On a board with no external 10 kΩ pull-ups the
            # call raises "No pull up found". The pull-up trick claims
            # each line via digitalio with Pull.UP and then deinits —
            # on RP2350 the pad's pull-up bit persists across the
            # function-mux change long enough for busio.I2C to see HIGH.
            try:
                self._enable_internal_pullups(digitalio, sda, scl)
            except Exception as e:
                print("Display: pull-up prep failed ({})".format(e))
            i2c = None
            i2c_kind = "busio"
            try:
                i2c = busio.I2C(scl, sda, frequency=freq)
            except (RuntimeError, ValueError) as e:
                print("Display: busio.I2C still failed ({}). The OLED is "
                      "likely not wired to GP{}/GP{} or has no power. "
                      "Falling back to bitbangio (note: CP 10.2.0 RP2350 "
                      "bitbangio.I2C has a known timeout-validator bug "
                      "that may also fail).".format(
                          e,
                          str(config["display_i2c_scl_pin"]).replace("GP", ""),
                          str(config["display_i2c_sda_pin"]).replace("GP", "")))
                try:
                    import bitbangio
                    i2c = bitbangio.I2C(scl, sda,
                                        frequency=100_000, timeout=255)
                    i2c_kind = "bitbang"
                except Exception as e2:
                    print("Display: bitbangio fallback also failed ({}).".format(e2))
                    return False

        width  = int(config["display_width"])
        height = int(config["display_height"])

        # Brief settle so a freshly-powered SSD1306 has time to
        # finish its own boot before we send init commands.
        time.sleep(0.05)

        try:
            self._display = _MiniSSD1306(i2c, addr, width, height,
                                         adafruit_framebuf)
            self._display.fill(0)
            self._display.show()
        except Exception:
            self._scan_for_diagnostic(i2c, config)
            raise

        # Post-init scan, purely for diagnostic logging.
        self._scan_for_diagnostic(i2c, config)

        print("Display: SSD1306 on I2C ({}) SDA={} SCL={} addr=0x{:02X} "
              "freq={}".format(i2c_kind,
                               config["display_i2c_sda_pin"],
                               config["display_i2c_scl_pin"], addr, freq))
        return True

    def _scan_for_diagnostic(self, i2c, config):
        try:
            while not i2c.try_lock():
                pass
            found = i2c.scan()
            i2c.unlock()
            if found:
                print("Display: I2C scan found {}".format(
                    [hex(a) for a in found]))
            else:
                print("Display: I2C scan found nothing on SDA={} "
                      "SCL={}".format(
                          config["display_i2c_sda_pin"],
                          config["display_i2c_scl_pin"]))
        except Exception as e:
            print("Display: I2C scan failed ({})".format(e))

    # --- Self-test ---------------------------------------------

    def _self_test(self, displayio):
        """Flash R, G, B, W solid fills (color panels only).

        Skipped automatically for mono OLEDs — there's nothing useful
        to verify by flashing white repeatedly on a 1-bit panel.
        """
        w = self._display.width
        h = self._display.height
        colors = (
            (0xFF0000, "RED"),
            (0x00FF00, "GREEN"),
            (0x0000FF, "BLUE"),
            (0xFFFFFF, "WHITE"),
        )
        for rgb, name in colors:
            try:
                bm = displayio.Bitmap(w, h, 1)
                pal = displayio.Palette(1)
                pal[0] = rgb
                grp = displayio.Group()
                grp.append(displayio.TileGrid(bm, pixel_shader=pal))
                self._display.root_group = grp
                self._display.refresh()
                print("Display: self-test {} (0x{:06X})".format(name, rgb))
                time.sleep(0.6)
            except Exception as e:
                print("Display: self-test {} failed ({})".format(name, e))
                return

    # --- Scene -------------------------------------------------

    def _build_scene(self, displayio, terminalio, Label, Rect, vectorio,
                     config):
        if self._is_mono:
            # Framebuf driver — no displayio scene to build. Just
            # set up the geometry for update() to render against.
            self._setup_mono_geometry()
        else:
            self._build_color_scene(displayio, terminalio, Label, Rect,
                                    vectorio, config)

    def _build_color_scene(self, displayio, terminalio, Label, Rect,
                           vectorio, config):
        bg     = int(config["display_bg_color"])
        text_c = int(config["display_text_color"])
        puff_c = int(config["display_puff_color"])
        sip_c  = int(config["display_sip_color"])
        thr_c  = int(config["display_threshold_color"])

        # LPS28 gauge swings are typically ~10–100x smaller than the
        # MPX5010DP so we let the LPS bars use a separate (smaller)
        # full-scale. Configurable via display_lps_full_scale_kpa.
        self._lps_full_scale = float(config.get(
            "display_lps_full_scale_kpa", 0.1))

        w = self._display.width
        h = self._display.height
        print("Display: scene layout {}x{} (4-bar MPX+LPS, mpx_full={} kPa, "
              "lps_full={} kPa)".format(
                  w, h, self._full_scale, self._lps_full_scale))

        # 160x128 layout — four bar rows, each 18 px tall:
        #   y=4   header: title + state
        #   y=22  MPX P  bar  value
        #   y=40  MPX S  bar  value
        #   y=64  LPS P  bar  value      (gap above visually separates)
        #   y=82  LPS S  bar  value
        header_y    =   4
        mpx_puff_y  =  22
        mpx_sip_y   =  40
        lps_puff_y  =  64
        lps_sip_y   =  82

        # Bargraph geometry — same x/width for all four rows so they
        # align vertically and are easy to compare at a glance.
        self._bar_x = 40
        self._bar_w = max(40, w - self._bar_x - 30)
        self._bar_h = 8

        root = displayio.Group()
        bg_bitmap = displayio.Bitmap(w, h, 1)
        bg_pal = displayio.Palette(1)
        bg_pal[0] = bg
        root.append(displayio.TileGrid(bg_bitmap, pixel_shader=bg_pal))

        # --- Header --------------------------------------------------
        root.append(Label(terminalio.FONT, text="T-Rex Sip-N-Puff",
                          color=text_c, x=4, y=header_y + 4))
        self._state_label = Label(
            terminalio.FONT, text="state: idle",
            color=text_c, x=max(4, w - 78), y=header_y + 4)
        root.append(self._state_label)

        # The big "P: ..." readout was redundant once we have four
        # value labels next to the bars, so it's gone.
        self._pressure_label = None

        # --- Helper: build one labelled bargraph row ---------------
        # Reused four times so the layout stays consistent and any
        # tweak to row geometry happens in one place.
        def _build_row(y_top, label_text, fill_color, threshold_kpa,
                       full_scale, value_text):
            text_y = y_top + self._bar_h // 2 + 1
            root.append(Label(terminalio.FONT, text=label_text,
                              color=fill_color, x=4, y=text_y))
            root.append(Rect(self._bar_x, y_top,
                             self._bar_w, self._bar_h,
                             outline=text_c, fill=bg))
            # Fill bar — vectorio.Rectangle has a mutable .width, unlike
            # adafruit_display_shapes.Rect which becomes read-only after
            # construction in newer bundle releases. Without this the
            # bars draw at their initial 1-pixel width and never grow,
            # even though the numeric labels update every tick.
            fill_pal = displayio.Palette(1)
            fill_pal[0] = fill_color
            fill_rect = vectorio.Rectangle(
                pixel_shader=fill_pal,
                width=1, height=max(1, self._bar_h - 2),
                x=self._bar_x + 1, y=y_top + 1)
            root.append(fill_rect)
            # Threshold tick — only drawn when threshold_kpa > 0.
            # LPS rows pass 0 (no event semantics tied to LPS yet).
            if threshold_kpa > 0:
                thr_x = self._bar_x + self._bar_pixels(
                    threshold_kpa, full_scale)
                root.append(Rect(thr_x, y_top - 2, 1, self._bar_h + 4,
                                 fill=thr_c))
            value_label = Label(
                terminalio.FONT, text=value_text, color=fill_color,
                x=self._bar_x + self._bar_w + 4, y=text_y)
            root.append(value_label)
            return fill_rect, value_label

        # --- MPX rows ------------------------------------------------
        self._puff_fill_rect, self._puff_value_label = _build_row(
            mpx_puff_y, "MPX P", puff_c,
            self._puff_on, self._full_scale, "0.00")
        self._sip_fill_rect, self._sip_value_label = _build_row(
            mpx_sip_y, "MPX S", sip_c,
            -self._sip_on, self._full_scale, "0.00")

        # --- LPS rows ------------------------------------------------
        self._lps_puff_fill_rect, self._lps_puff_value_label = _build_row(
            lps_puff_y, "LPS P", puff_c,
            0.0, self._lps_full_scale, " --- ")
        self._lps_sip_fill_rect, self._lps_sip_value_label = _build_row(
            lps_sip_y, "LPS S", sip_c,
            0.0, self._lps_full_scale, " --- ")

        # --- Bottom row: 4 event-indicator boxes ----------------------
        # Slots, left-to-right: Up (CW), Dn (CCW), SipC (single sip),
        # PufC (single puff). Each has a labelled outline + a filled
        # vectorio.Rectangle whose .hidden is toggled at update() time.
        self._build_event_boxes(displayio, Rect, Label, terminalio,
                                vectorio, w, h, bg, text_c, puff_c, sip_c,
                                root)

        self._display.root_group = root

    def _build_event_boxes(self, displayio, Rect, Label, terminalio,
                           vectorio, w, h, bg, text_c, puff_c, sip_c,
                           root):
        """Lay out the bottom-of-screen event indicator boxes."""
        box_h    = 14
        box_pad  = 4
        gap      = 4
        # Reserve a single row hugging the bottom — labels above, fills
        # below. Total content height ≈ 22 px.
        fill_y   = h - box_h - 2
        label_y  = fill_y - 8
        slots = (
            ("up",         "UP",  puff_c),
            ("down",       "DN",  sip_c),
            ("sip_click",  "SIP", sip_c),
            ("puff_click", "PUF", puff_c),
        )
        # Sized to fit four slots with gaps within the panel width.
        total_gap = gap * (len(slots) - 1)
        box_w = max(20, (w - 2 * box_pad - total_gap) // len(slots))
        x = box_pad
        for name, label_text, color in slots:
            # Centred small label above the box.
            root.append(Label(terminalio.FONT, text=label_text,
                              color=text_c, x=x + 4, y=label_y))
            # Static outline.
            root.append(Rect(x, fill_y, box_w, box_h,
                             outline=text_c, fill=bg))
            # Toggleable fill — start hidden.
            pal = displayio.Palette(1)
            pal[0] = color
            fill = vectorio.Rectangle(
                pixel_shader=pal,
                width=max(1, box_w - 2),
                height=max(1, box_h - 2),
                x=x + 1, y=fill_y + 1)
            fill.hidden = True
            root.append(fill)
            self._box_rects[name] = fill
            x += box_w + gap

    def _setup_mono_geometry(self):
        """Stash the per-frame mono layout coordinates.

        The framebuf driver redraws the whole screen each tick so
        there's no static scene to assemble — we just need to know
        where each element goes.

        Layout on a 128x64 OLED:

            y=0   "SipNPuff"                 state[:6]
            y=10  MP   [bar...........]   0.42
            y=22  MS   [bar...........]   0.00
            y=38  LP   [bar...........]   0.05    (visible gap above
            y=50  LS   [bar...........]   0.00     to separate sensors)

        On a 128x32 panel only the title row + the two MPX bars fit
        — LPS rows are silently clipped.
        """
        w = self._display.width
        h = self._display.height
        self._mono_w = w
        self._mono_h = h
        self._mono_is_tall = h >= 64

        if self._mono_is_tall:
            self._mono_title_y = 0
            self._mono_mpx_p_y = 10
            self._mono_mpx_s_y = 22
            self._mono_lps_p_y = 38
            self._mono_lps_s_y = 50
        else:
            # 128x32: drop LPS rows; MPX-only.
            self._mono_title_y = 0
            self._mono_mpx_p_y = 10
            self._mono_mpx_s_y = 22
            self._mono_lps_p_y = None
            self._mono_lps_s_y = None

        # Bargraph geometry. 32 px on the right is enough room for a
        # 4-char value label like "0.42" or "0.05" at terminalio's
        # native 6 px per char.
        self._bar_x = 14
        self._bar_w = max(20, w - self._bar_x - 32)
        self._bar_h = 6

        # Initial paint so the screen isn't blank before the first
        # update() call (display_update_hz throttles redraws).
        self._render_mono(0.0, "idle", None)

    # --- Per-frame update ---------------------------------------

    def flash(self, name):
        """Record an event for one of the indicator boxes.

        Click boxes use solid-then-off; stream boxes toggle parity on
        every call so each signal is a visible state change at rates
        the refresh loop can keep up with. Fresh series after a long
        gap always starts with the box ON, so the user catches the
        first event regardless of previous parity.
        """
        if not self._available or name not in self._box_last_event:
            return
        now = time.monotonic()
        last = self._box_last_event[name]
        # Different "fresh series" thresholds for the two box kinds —
        # but in both cases the next event should look like an ON pulse
        # from a clean state.
        gap_threshold = (self._box_stream_off_s
                         if name in ("up", "down")
                         else self._box_click_on_s)
        if (now - last) > gap_threshold:
            self._box_flash_count[name] = 1
        else:
            self._box_flash_count[name] += 1
        self._box_last_event[name] = now

    def _update_event_boxes(self, now):
        """Apply the visibility rule per box."""
        for name, rect in self._box_rects.items():
            age = now - self._box_last_event[name]
            if name in ("up", "down"):
                # Toggle parity per event, but force OFF after the
                # stream-off window so the box clears when the user
                # releases. Parity gives ≈50% off naturally — at very
                # high event rates the display refresh may not keep up
                # and the box can appear stuck; that's a known limit.
                if age > self._box_stream_off_s:
                    visible = False
                else:
                    visible = (self._box_flash_count[name] % 2) == 1
            else:
                # Click boxes: solid for the whole on-window.
                visible = age <= self._box_click_on_s
            hide = not visible
            if rect.hidden != hide:
                rect.hidden = hide

    def update(self, p_kpa, state, lps_kpa=None):
        """Refresh the screen if enough time has passed.

        Args:
            p_kpa: MPX5010DP baseline-zeroed pressure (signed kPa).
            state: classifier state string for the corner indicator.
            lps_kpa: LPS28 baseline-zeroed pressure (signed kPa) or
                None when the LPS sensor is unavailable. The LPS bars
                show "----" while None.
        """
        if not self._available:
            return

        now = time.monotonic()
        if now < self._t_next_update:
            return
        self._t_next_update = now + self._update_period

        # Event-indicator boxes must update every tick so the blink
        # phase progresses even when the pressure values are stable —
        # otherwise the short-circuit below would freeze the boxes
        # during an idle interval.
        if not self._is_mono:
            self._update_event_boxes(now)

        # Skip the actual draw if nothing meaningful has changed.
        # Quantise pressures so ADC/LPS jitter doesn't trigger redraws.
        # MPX → 0.01 kPa; LPS → 0.001 kPa (its swings are an order of
        # magnitude smaller).
        lps_q = (round(lps_kpa * 1000) / 1000.0
                 if lps_kpa is not None else None)
        snap = (round(p_kpa * 100) / 100.0, lps_q, state)
        if snap == self._last_rendered:
            return
        self._last_rendered = snap

        try:
            if self._is_mono:
                self._render_mono(p_kpa, state, lps_kpa)
                return

            self._state_label.text = "state: {}".format(state)

            # MPX bars
            puff_mag = max(0.0, p_kpa)
            sip_mag  = max(0.0, -p_kpa)
            self._set_bar(self._puff_fill_rect, puff_mag,
                          self._full_scale)
            self._set_bar(self._sip_fill_rect,  sip_mag,
                          self._full_scale)
            self._puff_value_label.text = "{:.2f}".format(puff_mag)
            self._sip_value_label.text  = "{:.2f}".format(sip_mag)

            # LPS bars
            if lps_kpa is None:
                self._set_bar(self._lps_puff_fill_rect, 0.0,
                              self._lps_full_scale)
                self._set_bar(self._lps_sip_fill_rect,  0.0,
                              self._lps_full_scale)
                self._lps_puff_value_label.text = " --- "
                self._lps_sip_value_label.text  = " --- "
            else:
                lps_puff_mag = max(0.0, lps_kpa)
                lps_sip_mag  = max(0.0, -lps_kpa)
                self._set_bar(self._lps_puff_fill_rect, lps_puff_mag,
                              self._lps_full_scale)
                self._set_bar(self._lps_sip_fill_rect,  lps_sip_mag,
                              self._lps_full_scale)
                # Label precision matches the configured full scale —
                # 3 decimals for tight (≤0.5 kPa) ranges where every
                # millibar matters, 2 decimals once the bar spans kPa.
                fmt = "{:.3f}" if self._lps_full_scale < 0.5 else "{:.2f}"
                self._lps_puff_value_label.text = fmt.format(lps_puff_mag)
                self._lps_sip_value_label.text  = fmt.format(lps_sip_mag)
        except Exception as e:
            if self._verbose:
                print("Display: update error ({})".format(e))
            self._t_next_update = now + 1.0

    def _render_mono(self, p_kpa, state, lps_kpa=None):
        """Full-frame redraw on the SSD1306 via framebuf primitives.

        Cheap enough at 10 Hz: 1 KB framebuffer fill + a handful of
        rect/text calls + a single I2C transfer to push the buffer.

        Draws the same 4-bar layout as the color path: MPX P, MPX S,
        LPS P, LPS S — so behaviour is consistent across the LCD and
        OLED variants of the device.
        """
        d = self._display
        d.fill(0)

        # Title + state on the top line.
        d.text("SipNPuff", 0, self._mono_title_y, 1)
        d.text(state[:6], max(0, self._mono_w - 48),
               self._mono_title_y, 1)

        def _draw_row(y_top, label, magnitude_kpa, full_scale,
                      threshold_kpa, value_text):
            text_y = y_top + self._bar_h // 2 - 4
            d.text(label, 0, text_y, 1)
            d.rect(self._bar_x, y_top, self._bar_w, self._bar_h, 1)
            fill_w = self._bar_pixels(magnitude_kpa, full_scale)
            if fill_w > 0:
                d.fill_rect(self._bar_x + 1, y_top + 1,
                            fill_w, max(1, self._bar_h - 2), 1)
            # Threshold tick on MPX rows only (LPS rows pass 0).
            if threshold_kpa > 0:
                thr_x = self._bar_x + self._bar_pixels(
                    threshold_kpa, full_scale)
                d.fill_rect(thr_x, y_top - 1, 1,
                            self._bar_h + 2, 1)
            d.text(value_text, self._bar_x + self._bar_w + 2,
                   text_y, 1)

        # MPX rows
        puff_mag = max(0.0, p_kpa)
        sip_mag  = max(0.0, -p_kpa)
        _draw_row(self._mono_mpx_p_y, "MP",
                  puff_mag, self._full_scale,
                  self._puff_on, "{:.1f}".format(puff_mag))
        _draw_row(self._mono_mpx_s_y, "MS",
                  sip_mag, self._full_scale,
                  -self._sip_on, "{:.1f}".format(sip_mag))

        # LPS rows (skipped on a 128x32 panel — slot Ys are None).
        if self._mono_lps_p_y is not None:
            if lps_kpa is None:
                _draw_row(self._mono_lps_p_y, "LP",
                          0.0, self._lps_full_scale, 0.0, " --")
                _draw_row(self._mono_lps_s_y, "LS",
                          0.0, self._lps_full_scale, 0.0, " --")
            else:
                lps_p_mag = max(0.0, lps_kpa)
                lps_s_mag = max(0.0, -lps_kpa)
                _draw_row(self._mono_lps_p_y, "LP",
                          lps_p_mag, self._lps_full_scale, 0.0,
                          "{:.2f}".format(lps_p_mag))
                _draw_row(self._mono_lps_s_y, "LS",
                          lps_s_mag, self._lps_full_scale, 0.0,
                          "{:.2f}".format(lps_s_mag))

        d.show()

    # --- Helpers -------------------------------------------------

    def _bar_pixels(self, magnitude_kpa, full_scale=None):
        """Map a kPa magnitude to bar pixel width [1, _bar_w-2].

        ``full_scale`` lets the LPS bars use a tighter scale than the
        MPX bars; defaults to the MPX (classifier) full scale.
        """
        if full_scale is None:
            full_scale = self._full_scale
        if full_scale <= 0:
            return 1
        frac = magnitude_kpa / full_scale
        if frac < 0.0:
            frac = 0.0
        if frac > 1.0:
            frac = 1.0
        px = int(frac * (self._bar_w - 2))
        return max(1, px)

    def _set_bar(self, rect, magnitude_kpa, full_scale=None):
        # rect is a vectorio.Rectangle whose width property is mutable.
        rect.width = self._bar_pixels(magnitude_kpa, full_scale)


# ===================================================================
# Minimal SSD1306 I2C driver
# ===================================================================
#
# Why we don't use adafruit_ssd1306 / adafruit_displayio_ssd1306:
#
# On this hardware (Pico 2 / CircuitPython 10.2.0 / multi-device I2C
# bus), every layered driver wedges with [Errno 116] ETIMEDOUT when
# it tries to push the framebuffer. Diagnosed empirically:
#
#   * Single bulk writeto of 64+ contiguous data bytes hangs the
#     bus — the SSD1306 clock-stretches while writing GDDRAM and
#     CP's busio.I2C clock-stretch tolerance is shorter.
#   * 32-byte writes work cleanly.
#   * Sending the entire init sequence as one writeto (50 bytes of
#     control+command pairs) ALSO works, because each pair is a
#     latched command and the chip doesn't stretch between them.
#   * adafruit_ssd1306 sends init as 25 separate 2-byte writes,
#     which leaves the chip in a state where the next data write
#     hangs even at 32 bytes. Replicating the all-at-once init here
#     avoids that.
#
# So this class:
#   1. Sends the full init sequence in a single I2C transaction.
#   2. Inherits from framebuf.FrameBuffer so we get fill/text/rect/etc.
#   3. show() pushes the framebuffer in 32-byte chunks under one lock.
# ===================================================================

# SSD1306 init sequence — all bytes in one writeto. Each "0x80, cmd"
# pair is a Co=1 command, latched immediately. Tuned for 128x64.
_SSD1306_INIT_128x64 = bytes((
    0x80, 0xAE,             # display off
    0x80, 0x20, 0x80, 0x00, # set memory addressing mode = horizontal
    0x80, 0x40,             # set display start line = 0
    0x80, 0xA1,             # segment remap col 127 -> SEG0
    0x80, 0xA8, 0x80, 0x3F, # multiplex ratio = 64
    0x80, 0xC8,             # COM scan dir reversed
    0x80, 0xD3, 0x80, 0x00, # display offset = 0
    0x80, 0xDA, 0x80, 0x12, # COM pins config
    0x80, 0xD5, 0x80, 0x80, # display clock divide / oscillator freq
    0x80, 0xD9, 0x80, 0xF1, # pre-charge period
    0x80, 0xDB, 0x80, 0x40, # VCOMH deselect level
    0x80, 0x81, 0x80, 0xFF, # contrast = max
    0x80, 0xA4,             # output follows RAM (not all-on)
    0x80, 0xA6,             # normal (not inverted)
    0x80, 0x8D, 0x80, 0x14, # charge pump on
    0x80, 0x21, 0x80, 0x00, 0x80, 0x7F,  # column range 0..127
    0x80, 0x22, 0x80, 0x00, 0x80, 0x07,  # page range 0..7
    0x80, 0xAF,             # display on
))

# Same shape for 128x32 — only the multiplex ratio + COM pins differ.
_SSD1306_INIT_128x32 = bytes((
    0x80, 0xAE,
    0x80, 0x20, 0x80, 0x00,
    0x80, 0x40,
    0x80, 0xA1,
    0x80, 0xA8, 0x80, 0x1F,
    0x80, 0xC8,
    0x80, 0xD3, 0x80, 0x00,
    0x80, 0xDA, 0x80, 0x02,
    0x80, 0xD5, 0x80, 0x80,
    0x80, 0xD9, 0x80, 0xF1,
    0x80, 0xDB, 0x80, 0x40,
    0x80, 0x81, 0x80, 0xFF,
    0x80, 0xA4,
    0x80, 0xA6,
    0x80, 0x8D, 0x80, 0x14,
    0x80, 0x21, 0x80, 0x00, 0x80, 0x7F,
    0x80, 0x22, 0x80, 0x00, 0x80, 0x03,
    0x80, 0xAF,
))


# Each I2C data transaction carries a 0x40 control prefix + N data
# bytes. Empirical limit on this hardware is 32 total bytes per
# transaction.
_CHUNK_BYTES = 32


class _MiniSSD1306:
    """Tiny SSD1306-over-I2C driver for the Sip-N-Puff status display.

    Public surface mirrors the subset of adafruit_ssd1306 we use:
    fill, fill_rect, rect, text, show. Everything else delegates to
    the underlying framebuf.FrameBuffer.
    """

    def __init__(self, i2c, addr, width, height, framebuf_module):
        self._i2c = i2c
        self._addr = addr
        self.width = width
        self.height = height

        if (width, height) == (128, 64):
            init_blob = _SSD1306_INIT_128x64
        elif (width, height) == (128, 32):
            init_blob = _SSD1306_INIT_128x32
        else:
            raise ValueError("Unsupported SSD1306 geometry "
                             "{}x{}".format(width, height))

        # 1 framebuffer byte = 8 vertical pixels (MVLSB packing).
        # +1 leading byte holds the 0x40 data-mode prefix so the
        # first chunk of show() doesn't need a synthetic prefix.
        self._buffer = bytearray(((height // 8) * width) + 1)
        self._buffer[0] = 0x40
        self._fb = framebuf_module.FrameBuffer(
            memoryview(self._buffer)[1:], width, height,
            framebuf_module.MVLSB)

        # Send init + first frame under ONE persistent lock. On
        # this hardware (Pico 2 / CP 10.2.0) unlocking between init
        # and the first framebuffer push leaves the bus in a state
        # where the next 32-byte write hangs with ETIMEDOUT.
        # Keeping the lock held for the entire init-then-show
        # sequence sidesteps that. Subsequent show() calls re-lock
        # cleanly because the panel is fully initialised by then.
        while not i2c.try_lock():
            pass
        try:
            i2c.writeto(addr, init_blob)
            # Push an all-zero framebuffer immediately so the panel
            # leaves init with a known visible state instead of
            # whatever GDDRAM defaults to. Done with the lock still
            # held — see comment above.
            self._show_locked()
        finally:
            i2c.unlock()

    # --- framebuf passthroughs ---------------------------------

    def fill(self, color):
        self._fb.fill(color)

    def fill_rect(self, x, y, w, h, color):
        self._fb.fill_rect(x, y, w, h, color)

    def rect(self, x, y, w, h, color):
        self._fb.rect(x, y, w, h, color)

    def text(self, s, x, y, color):
        self._fb.text(s, x, y, color)

    # --- Push framebuffer to panel -----------------------------

    def show(self):
        """Send the whole framebuffer to the SSD1306 in 32-byte chunks."""
        i2c = self._i2c
        while not i2c.try_lock():
            pass
        try:
            self._show_locked()
        finally:
            i2c.unlock()

    def _show_locked(self):
        """Push the framebuffer assuming the I2C lock is already held."""
        buf = self._buffer
        chunk = _CHUNK_BYTES
        total = len(buf)
        i2c  = self._i2c
        addr = self._addr

        # First chunk includes the buffer's own 0x40 prefix at
        # index 0 — send up to 32 bytes from the buffer head.
        first_end = min(chunk, total)
        i2c.writeto(addr, bytes(buf[0:first_end]))
        pos = first_end
        # Subsequent chunks each carry their own synthetic 0x40
        # control byte. The SSD1306's GDDRAM column pointer
        # auto-increments across transactions in horizontal
        # addressing mode, so the picture stays continuous.
        while pos < total:
            end = min(pos + (chunk - 1), total)
            out = bytes([0x40]) + bytes(buf[pos:end])
            i2c.writeto(addr, out)
            pos = end
