import gc
import time
import utime
import jpegdec
import pngdec
import ntptime
import uasyncio as asyncio
import urequests as requests

from picovector import ANTIALIAS_FAST, PicoVector, Transform
from touch import Button

from base import BaseApp
import options

MONTHS = ('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')
DAYS   = ('Mon','Tue','Wed','Thu','Fri','Sat','Sun')

WIIM_IP                = options.WIIM_IP
TIMEOUT                = 8
CONTROL_MODE           = options.CONTROL_MODE
AMBIENT_LEDS           = options.AMBIENT_LEDS
LEDS_OFF_WHEN_IDLE     = options.LEDS_OFF_WHEN_IDLE
SHOW_CLOCK             = options.SHOW_CLOCK_WHEN_IDLE
CLOCK_12HR             = options.CLOCK_12HR
ALWAYS_SHOW_BUTTONS    = options.ALWAYS_SHOW_BUTTONS
ALWAYS_SHOW_TRACK_INFO = options.ALWAYS_SHOW_TRACK_INFO
AUTO_HIDE_SECS         = options.AUTO_HIDE_SECS
IDLE_BG_COLOR          = options.IDLE_BACKGROUND_COLOR
IDLE_BG_IMAGE          = options.IDLE_BACKGROUND_IMAGE
IDLE_TEXT_COLOR        = options.IDLE_TEXT_COLOR
TRACK_INFO_COLOR       = options.TRACK_INFO_COLOR
TRACK_INFO_BAR_COLOR   = options.TRACK_INFO_BAR_COLOR
SCREEN_BRIGHTNESS      = max(10, min(100, options.SCREEN_BRIGHTNESS))
AMBIENT_LED_BRIGHTNESS = max(10, min(100, options.AMBIENT_LED_BRIGHTNESS))

POLL_INTERVAL = 8
CLOCK_IDLE    = max(10, options.CLOCK_IDLE_SECS)
TIMEZONE_SEC  = 0
ZONE_W        = 160

# ---------------------------------------------------------------------------
# Layout  (all offsets are measured UP from the bottom of the 480px screen)
# ---------------------------------------------------------------------------
ARTIST_Y_OFFSET  = 22    # artist baseline at y=458
TITLE_GAP        = 26    # px between title and artist baselines
TITLE_Y_OFFSET   = ARTIST_Y_OFFSET + TITLE_GAP   # = 48, title at y=432

INFO_BAR_PAD_TOP = 18    # px of bar above the title cap-height

BTN_BAR_H = 90           # transport button height
BTN_W     = 80           # transport button width
BTN_GAP   = 6            # gap between bottom of buttons and top of info bar

# Scrolling title settings
SCROLL_SPEED_MS = 150    # ms between each scroll step
SCROLL_PX       = 8      # pixels moved per step
SCROLL_PAUSE_S  = 2      # seconds to pause at start and end of each cycle
TITLE_LEFT_MARGIN = 19   # normal left margin for title text (px)

WAIT_TITLE_Y = 70
WAIT_LINE1_Y = 155
WAIT_LINE2_Y = 193
WAIT_LINE3_Y = 231
WAIT_HINT_Y  = 268

GC_INTERVAL = 30


# ---------------------------------------------------------------------------
# WiiM HTTP helpers
# ---------------------------------------------------------------------------

def wiim_get(command, parse_json=True):
    url = "https://" + WIIM_IP + "/httpapi.asp?command=" + command
    resp = None
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            result = resp.json() if parse_json else resp.text
            resp.close()
            return result
        resp.close()
    except Exception as e:
        print("WiiM error: " + str(e))
        if resp:
            try:
                resp.close()
            except Exception:
                pass
    return None

def wiim_get_player_status():
    return wiim_get("getPlayerStatus")

def wiim_get_meta_info():
    data = wiim_get("getMetaInfo")
    if data and "metaData" in data:
        return data["metaData"]
    return None

def wiim_toggle_play_pause():
    wiim_get("setPlayerCmd:onepause", parse_json=False)

def wiim_next():
    wiim_get("setPlayerCmd:next", parse_json=False)

