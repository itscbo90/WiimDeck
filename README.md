# WiimDeck

A WiiM "now playing" display and touch remote for the Pimoroni Presto
(RP2350 / Raspberry Pi Pico, 4-inch 480×480 touchscreen, ambient LEDs).

Displays album art full-screen, scrolls long track titles automatically,
shows a clock when idle, and gives you one-tap playback control.

---

## File layout

```
WiimDeck/
  main.py                          ← entry point (calls launch())
  base.py                          ← BaseApp + Colors helper classes
  secrets.py                       ← WiFi credentials  (MUST keep this name)
  options.py                       ← all user settings  (edit this)
  wiim_client.py                   ← WiiM HTTP API wrapper (reference)
  simplebg.jpg                     ← example idle background image
  applications/
    wiim/
      wiim.py                      ← full application code
      icons/                       ← PNG transport button icons
        play.png
        pause.png
        next.png
        previous.png
```

---

## Requirements

- **Pimoroni Presto** running the official Pimoroni MicroPython firmware
- **`Roboto-Medium.af`** must be present in the root of the Pico flash.
  This font file ships with the Pimoroni firmware — if it is missing,
  re-flash the firmware from https://pimoroni.com/presto
- A **WiiM** streaming device on the same LAN

---

## Quick start

1. Flash the Pimoroni MicroPython firmware onto your Presto.
2. Copy **all files** to the root of the Pico flash using Thonny or mpremote.
3. Edit **`secrets.py`** with your WiFi credentials.
4. Edit **`options.py`** with your WiiM's LAN IP and your preferences.
5. Run `main.py` in Thonny, or add `import main` to `boot.py` for auto-start.
6. To restart after a settings change: unplug and replug the Presto.

---

## secrets.py  (do not rename)

The Presto firmware's `presto.connect()` reads WiFi credentials
**specifically from a file called `secrets.py`**. Renaming it will
prevent WiFi from connecting.

```python
WIFI_SSID     = "YourNetwork"
WIFI_PASSWORD = "YourPassword"
```

---

## options.py  (all settings)

Every user-facing setting is in `options.py` with comments and examples.
Key settings:

| Setting | Default | Description |
|---|---|---|
| `WIIM_IP` | `"10.70.30.40"` | LAN IP of your WiiM device |
| `CLOCK_12HR` | `True` | 12-hour (`True`) or 24-hour (`False`) clock |
| `SHOW_CLOCK_WHEN_IDLE` | `True` | Show clock when idle, or black screen |
| `CLOCK_IDLE_SECS` | `120` | Seconds of no playback before idle screen |
| `IDLE_BACKGROUND_COLOR` | `(0,0,0)` | Idle screen background RGB |
| `IDLE_BACKGROUND_IMAGE` | `""` | Optional 480×480 JPEG/PNG background |
| `IDLE_TEXT_COLOR` | `(255,255,255)` | Clock / idle text colour |
| `TRACK_INFO_COLOR` | `(255,255,255)` | Title / artist text colour |
| `TRACK_INFO_BAR_COLOR` | `(60,60,60)` | Colour of bar behind track info |
| `SCREEN_BRIGHTNESS` | `100` | Screen backlight brightness 10–100 % |
| `AMBIENT_LED_BRIGHTNESS` | `100` | Ambient LED brightness 10–100 % |
| `AMBIENT_LEDS` | `True` | Presto ambient LEDs on or off |
| `LEDS_OFF_WHEN_IDLE` | `False` | Turn LEDs off on idle clock screen |
| `CONTROL_MODE` | `"buttons"` | `"buttons"` or `"touch"` |
| `ALWAYS_SHOW_BUTTONS` | `False` | Keep transport buttons always visible |
| `ALWAYS_SHOW_TRACK_INFO` | `True` | Keep title/artist always visible |
| `AUTO_HIDE_SECS` | `20` | Seconds before buttons auto-hide |

Timezone is **detected automatically** via ip-api.com on first connect.
No manual timezone setting is needed.

---

## Control modes

### `CONTROL_MODE = "buttons"` (default)

Three PNG transport icons are shown on screen just above the track info bar.

