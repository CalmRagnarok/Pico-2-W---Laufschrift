# app_weather.py — Wetter-App mit A-Toggle (Start/Stopp der Wochenanzeige)
import time, json
import network
import picoscroll as scroll

# ---- WLAN aus secrets.py (empfohlen) ----
try:
    import secrets
    WIFI_SSID = secrets.WIFI_SSID
    WIFI_PASS = secrets.WIFI_PASS
except Exception:
    WIFI_SSID = "IOT"
    WIFI_PASS = "1oT4-VBdT-21"

BRIGHT = 70
REFRESH_S = 30*60  # alle 30 Min neu laden

sc = scroll.PicoScroll()
WIDTH, HEIGHT = scroll.WIDTH, scroll.HEIGHT

def _commit():
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
    sc.clear()
    _commit()

def setpx(x,y,v):
    sc.set_pixel(x,y,v)

# ---- 7x7 Icons ----
ICON = {
    "sun":   ["0011100","0100100","1011101","0111110","1011101","0100100","0011100"],
    "cloud": ["0000000","0011100","0111110","1111111","1111111","0111110","0011100"],
    "rain":  ["0011100","0111110","1111111","1111111","0010010","0100100","1001000"],
    "snow":  ["0010000","1010100","0111100","0010000","0111100","1010100","0010000"],
    "storm": ["0001000","0011100","0111110","1111111","0001100","0011000","0110000"],
    "fog":   ["0000000","1111111","0000000","1111111","0000000","1111111","0000000"],
}

def code_to_icon_label(wc):
    if wc in (0,): return "sun","klar"
    if wc in (1,2): return "sun","heiter"
    if wc in (3,): return "cloud","bedeckt"
    if wc in (45,48): return "fog","Nebel"
    if wc in (51,53,55,61,63,65,80,81,82): return "rain","Regen"
    if wc in (71,73,75,77,85,86): return "snow","Schnee"
    if wc in (95,96,99): return "storm","Gewitter"
    return "cloud","Wetter"

def draw_icon(name):
    bmp = ICON.get(name, ICON["sun"])
    clear(); x_off = 5
    for y,row in enumerate(bmp):
        for x,ch in enumerate(row):
            if ch == "1":
                setpx(x+x_off, y, BRIGHT)
    _commit()

# ---- 3x5 Font ----
FONT3x5 = {
    "0":["111","101","101","101","111"],
    "1":["010","110","010","010","111"],
    "2":["111","001","111","100","111"],
    "3":["111","001","111","001","111"],
    "4":["101","101","111","001","001"],
    "5":["111","100","111","001","111"],
    "6":["111","100","111","101","111"],
    "7":["111","001","001","010","010"],
    "8":["111","101","111","101","111"],
    "9":["111","101","111","001","111"],
    "/":["001","001","010","100","100"],
    "-":["000","000","111","000","000"],
    "°":["111","101","111","000","000"],
}

def draw_small_text(txt, y_top=1, x_start=0):
    x = x_start
    for ch in txt:
        g = FONT3x5.get(ch)
        if not g:
            x += 2
            continue
        for ry,row in enumerate(g):
            for rx,c in enumerate(row):
                if c == "1":
                    xx = x+rx; yy = y_top+ry
                    if 0<=xx<WIDTH and 0<=yy<HEIGHT:
                        setpx(xx, yy, BRIGHT)
        x += 4
    _commit()

def fmt_day_label(date_iso):
    try:
        y,m,d = date_iso.split("-"); return "{}/{}".format(d,m)
    except Exception:
        return "??/??"

# ---- WLAN / HTTP ----
def wifi_connect(ssid, pwd, timeout_s=20):
    wlan = network.WLAN(network.STA_IF); wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, pwd)
        t0 = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_s*1000: return False, None
            time.sleep_ms(200)
    return True, wlan.ifconfig()

def http_get_json(url, timeout=15):
    try:
        import urequests as requests
        r = requests.get(url, timeout=timeout)
        try: return r.json()
        finally: r.close()
    except Exception:
        import usocket as socket, ussl
        proto, _, hostpath = url.partition("://")
        host, _, path = hostpath.partition("/")
        addr = socket.getaddrinfo(host, 443 if proto=="https" else 80)[0][-1]
        s = socket.socket(); s.connect(addr)
        if proto == "https": s = ussl.wrap_socket(s, server_hostname=host)
        s.write("GET /{} HTTP/1.0\r\nHost: {}\r\n\r\n".format(path, host))
        while True:
            line = s.readline()
            if not line or line == b"\r\n": break
        body=b""
        while True:
            d = s.read(1024)
            if not d: break
            body += d
        s.close()
        return json.loads(body)

