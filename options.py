# =============================================================================
# WiimDeck  -  options.py
# All user-configurable settings live here.
# WiFi credentials stay in secrets.py (required by Presto firmware).
# Note: Make sure you have Roboto-Medium.af in the root of your Pico or the app will fail to launch.
# =============================================================================

# WiiM device LAN IP address
WIIM_IP = "Your WIIM IP or Hostname"

# Timezone is detected automatically via ip-api.com after WiFi connects.
# Falls back to UTC if detection fails. No manual setting needed.

# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------
# Clock style: True = 12-hour with AM/PM,  False = 24-hour
# Default Value: CLOCK_12HR = True
CLOCK_12HR = True

# Idle screen: True = show clock + date when idle,  False = black screen
# Default Value: SHOW_CLOCK_WHEN_IDLE = True
SHOW_CLOCK_WHEN_IDLE = True

# How many seconds of no playback before the idle screen appears (minimum 10)
# Default Value: CLOCK_IDLE_SECS = 120
CLOCK_IDLE_SECS = 120

# ---------------------------------------------------------------------------
# Idle screen background
# ---------------------------------------------------------------------------
# Solid background color (R, G, B) used when IDLE_BACKGROUND_IMAGE is "".
#   (0,   0,   0)   black (default)
#   (25,  25, 112)  midnight blue
#   (20,  20,  20)  very dark 
# Default Value: IDLE_BACKGROUND_COLOR = (0, 0, 0)
IDLE_BACKGROUND_COLOR = (0, 0, 0)

# Background image shown on the idle / waiting screen.
# Must be a JPEG or PNG at 480x480 px stored on the Presto flash.
# Overrides IDLE_BACKGROUND_COLOR when set.
# Leave as "" to use the solid colour above instead.
# Example:  IDLE_BACKGROUND_IMAGE = "simplebg.jpg"
# Place in the root of the Pico
# Default Value: IDLE_BACKGROUND_IMAGE = ""
IDLE_BACKGROUND_IMAGE = ""

# ---------------------------------------------------------------------------
# Text colours  (R, G, B)  –  each channel 0-255
# ---------------------------------------------------------------------------
# Colour for the clock time, date, and all idle / waiting screen text.
#   (255, 255, 255)  white (default)
#   (100, 200, 255)  light blue
#   (255, 200,  50)  warm gold
# Default Value: IDLE_TEXT_COLOR = (255, 255, 255)
IDLE_TEXT_COLOR = (255, 255, 255)

# Colour for the track title and artist name shown over album art.
#   (255, 250, 240)  warm white (default)
#   (255, 255, 255)  pure white
#   (255, 220, 100)  warm yellow
#   (150, 220, 255)  soft blue
# Default Value: TRACK_INFO_COLOR = (255, 255, 255)
TRACK_INFO_COLOR = (255, 255, 255)

# ---------------------------------------------------------------------------
# Track info bar
# ---------------------------------------------------------------------------
# A solid colour band painted directly on top of the album art, behind the
# title and artist text.  The bar starts just above the title text and runs
# all the way to the bottom of the screen.
#
# Because the bar is painted on the same layer as the album art, it is a
# true solid rectangle – there is no transparency or blending.  Choose a
# dark colour so the white text is readable against it.
#
#   (0,   0,   0)   black (default)
#   (20,  20,  20)  very dark grey
#   (0,   0,  60)   dark navy
#   (40,  0,   0)   dark red / burgundy
#   (0,  30,   0)   dark green
# Default Value: TRACK_INFO_BAR_COLOR = (60,  60,  60)
TRACK_INFO_BAR_COLOR = (60,  60,  60)

# ---------------------------------------------------------------------------
# Screen and LED brightness
# ---------------------------------------------------------------------------
# Screen backlight brightness as a percentage.  10 = very dim.  100 = full.
# Reducing this saves power and is easier on the eyes in a dark room.
# Default Value: SCREEN_BRIGHTNESS = 100
SCREEN_BRIGHTNESS = 70

# Ambient LED brightness as a percentage.  10 = very dim.  100 = full auto.
# At 100 the LEDs use auto_ambient_leds mode (colour-matches the display).
# At any value below 100 the LEDs are driven manually at that brightness
# as neutral white, giving smooth dimming control.
# Has no effect when AMBIENT_LEDS = False.
# Default Value: AMBIENT_LED_BRIGHTNESS = 100
AMBIENT_LED_BRIGHTNESS = 100

# ---------------------------------------------------------------------------
# Ambient LEDs
# ---------------------------------------------------------------------------
# True  = Presto ambient LEDs on (auto-brightness from artwork colours)
# False = LEDs always off
# Default Value: AMBIENT_LEDS = True
AMBIENT_LEDS = True

# Turn the ambient LEDs off when the idle clock screen appears and restore them automatically when playback resumes.
# Has no effect when AMBIENT_LEDS = False (LEDs stay off regardless).
# Default Value: LEDS_OFF_WHEN_IDLE = False
LEDS_OFF_WHEN_IDLE = False

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
# How playback is controlled by touching the screen:
#
#   "touch"   – Screen divided into three zones (no visible buttons):
#                 Left 160 px  = Previous track
#                 Centre 160 px = Play / Pause
#                 Right 160 px  = Next track
#
#   "buttons" – Three PNG icons shown on screen.
#               Tap anywhere to show / hide them (or see ALWAYS_SHOW_BUTTONS).
# Default Value: CONTROL_MODE = "touch"
CONTROL_MODE = "touch"

# Button mode only – True = transport buttons always visible on screen.
# False = buttons appear on tap and auto-hide after AUTO_HIDE_SECS seconds.
# Default Value: ALWAYS_SHOW_BUTTONS = False
ALWAYS_SHOW_BUTTONS = False

# True  = track title and artist always visible over album art.
# False = title / artist appear on tap alongside the buttons.
# Default Value: ALWAYS_SHOW_TRACK_INFO = True
ALWAYS_SHOW_TRACK_INFO = True

# Seconds of no interaction before the transport buttons auto-hide.
# Applies in button mode only.  Set to 0 to disable auto-hide.
# Default Value: AUTO_HIDE_SECS = 20
AUTO_HIDE_SECS = 20

# ---------------------------------------------------------------------------
# NOTE: To restart the application unplug and replug the Presto.
# ---------------------------------------------------------------------------