```
[ ◀◀ Prev ]   [ ▶ Play/Pause ]   [ Next ▶▶ ]
```

- **Tap anywhere** on screen to show or hide the buttons.
- Buttons auto-hide after `AUTO_HIDE_SECS` seconds of no interaction.
- Set `ALWAYS_SHOW_BUTTONS = True` to keep them permanently visible.
- Shell output: `Button: Previous / Play / Next / Toggle Overlay`

### `CONTROL_MODE = "touch"`

The screen is divided into three invisible tap zones:

```
|── Left 160 px ──|── Centre 160 px ──|── Right 160 px ──|
      Previous           Play/Pause           Next
```

- Single tap per zone. No buttons are shown.
- Shell output: `Touch: Previous/Play/Pause/Next (x=NNN)` where NNN is
  the raw touch X coordinate — useful for confirming the touchscreen is
  registering correctly.

---

## Track info bar

A solid colour rectangle is painted directly on top of the album art,
behind the title and artist text. It starts just above the title text
and runs to the bottom of the screen.

Set the colour with `TRACK_INFO_BAR_COLOR = (R, G, B)` in `options.py`.
Use a dark colour so white text remains readable:

```
(0,   0,   0)   black
(60,  60,  60)  dark grey  (default)
(0,   0,  60)   dark navy
(40,  0,   0)   dark red
```

---

## Scrolling titles

If a track title is too wide to fit on screen it scrolls automatically:

- Pauses 2 seconds at the full start position
- Scrolls left at 8 px per 150 ms
- Pauses 2 seconds when fully scrolled, then restarts
- Scrolling pauses while transport buttons are visible (performance)
- Artist name is always truncated (shorter line, rarely overflows)

Scroll speed and pause duration can be tuned at the top of `wiim.py`:

```python
SCROLL_SPEED_MS = 150   # ms between scroll steps
SCROLL_PX       = 8     # pixels per step
SCROLL_PAUSE_S  = 2     # seconds to hold at start / end
```

---

## Idle / waiting screens

| State | Display |
|---|---|
| Playback active | Full-screen album art + track info bar + title/artist |
| No playback, < `CLOCK_IDLE_SECS` elapsed | "WiimDeck – Ready and connected" waiting screen |
| No playback, ≥ `CLOCK_IDLE_SECS` elapsed | Clock + date (or black screen if `SHOW_CLOCK_WHEN_IDLE = False`) |

The idle clock refreshes every 30 seconds so the time stays current.

---

## Screen brightness

`SCREEN_BRIGHTNESS` sets the LCD backlight level as a percentage (10–100).

```python
SCREEN_BRIGHTNESS = 100   # full brightness
SCREEN_BRIGHTNESS = 50    # half brightness — good for dark rooms
SCREEN_BRIGHTNESS = 10    # minimum (never goes fully off)
```

Applied once at startup via `presto.set_backlight()`.

---

## Ambient LEDs

```python
AMBIENT_LEDS = True           # LEDs on
AMBIENT_LEDS = False          # LEDs always off
LEDS_OFF_WHEN_IDLE = True     # LEDs off during idle clock, restore on play
LEDS_OFF_WHEN_IDLE = False    # LEDs stay on during idle (default)
```

`AMBIENT_LED_BRIGHTNESS` controls how bright the LEDs are (10–100 %):

| Value | Behaviour |
|---|---|
| `100` (default) | `auto_ambient_leds` mode — LEDs automatically colour-match the display content |
| `< 100` | Manual mode — all 7 LEDs set to neutral white at the specified brightness |

```python
AMBIENT_LED_BRIGHTNESS = 100   # full auto colour-match
AMBIENT_LED_BRIGHTNESS = 60    # 60 % brightness, neutral white
AMBIENT_LED_BRIGHTNESS = 20    # very dim, neutral white
```

`AMBIENT_LED_BRIGHTNESS` has no effect when `AMBIENT_LEDS = False`.

---

## WiiM API endpoints used

| Command | When called |
|---|---|
| `getPlayerStatus` | Every 10 seconds (separate async task) |
| `getMetaInfo` | Only when the track title changes |
| `setPlayerCmd:onepause` | Play / Pause toggle |
| `setPlayerCmd:next` | Skip forward |
| `setPlayerCmd:prev` | Skip back |