def get_location():
    j = http_get_json("http://ip-api.com/json/?fields=status,lat,lon,city,country")
    if j and j.get("status")=="success":
        return j["lat"], j["lon"], j.get("city") or "Ort", j.get("country") or ""
    return None, None, "Ort", ""

def get_weather(lat, lon, days=7):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude={:.4f}&longitude={:.4f}"
        "&current=temperature_2m,weather_code"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min"
        "&forecast_days={}"
        "&temperature_unit=celsius"
        "&timezone=auto"
    ).format(lat, lon, max(1,min(7,days)))
    j = http_get_json(url)
    cur = (j.get("current") or {})
    daily = (j.get("daily") or {})
    return {
        "current_temp": cur.get("temperature_2m"),
        "current_code": cur.get("weather_code"),
        "time": daily.get("time") or [],
        "code": daily.get("weather_code") or [],
        "tmax": daily.get("temperature_2m_max") or [],
        "tmin": daily.get("temperature_2m_min") or [],
    }

# ---- App-Klasse ----
class AppWeather:
    name = "Wetter"

    def __init__(self, lat=None, lon=None, city="Ort"):
        # user prefs / fixed location (optional)
        self.lat = lat
        self.lon = lon
        self.city = city

        # runtime state
        self.day_sel = 0
        self.cache = {"t": 0, "data": None, "city": city}
        self.next_fetch_ms = 0
        self.mode = "idle"
        self.step = 0
        self.timer = 0

        # button edge detection
        self._last_a = False
        self._last_b = False
        self._last_y = False

        # non-blocking scroll state
        self._scroll = None
        self._scroll_wait = False

    def init(self):
        # Always show *something* immediately so it doesn't look dead
        clear()
        draw_icon("cloud")
        self.next_fetch_ms = 0
        self.day_sel = 0
        self.mode = "idle"
        self.step = 0
        self.timer = 0
        self._scroll = None
        self._scroll_wait = False

        # Try Wi-Fi briefly; if it fails we still run
        try:
            ok, _ = wifi_connect(WIFI_SSID, WIFI_PASS, timeout_s=5)
            if not ok:
                draw_icon("storm")
        except Exception:
            draw_icon("storm")

    def _ensure_data(self):
        if (self.cache["data"] is None) or (time.time() - self.cache["t"] > REFRESH_S) or (self.next_fetch_ms <= 0):
            try:
                if self.lat is not None and self.lon is not None:
                    lat, lon, city = self.lat, self.lon, self.city
                else:
                    lat, lon, city, _ = get_location()
                    if lat is None:
                        lat, lon, city = 47.3769, 8.5417, "ZRH"
                self.cache["data"] = get_weather(lat, lon, 7)
                self.cache["t"] = time.time()
                self.cache["city"] = city or "Ort"
                self.next_fetch_ms = REFRESH_S * 1000
            except Exception:
                self.cache["data"] = None
                self.next_fetch_ms = 10_000
        else:
            self.next_fetch_ms = max(0, self.next_fetch_ms - 50)

    # --- non-blocking scrolling helpers ---
    def _start_scroll(self, val, y_top=1):
        """Draw text. If it fits, draw once and return True; else set up scrolling and return False."""
        char_width = 4
        txt_width = len(val) * char_width - 1
        if txt_width <= WIDTH:
            clear()
            draw_small_text(val, y_top=y_top, x_start=(WIDTH - txt_width)//2)
            _commit()
            self._scroll = None
            return True
        self._scroll = {
            "text": val,
            "y": y_top,
            "offset": WIDTH,
            "end": -txt_width,
            "acc": 0,
            "step_ms": 60,
        }
        return False

    def _advance_scroll(self, dt_ms, buttons):
        """Advance the scroller. Returns True when finished or cancelled."""
        if buttons.get("B") or buttons.get("A") or buttons.get("X") or buttons.get("Y"):
            self._scroll = None
            return True
        s = self._scroll
        if not s:
            return True
        s["acc"] += dt_ms
        moved = False
        while s["acc"] >= s["step_ms"]:
            s["acc"] -= s["step_ms"]
            s["offset"] -= 1
            moved = True
        if moved:
            clear()
            draw_small_text(s["text"], y_top=s["y"], x_start=s["offset"])
            _commit()
        if s["offset"] <= s["end"]:
            self._scroll = None
            return True
        return False

    def _draw_instant(self, val, y_top=1):
        """Instant small text (no scrolling), used for '+1' etc."""
        char_width = 4
        txt_width = len(val) * char_width - 1
        clear()
        draw_small_text(val, y_top=y_top, x_start=max(0, (WIDTH - txt_width)//2))
        _commit()

    def update(self, dt_ms, buttons, events):
        # --- A-Toggle: Start/Stopp der Wochenanzeige ---
        if buttons["A"] and not self._last_a:
            if self.mode == "tn":
                self.mode = "idle"
                clear()
            else:
                self.mode = "tn"
                self.step = 0
                self.timer = 0
        self._last_a = buttons["A"]

        # --- Y: Tag wechseln ---
        if buttons["Y"] and not self._last_y:
            self.day_sel = (self.day_sel + 1) % 8
            sign = "" if self.day_sel == 0 else "+"
            self._draw_instant(sign + str(self.day_sel))
            self.mode = "idle"; self.timer = 300; self.step = 0
        self._last_y = buttons["Y"]

        # --- B: Start single view when idle; otherwise SKIP/CANCEL current sequence ---
        if buttons["B"] and not self._last_b:
            if self.mode == "idle":
                self.mode = "one"; self.step = 0; self.timer = 0
            else:
                self.mode = "idle"
                self._scroll = None
                self._scroll_wait = False
                self.step = 0
                self.timer = 0
                clear()
        self._last_b = buttons["B"]

        # --- X: Icons sequence (optional) ---
        if buttons.get("X"):
            if self.mode != "icons":
                self.mode = "icons"; self.step = 0; self.timer = 0

        # --- Wetterdaten prüfen ---
        self._ensure_data()
        d = self.cache["data"]
        self.timer = max(0, self.timer - dt_ms)

        # --- Einzelanzeige ---
        if self.mode == "one":
            if not d:
                draw_icon("storm"); self.mode = "idle"; return
            if self.step == 0:
                code = d["current_code"] if self.day_sel == 0 else d["code"][min(self.day_sel-1, len(d["code"])-1)]
                draw_icon(code_to_icon_label(code if code is not None else 3)[0])
                self.timer = 400; self.step = 1
            elif self.step == 1 and self.timer == 0:
                if self.day_sel == 0:
                    t = d["current_temp"]
                    s = "{}°".format(int(round(float(t))) if t is not None else "?")
                else:
                    i = min(self.day_sel-1, len(d["tmax"])-1)
                    tmax = d["tmax"][i] if i>=0 else None
                    tmin = d["tmin"][i] if i>=0 else None
                    s = "{}/{}".format("?" if tmax is None else int(round(tmax)),
                                       "?" if tmin is None else int(round(tmin)))
                if not self._scroll_wait:
                    done = self._start_scroll(s)
                    if done:
                        self.timer = 800; self.step = 2
                    else:
                        self._scroll_wait = True
                else:
                    if self._advance_scroll(dt_ms, buttons):
                        self._scroll_wait = False
                        self.timer = 800; self.step = 2
            elif self.step == 2 and self.timer == 0:
                self.mode = "idle"

        # --- Icon-Sequenz ---
        elif self.mode == "icons":
            if not d:
                draw_icon("storm"); self.mode = "idle"; return
            if self.step == 0:
                draw_icon(code_to_icon_label(d["current_code"] if d["current_code"] is not None else 3)[0])
                self.timer = 250; self.step = 1
            elif 1 <= self.step <= 7:
                i = self.step - 1
                if i < len(d["code"]):
                    draw_icon(code_to_icon_label(d["code"][i])[0])
                self.timer = 250; self.step += 1
            elif self.step > 7 and self.timer == 0:
                self.mode = "idle"

        # --- Wochenanzeige (Tmax/Tmin) ---
        elif self.mode == "tn":
            if not d:
                draw_icon("storm"); self.mode = "idle"; return
            total = min(7, len(d["time"]))
            if self.step < total * 2:
                i = self.step // 2
                s = fmt_day_label(d["time"][i]) if self.step % 2 == 0 else "{}/{}".format(
                    "?" if d["tmax"][i] is None else int(round(d["tmax"][i])),
                    "?" if d["tmin"][i] is None else int(round(d["tmin"][i])))
                if not self._scroll_wait:
                    done = self._start_scroll(s)
                    if done:
                        self.timer = 450; self.step += 1
                    else:
                        self._scroll_wait = True
                else:
                    if self._advance_scroll(dt_ms, buttons):
                        self._scroll_wait = False
                        self.timer = 450; self.step += 1
            else:
                self.mode = "idle"


