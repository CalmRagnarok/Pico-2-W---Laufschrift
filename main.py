# main.py — schlanker App-Launcher (ohne Overlays/Hilfetext)
# Pico 2 W + Pimoroni Pico Scroll Pack (pimoroni MicroPython)

import time
import picoscroll as scroll
from app_weather import AppWeather
from app_tetris import AppTetris
from app_quotes import AppQuotes

# ---------------------------
# >>> Standort-Einstellungen <<<
# Wenn du feste Koordinaten möchtest, hier ändern:
MY_LAT = 56.1304   # Zürich
MY_LON = 106.3468
MY_CITY = "Canada"
# Wenn du None setzt, nutzt AppWeather die IP-Ortung
# MY_LAT, MY_LON, MY_CITY = None, None, "Ort"
# ---------------------------

sc = scroll.PicoScroll()
WIDTH, HEIGHT = scroll.WIDTH, scroll.HEIGHT
BRIGHT = 70

def commit():
    try:
        sc.show(); return
    except Exception:
        pass
    try:
        sc.update(); return
    except TypeError:
        try:
            sc.update(False); return
        except Exception:
            pass

def clear():
    sc.clear(); commit()

# ---------- Buttons ----------
BTN_NAMES = ["A","B","X","Y"]
BTN_CONST = [scroll.BUTTON_A, scroll.BUTTON_B, scroll.BUTTON_X, scroll.BUTTON_Y]

def _detect_button_mode():
    try:
        _ = sc.is_pressed(BTN_CONST[0]); return 1
    except TypeError:
        pass
    except Exception:
        pass
    try:
        st = sc.is_pressed(); _ = st[0]; _ = st[1]; _ = st[2]; _ = st[3]; return 2
    except Exception:
        return 0

BUTTON_MODE = _detect_button_mode()

def read_buttons():
    if BUTTON_MODE == 1:
        return {n: bool(sc.is_pressed(c)) for n,c in zip(BTN_NAMES, BTN_CONST)}
    elif BUTTON_MODE == 2:
        st = sc.is_pressed()
        return dict(zip(BTN_NAMES, [bool(st[i]) for i in range(4)]))
    else:
        return {n: False for n in BTN_NAMES}

# ---------- X-Doppelklick ----------
DOUBLE_MS = 350
_last_x_ms = None
_pending_x_single = False

def process_double_click_x(st, prev):
    global _last_x_ms, _pending_x_single
    ev = {"x_single": False, "x_double": False}
    if st["X"] and not prev["X"]:
        now = time.ticks_ms()
        if _last_x_ms is not None and time.ticks_diff(now, _last_x_ms) <= DOUBLE_MS:
            _pending_x_single = False
            _last_x_ms = None
            ev["x_double"] = True
        else:
            _last_x_ms = now
            _pending_x_single = True
    if _pending_x_single and _last_x_ms is not None:
        if time.ticks_diff(time.ticks_ms(), _last_x_ms) > DOUBLE_MS:
            _pending_x_single = False
            _last_x_ms = None
            ev["x_single"] = True
    return ev

# ---------- App-Basis ----------
class AppBase:
    name = "App"
    def init(self): pass
    def update(self, dt_ms, buttons, events): pass

# ---------- Deine Apps ----------
APPS = [
    AppWeather(MY_LAT, MY_LON, MY_CITY),
    AppTetris(),
    AppQuotes("sprueche.txt"),
]

# ---------- Launcher-Loop ----------
def main():
    idx = 0
    app = APPS[idx]
    app.init()

    prev = read_buttons()
    last_tick = time.ticks_ms()

    clear()  # kein Hilfetext/Overlay

    while True:
        now = time.ticks_ms()
        dt = time.ticks_diff(now, last_tick); last_tick = now

        st = read_buttons()
        ev = process_double_click_x(st, prev)

        # App-Wechsel bei X-Doppelklick
        if ev["x_double"]:
            idx = (idx + 1) % len(APPS)
            app = APPS[idx]
            app.init()

        # App updaten
        app.update(dt, st, ev)

        prev = st
        time.sleep_ms(20)

# --- Start ---
try:
    main()
except KeyboardInterrupt:
    clear()