def wiim_prev():
    wiim_get("setPlayerCmd:prev", parse_json=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_timezone_offset():
    print("Timezone: auto-detecting...")
    try:
        resp = requests.get(
            "http://ip-api.com/json/?fields=timezone,offset,status", timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            resp.close()
            if data.get("status") == "success":
                offset_sec = data.get("offset", None)
                tz_name    = data.get("timezone", "unknown")
                if offset_sec is not None:
                    hrs  = int(offset_sec) // 3600
                    sign = "+" if offset_sec >= 0 else "-"
                    print("Timezone: " + tz_name + " UTC" + sign + str(abs(hrs)))
                    return int(offset_sec)
        else:
            resp.close()
    except Exception as e:
        print("Timezone failed: " + str(e))
    print("Timezone: UTC fallback")
    return 0

def sanitise(text, max_len=None):
    """Strip non-ASCII chars. If max_len given, truncate with ellipsis."""
    out = "".join(c if ord(c) < 128 else " " for c in text)
    if max_len is not None and len(out) > max_len:
        out = out[:max_len] + "..."
    return out

def pv_centred_x(vector, text, font_size, screen_width):
    vector.set_font_size(font_size)
    text_w = int(vector.measure_text(text)[2])
    return int(max(0, (screen_width - text_w) // 2))


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class State:
    def __init__(self):
        self.is_playing   = False
        self.title        = ""
        self.artist       = ""
        self.art_url      = ""
        self.overlay_on   = False
        self.disp_title    = ""    # full sanitised title (no truncation)
        self.disp_artist   = ""    # sanitised + truncated artist
        self.title_scrolls  = False  # True when title is wider than screen
        self.title_px_width = 0      # cached pixel width of disp_title

    def update_display_strings(self, display=None):
        # Artist: always truncated — short line, rarely overflows
        self.disp_artist = sanitise(self.artist, 36)
        # Title: sanitise without truncation so full text is available to scroll
        clean = sanitise(self.title)
        # Measure pixel width using the bitmap font at scale=1.1.
        # set_font must be called first so measure_text uses the correct
        # font metrics — otherwise it may use whatever font was active last.
        if display is not None:
            try:
                display.set_font("sans")
                px_w = display.measure_text(clean, scale=1.1)
            except Exception:
                px_w = len(clean) * 9   # ~9px per char at scale 1.1
        else:
            px_w = len(clean) * 9
        usable = 480 - TITLE_LEFT_MARGIN  # 461 px
        self.title_px_width = px_w
        if px_w > usable:
            self.title_scrolls = True
            self.disp_title    = clean          # full text for scrolling
        else:
            self.title_scrolls = False
            self.disp_title    = clean          # fits — display as-is

    def copy(self):
        s = State()
        s.is_playing    = self.is_playing
        s.title         = self.title
        s.artist        = self.artist
        s.art_url       = self.art_url
        s.overlay_on    = self.overlay_on
        s.disp_title     = self.disp_title
        s.disp_artist    = self.disp_artist
        s.title_scrolls  = self.title_scrolls
        s.title_px_width = self.title_px_width
        return s

    def __eq__(self, other):
        if not isinstance(other, State):
            return False
        return (self.is_playing == other.is_playing and
                self.title      == other.title      and
                self.artist     == other.artist     and
                self.art_url    == other.art_url    and
                self.overlay_on == other.overlay_on)


# ---------------------------------------------------------------------------
# ControlButton
# ---------------------------------------------------------------------------

class ControlButton:
    def __init__(self, display, name, icons, bounds, on_press=None, update=None):
        self.name     = name
        self.enabled  = False
        self.icon     = icons[0] if icons else None
        self.pngs     = {}
        if icons:
            for icon in icons:
                png = pngdec.PNG(display)
                png.open_file("applications/wiim/icons/" + icon)
                self.pngs[icon] = png
        self.button   = Button(*bounds)
        self.on_press = on_press
        self.update   = update

    def is_pressed(self, state):
        return self.enabled and self.button.is_pressed()

    def draw(self, state):
        if self.enabled and self.icon and self.icon in self.pngs:
            png = self.pngs[self.icon]
            x, y, w, h = self.button.bounds
            png_w, png_h = png.get_width(), png.get_height()
            png.decode(x + (w - png_w) // 2, y + (h - png_h) // 2)


# ---------------------------------------------------------------------------
# WiimDeck
# ---------------------------------------------------------------------------

class WiimDeck(BaseApp):

    ART_SIZE = 480

    def __init__(self):
        global TIMEZONE_SEC

        super().__init__(ambient_light=False, full_res=True, layers=2)
        # Set screen backlight brightness (0.0-1.0)
        self.presto.set_backlight(SCREEN_BRIGHTNESS / 100.0)
        self.toggle_leds(AMBIENT_LEDS)

        self.jpd    = jpegdec.JPEG(self.display)
        self.pnd    = pngdec.PNG(self.display)
        self.vector = PicoVector(self.display)
        self.vector.set_antialiasing(ANTIALIAS_FAST)
        self.vector.set_font("Roboto-Medium.af", 14)
        self.vector.set_font_letter_spacing(100)
        self.vector.set_font_word_spacing(100)
        self.vector.set_transform(Transform())

        # Pens
        r, g, b = IDLE_TEXT_COLOR
        self._idle_text_pen  = self.display.create_pen(r, g, b)
        r, g, b = TRACK_INFO_COLOR
        self._track_info_pen = self.display.create_pen(r, g, b)
        self._shadow_pen     = self.colors._BLACK
        r, g, b = TRACK_INFO_BAR_COLOR
        self._bar_pen        = self.display.create_pen(r, g, b)

        # Pre-compute bar and button Y positions from layout constants.
        # bar_top: top of the info bar on layer 0.
        # btn_y:   top of transport button icons, sitting just above the bar.
        self._bar_top = self.height - TITLE_Y_OFFSET - INFO_BAR_PAD_TOP
        self._btn_y   = self._bar_top - BTN_BAR_H - BTN_GAP

        # Load idle background image into RAM once (if configured)
        self._idle_bg_img = None
        if IDLE_BG_IMAGE:
            try:
                f = open(IDLE_BG_IMAGE, "rb")
                self._idle_bg_img = f.read()
                f.close()
                print("Idle bg loaded: " + IDLE_BG_IMAGE)
            except Exception as e:
                print("Idle bg load failed: " + str(e))

        # Splash + WiFi
        self._show_splash("WiimDeck", "Connecting to WiFi...")
        self.presto.connect()
        retries = 0
        while not self.presto.wifi.isconnected():
            retries += 1
            self._show_splash("WiimDeck", "WiFi retry " + str(retries) + "...")
            time.sleep(2)

        try:
            ntptime.settime()
        except Exception as e:
            print("NTP failed: " + str(e))

        self._show_splash("WiimDeck", "Detecting timezone...")
        TIMEZONE_SEC = get_timezone_offset()
        self._show_splash("WiimDeck", "Connected! Starting...")

        self.state             = State()
        self._idle_since       = None  # time.time() when playback last stopped
        self._clock_showing    = False
        self._leds_idle        = False
        self._overlay_shown_at = None
        self._init_poll        = False
        self._force_poll       = False
        self._polling          = False
        self._last_gc          = time.time()
        self._last_clock_refresh = 0

        # Scrolling title state
        self._scroll_x         = TITLE_LEFT_MARGIN  # current title x position
        self._scroll_pause_until = time.time() + SCROLL_PAUSE_S  # pause at start
        self._scroll_last_ms   = utime.ticks_ms()   # last scroll tick timestamp

        self.buttons = []
        if CONTROL_MODE == "buttons":
            self._setup_buttons()
            if ALWAYS_SHOW_BUTTONS or ALWAYS_SHOW_TRACK_INFO:
                self.state.overlay_on    = True
                # Start the auto-hide timer from boot so buttons hide
                # automatically even without a tap from the user.
                if not ALWAYS_SHOW_BUTTONS and AUTO_HIDE_SECS > 0:
                    self._overlay_shown_at = time.time()

        self.clear()
        self.presto.update()
        self._show_splash("WiimDeck", "Loading now playing...")
        self._init_poll = True
        self.poll_wiim()
        self._init_poll = False
        self.clear(1)
        if not self.state.title and not self._clock_showing:
            self.show_waiting()
        self._redraw()
        self.presto.update()

    # --- Splash -------------------------------------------------------------

    def toggle_leds(self, value):
        """Brightness-aware LED toggle.

        When AMBIENT_LED_BRIGHTNESS = 100 and LEDs are on, use
        auto_ambient_leds(True) so the LEDs colour-match the display.
        At any other brightness, drive all 7 LEDs manually at the
        requested brightness (white light) via set_led_hsv so the
        level is respected.
        """
        if value:
            if AMBIENT_LED_BRIGHTNESS >= 100:
                self.presto.auto_ambient_leds(True)
            else:
                self.presto.auto_ambient_leds(False)
                brightness = AMBIENT_LED_BRIGHTNESS / 100.0
                for i in range(7):
                    self.presto.set_led_hsv(i, 0.0, 0.0, brightness)
        else:
            self.presto.auto_ambient_leds(False)
            for i in range(7):
                self.presto.set_led_rgb(i, 0, 0, 0)

    def _show_splash(self, line1, line2=""):
        print("Screen: Splash | " + line1 + (" | " + line2 if line2 else ""))
        self.clear(1)
        self.display.set_layer(1)
        self.display.set_pen(self.colors.WHITE)
        x1 = pv_centred_x(self.vector, line1, 58, self.width)
        self.vector.set_font_size(58)
        self.vector.text(line1, x1, int(self.center_y - 15))
        if line2:
            self.display.set_pen(self.colors.GRAY)
            x2 = pv_centred_x(self.vector, line2, 26, self.width)
            self.vector.set_font_size(26)
            self.vector.text(line2, x2, int(self.center_y + 38))
            self.display.set_pen(self.colors.WHITE)
        self.presto.update()

    # --- Layer 0 backgrounds ------------------------------------------------

    def _draw_idle_background(self):
        self.display.set_layer(0)
        if self._idle_bg_img:
            try:
                mv = memoryview(self._idle_bg_img)
                if ".png" in IDLE_BG_IMAGE.lower():
                    self.pnd.open_RAM(mv)
                    self.pnd.decode(0, 0)
                else:
                    self.jpd.open_RAM(mv)
                    self.jpd.decode(0, 0, jpegdec.JPEG_SCALE_FULL, dither=False)
                return
            except Exception as e:
                print("Idle bg draw error: " + str(e))
        r, g, b = IDLE_BG_COLOR
        self.display.set_pen(self.display.create_pen(r, g, b))
        self.display.clear()

    def _draw_info_bar(self):
        """Paint the solid info bar on layer 0, from _bar_top to screen bottom."""
        self.display.set_layer(0)
        self.display.set_pen(self._bar_pen)
        self.display.rectangle(0, self._bar_top, self.width,
                               self.height - self._bar_top)

    # --- Button setup -------------------------------------------------------

    def _setup_buttons(self):
        W  = self.width
        H  = self.height
        CX = self.center_x
        # Buttons computed from bar position — always sit directly above it
        btn_y = self._btn_y

        def upd_transport(state, button):
            button.enabled = ALWAYS_SHOW_BUTTONS or state.overlay_on

        def upd_play(state, button):
            button.enabled = ALWAYS_SHOW_BUTTONS or state.overlay_on
            button.icon = "pause.png" if state.is_playing else "play.png"

        def upd_fullscreen(state, button):
            button.enabled = True

        def press_toggle_overlay(app):
            app.state.overlay_on = not app.state.overlay_on
            app._overlay_shown_at = time.time() if app.state.overlay_on else None

        def press_play_pause(app):
            wiim_toggle_play_pause()
            app.state.is_playing = not app.state.is_playing

        def press_next(app):
            wiim_next()
            app.state.title   = ""
            app.state.art_url = ""
            app._force_poll   = True

        def press_prev(app):
            wiim_prev()
            app.state.title   = ""
            app.state.art_url = ""
            app._force_poll   = True

        cfg = [
            ("Previous",       ["previous.png"],          (CX-130, btn_y, BTN_W, BTN_BAR_H), press_prev,           upd_transport),
            ("Play",           ["play.png", "pause.png"], (CX-40,  btn_y, BTN_W, BTN_BAR_H), press_play_pause,     upd_play),
            ("Next",           ["next.png"],              (CX+50,  btn_y, BTN_W, BTN_BAR_H), press_next,           upd_transport),
            ("Toggle Overlay", None,                      (0, 0, W, H),                       press_toggle_overlay, upd_fullscreen),
        ]
        self.buttons = [
            ControlButton(self.display, name, icons, bounds, pfn, ufn)
            for name, icons, bounds, pfn, ufn in cfg
        ]

    # --- Async tasks --------------------------------------------------------

    def run(self):
        loop = asyncio.get_event_loop()
        if CONTROL_MODE == "buttons":
            loop.create_task(self._button_touch_loop())
        else:
            loop.create_task(self._gesture_touch_loop())
        loop.create_task(self._poll_loop())
        loop.create_task(self._display_loop())
        loop.run_forever()

    async def _button_touch_loop(self):
        while True:
            self.touch.poll()
            if self.touch.state:
                for btn in self.buttons:
                    btn.update(self.state, btn)
                for btn in self.buttons:
                    if btn.is_pressed(self.state):
                        print("Button: " + btn.name)
                        try:
                            btn.on_press(self)
                        except Exception as e:
                            print("Button error: " + str(e))
                        break
                while self.touch.state:
                    self.touch.poll()
                    await asyncio.sleep_ms(5)
            await asyncio.sleep_ms(10)

    async def _gesture_touch_loop(self):
        while True:
            self.touch.poll()
            if self.touch.state:
                tap_x = self.touch.x
                while self.touch.state:
                    self.touch.poll()
                    await asyncio.sleep_ms(5)
                if tap_x < ZONE_W:
                    print("Touch: Previous (x={})".format(tap_x))
                    wiim_prev()
                    self.state.title   = ""
                    self.state.art_url = ""
                    self._force_poll   = True
                elif tap_x < ZONE_W * 2:
                    print("Touch: Play/Pause (x={})".format(tap_x))
                    wiim_toggle_play_pause()
                    self.state.is_playing = not self.state.is_playing
                else:
                    print("Touch: Next (x={})".format(tap_x))
                    wiim_next()
                    self.state.title   = ""
                    self.state.art_url = ""
                    self._force_poll   = True
            await asyncio.sleep_ms(10)

    async def _poll_loop(self):
        """WiiM polling in its own task. Wait split into 100 ms slices so
        _force_poll can interrupt it immediately on track skip."""
        while True:
            for _ in range(POLL_INTERVAL * 10):
                if self._force_poll:
                    break
                await asyncio.sleep_ms(100)
            self._force_poll = False
            self._polling = True
            await asyncio.sleep_ms(20)
            self.poll_wiim()
            self._polling = False

    def _reset_scroll(self):
        """Call whenever the track changes to restart the scroll cycle."""
        self._scroll_x           = TITLE_LEFT_MARGIN
        self._scroll_pause_until = time.time() + SCROLL_PAUSE_S
        self._scroll_last_ms     = utime.ticks_ms()

    async def _display_loop(self):
        """UI redraws, auto-hide, and title scroll — no network calls."""
        prev_state = None
        while True:
            now    = time.time()
            now_ms = utime.ticks_ms()

            # ---- Auto-hide transport buttons --------------------------------
            if (CONTROL_MODE == "buttons" and AUTO_HIDE_SECS > 0 and
                    self._overlay_shown_at is not None and
                    now - self._overlay_shown_at >= AUTO_HIDE_SECS):
                self.state.overlay_on  = False
                self._overlay_shown_at = None

            # ---- Full state-change redraw -----------------------------------
            state_changed = prev_state != self.state
            if state_changed:
                # Only reset scroll when the title itself changes.
                # Overlay toggles (show/hide buttons, auto-hide) must NOT
                # reset the scroll position or the title jumps back mid-scroll.
                if prev_state is None or prev_state.title != self.state.title:
                    self._reset_scroll()
                self._redraw()
                prev_state = self.state.copy()

            # ---- Scroll tick -----------------------------------------------
            # Only scroll when:
            #   • title is long enough to need it
            #   • we are currently showing track info
            #   • buttons are NOT visible (avoid costly PNG decodes every tick)
            #   • not mid-pause (start / end hold)
            elif (self.state.title_scrolls and
                    self.state.disp_title and
                    not (CONTROL_MODE == "buttons" and
                         (ALWAYS_SHOW_BUTTONS or self.state.overlay_on)) and
                    now >= self._scroll_pause_until and
                    utime.ticks_diff(now_ms, self._scroll_last_ms) >= SCROLL_SPEED_MS and
                    not self._polling):

                self._scroll_last_ms = now_ms
                self._scroll_x      -= SCROLL_PX

                # Use the cached pixel width from update_display_strings.
                # Scroll until the full title + one screen-width of extra
                # travel has passed, so the text is guaranteed to be gone
                # before the position resets.
                title_px = self.state.title_px_width or len(self.state.disp_title) * 9

                # Reset when the entire title has scrolled past the left
                # edge of the screen (right edge of text < x=0) with a small
                # 20 px safety margin. Do NOT add self.width here — that causes
                # nearly 10 seconds of scrolling empty space before reset.
                if self._scroll_x + title_px < -20:
                    self._scroll_x           = TITLE_LEFT_MARGIN
                    self._scroll_pause_until = now + SCROLL_PAUSE_S

                # Redraw layer 1 only — layer 0 (art + bar) unchanged
                self._draw_layer1()
                self.presto.update()

            # ---- Clock refresh
            if self._clock_showing and now - self._last_clock_refresh >= 30:
                self._last_clock_refresh = now
                self.show_clock(update_display=False)
                self._draw_layer1()
                self.presto.update()

            # ---- Periodic GC -----------------------------------------------
            if now - self._last_gc >= GC_INTERVAL:
                gc.collect()
                self._last_gc = now

            await asyncio.sleep_ms(100)

    # --- Rendering ----------------------------------------------------------
    #
    # Layer 0: background — album art + info bar, or clock, or waiting screen.
    #          Written once per track change; repainted by _redraw as needed.
    # Layer 1: foreground — button icons + track info text only.
    #          Cleared and rebuilt on every state change. Pen (0,0,0) on
    #          layer 1 is the colour-key transparent value.
    # -----------------------------------------------------------------------

    def _redraw(self):
        """Repaint whichever layer 0 content is current, then rebuild layer 1."""
        if self._clock_showing:
            self.show_clock(update_display=False)
        elif self.state.title:
            self._draw_info_bar()
        self._draw_layer1()
        self.presto.update()

    def _draw_layer1(self):
        """Clear layer 1 and redraw buttons + text."""
        self.clear(1)
        self.display.set_layer(1)
        if CONTROL_MODE == "buttons":
            show_buttons = ALWAYS_SHOW_BUTTONS or self.state.overlay_on
            show_info    = ALWAYS_SHOW_TRACK_INFO or self.state.overlay_on
            if show_buttons:
                for btn in self.buttons:
                    btn.update(self.state, btn)
                    btn.draw(self.state)
            if show_info:
                self._draw_track_info()
        else:
            if ALWAYS_SHOW_TRACK_INFO:
                self._draw_track_info()

    # --- WiiM poll ----------------------------------------------------------

    def poll_wiim(self):
        ps = wiim_get_player_status()
        if ps is None:
            # Network error - treat as still playing to avoid false idle
            return
        status = ps.get("status", "stop")
        if status == "play" or status == "loading":
            self.state.is_playing = (status == "play")
            if self._clock_showing:
                self._clock_showing = False
                self.state.art_url  = ""
                self.state.title    = ""
                if self._leds_idle and AMBIENT_LEDS:
                    self.toggle_leds(True)
                    self._leds_idle = False
            self._idle_since = None   # reset idle timer
            api_title = ps.get("Title", "")
            if api_title != self.state.title:
                self.state.title = api_title
                meta = wiim_get_meta_info()
                if meta:
                    raw_artist = meta.get("artist", "")
                    if raw_artist == "unknow" or raw_artist == "":
                        raw_artist = meta.get("subtitle", "")
                    self.state.artist = raw_artist
                    plain_title = meta.get("title", "")
                    self.state.title = plain_title if plain_title else api_title
                    self.state.update_display_strings(self.display)
                    # scroll reset handled in _display_loop on title change
                    new_url = meta.get("albumArtURI", "")
                    if new_url and new_url != self.state.art_url:
                        self.state.art_url = new_url
                        self.show_album_art(new_url)
        else:
            self.state.is_playing = False
            # Start idle timer the first time we see non-playing status
            if self._idle_since is None:
                self._idle_since = time.time()
            idle_secs = time.time() - self._idle_since
            if idle_secs >= CLOCK_IDLE:
                self._idle_since = None   # reset so it only triggers once
                self.state.title  = ""
                self.state.artist = ""
                self.state.update_display_strings(self.display)
                if SHOW_CLOCK:
                    self.show_clock()
                else:
                    print("Screen: Idle black screen")
                    self.clear()
                    self.presto.update()
                    self._clock_showing = True
                if LEDS_OFF_WHEN_IDLE and AMBIENT_LEDS and not self._leds_idle:
                    self.toggle_leds(False)
                    self._leds_idle = True
            elif (idle_secs >= 5 and not self.state.title
                  and not self._clock_showing and not self._init_poll):
                self.show_waiting()

    # --- Album art ----------------------------------------------------------

    def show_album_art(self, art_url):
        if not art_url:
            return
        self.display.set_layer(0)
        self.display.set_pen(self.colors.BLACK)
        self.display.clear()
        self._draw_layer1()
        self.presto.update()

        if "size=0" in art_url:
            url = art_url[:-1] + str(self.ART_SIZE) + "X" + str(self.ART_SIZE)
        else:
            url = ("https://wsrv.nl/?url=" + art_url
                   + "&w=" + str(self.ART_SIZE)
                   + "&h=" + str(self.ART_SIZE))

        img = None
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                img = resp.content
            else:
                print("Art HTTP " + str(resp.status_code))
            resp.close()
        except Exception as e:
            print("Art fetch error: " + str(e))
            return

        if not img:
            return

        self.display.set_layer(0)
        self.display.set_pen(self.colors.BLACK)
        self.display.clear()
        try:
            mv = memoryview(img)
            if ".png" in url:
                self.pnd.open_RAM(mv)
                self.pnd.decode(0, 0)
            else:
                self.jpd.open_RAM(mv)
                self.jpd.decode(0, 0, jpegdec.JPEG_SCALE_FULL, dither=True)
        except Exception as e:
            print("Art decode error: " + str(e))
        del img
        gc.collect()

        # Info bar painted on layer 0 directly over the decoded art pixels
        self._draw_info_bar()

        self._clock_showing = False
        print("Screen: Now playing | " + self.state.title + " - " + self.state.artist)
        self._draw_layer1()
        self.presto.update()

    # --- Clock screen -------------------------------------------------------

    def show_clock(self, update_display=True):
        tm       = utime.localtime(int(utime.time()) + TIMEZONE_SEC)
        hour     = tm[3]
        minute   = tm[4]
        date_str = "{} {:02d} {} {:d}".format(
            DAYS[tm[6]], tm[2], MONTHS[tm[1] - 1], tm[0])

        self._draw_idle_background()
        self.display.set_layer(0)
        self.display.set_pen(self._idle_text_pen)

        if CLOCK_12HR:
            ampm     = "AM" if hour < 12 else "PM"
            hour12   = hour % 12 or 12
            time_str = "{:d}:{:02d}".format(hour12, minute)
            TIME_SIZE = 155
            AMPM_SIZE = 48
            self.vector.set_font_size(TIME_SIZE)
            time_w  = int(self.vector.measure_text(time_str)[2])
            self.vector.set_font_size(AMPM_SIZE)
            ampm_w  = int(self.vector.measure_text(ampm)[2])
            gap     = 10
            block_x = int(max(0, (self.width - time_w - gap - ampm_w) // 2))
            self.vector.set_font_size(TIME_SIZE)
            self.vector.text(time_str, block_x, 220)
            self.vector.set_font_size(AMPM_SIZE)
            self.vector.text(ampm, block_x + time_w + gap, 220)
            DATE_SIZE = 46
            dx = pv_centred_x(self.vector, date_str, DATE_SIZE, self.width)
            self.vector.set_font_size(DATE_SIZE)
            self.vector.text(date_str, dx, 268)
        else:
            TIME_SIZE = 165
            time_str  = "{:02d}:{:02d}".format(hour, minute)
            tx = pv_centred_x(self.vector, time_str, TIME_SIZE, self.width)
            self.vector.set_font_size(TIME_SIZE)
            self.vector.text(time_str, tx, 240)
            DATE_SIZE = 46
            dx = pv_centred_x(self.vector, date_str, DATE_SIZE, self.width)
            self.vector.set_font_size(DATE_SIZE)
            self.vector.text(date_str, dx, 290)

        if update_display:
            print("Screen: Idle clock")
            self.presto.update()
            self._clock_showing = True

    # --- Waiting screen -----------------------------------------------------

    def show_waiting(self):
        print("Screen: Waiting for playback")
        self._draw_idle_background()
        self.display.set_layer(0)
        self.display.set_pen(self._idle_text_pen)

        tx = pv_centred_x(self.vector, "WiimDeck", 65, self.width)
        self.vector.set_font_size(65)
        self.vector.text("WiimDeck", tx, WAIT_TITLE_Y)

        for text, fsize, y in [
            ("Ready and connected.", 28, WAIT_LINE1_Y),
            ("Start playing music on", 28, WAIT_LINE2_Y),
            ("your WiiM to begin.", 28, WAIT_LINE3_Y),
        ]:
            lx = pv_centred_x(self.vector, text, fsize, self.width)
            self.vector.set_font_size(fsize)
            self.vector.text(text, lx, y)

        self.display.set_pen(self.colors.GRAY)
        hint = ("Left=Prev  Centre=Play  Right=Next"
                if CONTROL_MODE == "touch" else "Tap screen to show controls")
        hx = pv_centred_x(self.vector, hint, 22, self.width)
        self.vector.set_font_size(22)
        self.vector.text(hint, hx, WAIT_HINT_Y)
        self.presto.update()

    # --- Track info text  (layer 1) -----------------------------------------

    def _draw_track_info(self):
        if not self.state.disp_title:
            return
        self.display.set_layer(1)
        self.display.set_font("sans")

        title  = self.state.disp_title
        artist = self.state.disp_artist

        ty = int(self.height - TITLE_Y_OFFSET)
        ay = int(self.height - ARTIST_Y_OFFSET)

        # Title x: use scroll offset when scrolling, fixed margin otherwise.
        # Pixels drawn off the left edge (x < 0) or right edge (x > width)
        # are silently ignored by PicoGraphics — no clipping code needed.
        tx = self._scroll_x if self.state.title_scrolls else TITLE_LEFT_MARGIN

        # Title — shadow then colour
        self.display.set_thickness(3)
        self.display.set_pen(self._shadow_pen)
        self.display.text(title, tx + 2, ty + 2, scale=1.1)
        self.display.set_pen(self._track_info_pen)
        self.display.text(title, tx,     ty,     scale=1.1)

        # Artist — always fixed position, shadow then colour
        self.display.set_thickness(2)
        self.display.set_pen(self._shadow_pen)
        self.display.text(artist, 21, ay + 2, scale=0.75)
        self.display.set_pen(self._track_info_pen)
        self.display.text(artist, 19, ay,     scale=0.75)


def launch():
    app = WiimDeck()
    app.run()
    app.clear()
    del app
    gc.collect()
