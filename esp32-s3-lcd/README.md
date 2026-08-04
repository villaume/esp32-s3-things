
# Tibber elpris display (ESP32-S3 + GC9A01 240x240 round)

Shows the current electricity price and the cheapest upcoming window.

```
     ELPRIS          <- blue header
       52            <- current price, colour-coded
     ore/kWh
   ####------        <- price bar
   BILLIGAST
     23-00           <- cheapest window, colour-coded
    48o +12h         <- its average price, and how far off
```

When the cheapest window *is* the current hour it reads `BILLIGAST NU` / `48 ore NU`.

## Uploading

**Use `tools/push.py`, not `mpremote fs cp`.** See "Gotchas" below.

```sh
# find the port (the board shows up as 1a86:55d3, a CH343 bridge)
uvx mpremote connect list

export MPY_PORT=/dev/cu.usbmodemXXXX     # optional; a default is baked in
uv run tools/push.py main.py
uv run tools/push.py vga1_16x16.py       # only needed once

# watch it run
uvx mpremote connect $MPY_PORT repl      # Ctrl-] to exit
```

Do **not** copy `config.py` to the device. The checked-in copy has placeholder
values; the device holds the real WiFi and Tibber credentials and is the only
copy of them.

## Config

`BEST_WINDOW_HOURS` sets the length of the "cheapest window" (1 = the single
cheapest hour). `PRICE_GREEN_MAX` / `PRICE_YELLOW_MAX` set the colour
thresholds in öre/kWh, `PRICE_BAR_MAX` is the öre value that fills the bar.

Every one of these has a fallback in `main.py`, so an older `config.py` on the
device keeps working without being touched.

The board has no RTC sync — Tibber's own `current.startsAt` is used as the
clock, so no NTP setup is needed.

## Fonts

Only `vga1_16x32.py` ships with the board. `vga1_16x16.py` is generated from
it by `tools/make_small_font.py` (the big font is a 16x16 face doubled
vertically, so dropping every other row recovers it losslessly).

## Gotchas

Things that cost real time here, worth knowing before touching this again:

- **`mpremote connect auto` grabs `/dev/cu.Bluetooth-Incoming-Port`** and
  floods `\xff`. Always name the port explicitly.
- **`mpremote fs cp` is unreliable on this firmware** (MicroPython
  1.22.0-preview, 2023-12-02). It silently truncated an 11 KB file to exactly
  4352 bytes, and later reported success while not writing at all. Its
  raw-paste flow control does not agree with this build. `tools/push.py` uses
  the plain raw REPL in small chunks and verifies with SHA-256.
- **MicroPython f-strings cannot contain quotes inside `{}`.**
  `f"{d['k']}"` is a *SyntaxError at import time*, even though CPython accepts
  it. Use `%` formatting for anything indexing a dict.
- **The GC9A01 driver's `text()` needs a real module** as its font argument —
  it calls `mp_obj_module_get_globals()` on it. Passing a class or any
  synthesised object crashes the board with `LoadProhibited`. That is why the
  small font is a file on the device and not built at runtime.
- **The panel is round**, so usable width shrinks near the top and bottom. A
  16-wide 6-character title does not fit above y≈10. `fit_chars()` in
  `main.py` computes the chord width, and `center_best()` picks the longest
  label that actually fits.
- **If the board seems dead** — dark screen, no REPL, `\xff` on the wire — it
  is probably stuck in download mode from a BOOT+RESET. Unplug it and plug it
  back in *without* touching BOOT.

# Todo:

Add power used
Improve the UI