Album art is fetched via **wsrv.nl** (image proxy/resizer) and decoded
directly into the display framebuffer. Art is re-fetched only when the
track changes.

---

## Shell output reference

All messages printed to the Thonny shell / REPL:

| Message | Meaning |
|---|---|
| `Screen: Splash \| WiimDeck \| Connecting to WiFi...` | Startup splash screen |
| `Screen: Splash \| WiimDeck \| Detecting timezone...` | Timezone detection splash |
| `Screen: Splash \| WiimDeck \| Connected! Starting...` | Connection confirmed |
| `Screen: Waiting for playback` | Waiting screen shown (no music playing) |
| `Screen: Now playing \| Title - Artist` | Album art + track info drawn |
| `Screen: Idle clock` | Idle clock screen appeared |
| `Screen: Idle black screen` | Black idle screen (SHOW_CLOCK_WHEN_IDLE = False) |
| `Timezone: Europe/London UTC+1` | Timezone auto-detected successfully |
| `Timezone: UTC fallback` | ip-api.com unreachable — using UTC |
| `NTP failed: ...` | Time sync failed (clock may be wrong) |
| `Idle bg loaded: simplebg.jpg` | Background image loaded into RAM |
| `Button: Previous` | Transport button tapped (button mode) |
| `Button: Play` | Transport button tapped (button mode) |
| `Button: Next` | Transport button tapped (button mode) |
| `Button: Toggle Overlay` | Screen tapped to show/hide overlay |
| `Touch: Previous (x=42)` | Left zone tapped (touch mode) |
| `Touch: Play/Pause (x=230)` | Centre zone tapped (touch mode) |
| `Touch: Next (x=380)` | Right zone tapped (touch mode) |
| `WiiM error: ...` | Network error polling the WiiM device |
| `Art fetch error: ...` | Album art download failed |
| `Art decode error: ...` | Album art could not be decoded |

---

## Troubleshooting

**App crashes at startup with `OSError: [Errno 2] ENOENT`**
→ `Roboto-Medium.af` is missing from the root of the Pico flash.
  Re-flash the Pimoroni firmware or copy the font from another project.

**WiFi never connects**
→ Check `WIFI_SSID` / `WIFI_PASSWORD` in `secrets.py`.
  The file must be named exactly `secrets.py`.

**No album art / WiiM errors in shell**
→ Check `WIIM_IP` in `options.py` matches your WiiM's LAN IP.
  Confirm the WiiM and Presto are on the same network/VLAN.

**Touch not registering (touch mode)**
→ Check shell for `Touch: ...` messages. If absent, the touchscreen
  driver may not be initialising — try re-flashing the firmware.

**Buttons show but don't auto-hide**
→ Ensure `AUTO_HIDE_SECS` is > 0 and `ALWAYS_SHOW_BUTTONS = False`.

**Clock shows wrong time**
→ NTP sync may have failed. Check shell for `NTP failed:` message.
  The Presto must reach the internet (not just the local network).

**Screen is too bright / too dim**
→ Adjust `SCREEN_BRIGHTNESS` in `options.py` (10–100). Changes take
  effect on next restart.

**Ambient LEDs not dimming**
→ Set `AMBIENT_LED_BRIGHTNESS` below 100 in `options.py`. Note that
  at 100 the LEDs are in auto colour-match mode; below 100 they switch
  to manual neutral white at the specified level.

---

## Architecture notes

The app runs three concurrent async tasks:

| Task | Role |
|---|---|
| `_poll_loop` | Polls WiiM every 10 s. Blocking HTTPS call isolated here so it never stalls touch or display. |
| `_display_loop` | Redraws UI on state change, drives title scroll tick, refreshes idle clock, fires auto-hide timer. No network calls. |
| `_button_touch_loop` / `_gesture_touch_loop` | Polls touch hardware every 10 ms and dispatches commands. |

Display uses two hardware layers:
- **Layer 0** — album art + track info bar (repainted on track change only)
- **Layer 1** — button icons + title/artist text (repainted on every overlay change or scroll tick)
