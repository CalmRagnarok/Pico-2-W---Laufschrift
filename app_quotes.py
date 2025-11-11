# app_quotes.py — Zufalls-Sprüche aus sprueche.txt
# X: zufälliger Spruch (mit 2s Verzögerung)
# Y: nächster Spruch (mit 2s Verzögerung)
# A/B: Helligkeit +/-
# Scroll startet außerhalb rechts und läuft rein.
#
# nicht-blockierend, damit dein Launcher weiter X-Doppelklick erkennt.

import time
import picoscroll as scroll
try:
    import urandom as random
except ImportError:
    import random

FILENAME = "sprueche.txt"
SCROLL_MS = 80
START_DELAY_MS = 100  # 2 Sekunden warten

sc = scroll.PicoScroll()
WIDTH, HEIGHT = scroll.WIDTH, scroll.HEIGHT
DEFAULT_BRIGHT = 70

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
    sc.clear(); _commit()

# 5-zeiliger Font
FONT = {
    "A":["0110","1001","1111","1001","1001"],
    "B":["1110","1001","1110","1001","1110"],
    "C":["0111","1000","1000","1000","0111"],
    "D":["1110","1001","1001","1001","1110"],
    "E":["1111","1000","1110","1000","1111"],
    "F":["1111","1000","1110","1000","1000"],
    "G":["0111","1000","1011","1001","0111"],
    "H":["1001","1001","1111","1001","1001"],
    "I":["111","010","010","010","111"],
    "J":["0011","0001","0001","1001","0110"],
    "K":["1001","1010","1100","1010","1001"],
    "L":["1000","1000","1000","1000","1111"],
    "M":["10001","11011","10101","10001","10001"],  # <-- damit "MUT" geht
    "N":["1001","1101","1011","1001","1001"],
    "O":["0110","1001","1001","1001","0110"],
    "P":["1110","1001","1110","1000","1000"],
    "R":["1110","1001","1110","1010","1001"],
    "S":["0111","1000","0110","0001","1110"],
    "T":["11111","00100","00100","00100","00100"],
    "U":["1001","1001","1001","1001","0110"],
    "V":["10001","10001","01010","01010","00100"],
    "W":["10001","10001","10101","10101","01010"],
    "Y":["1001","1001","0110","0010","1110"],
    "Z":["1111","0001","0010","0100","1111"],
    # Umlaute
    "Ä":["0110","1001","1111","1001","1001"],
    "Ö":["0110","1001","1001","1001","0110"],
    "Ü":["1001","1001","1001","1001","0110"],
    # Ziffern
    "0":["0110","1001","1001","1001","0110"],
    "1":["010","110","010","010","111"],
    "2":["111","001","111","100","111"],
    "3":["111","001","111","001","111"],
    "4":["101","101","111","001","001"],
    "5":["111","100","111","001","111"],
    "6":["011","100","111","101","011"],
    "7":["111","001","010","010","010"],
    "8":["111","101","111","101","111"],
    "9":["111","101","111","001","111"],
    # Satzzeichen
    "!":["1","1","1","0","1"],
    "?":["111","001","010","000","010"],
    ".":["0","0","0","0","1"],
    ",":["0","0","0","1","1"],
    ":":["0","1","0","1","0"],
    "-":["0","0","111","0","0"],
    " " :["0","0","0","0","0"],
}

def normalize_text(t: str) -> str:
    # 1. typografische Striche/Quotes glätten
    t = t.replace("–", "-").replace("—", "-")
    t = t.replace("„", " ").replace("“", " ").replace("”", " ")
    t = t.replace("’", "'")
    # 2. geschützte/leise Spaces -> normales Space
    t = t.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    # 3. Umlaute
    t = t.replace("ä", "Ä").replace("ö", "Ö").replace("ü", "Ü")
    t = t.replace("Ä", "Ä").replace("Ö", "Ö").replace("Ü", "Ü")
    t = t.replace("ß", "SS")
    # 4. groß
    t = t.upper()
    return t

def text_to_columns(text):
    # Start-Padding, damit der Text wirklich von rechts reinkommt
    cols = [0] * WIDTH

    text = text.strip()
    if not text:
        text = "..."

    text = normalize_text(text)

    for ch in text:
        glyph = FONT.get(ch, FONT[" "])
        max_w = max(len(row) for row in glyph)
        for x in range(max_w):
            col = 0
            for y, row in enumerate(glyph):
                if x < len(row) and row[x] == "1":
                    # +1 → Text etwas nach unten setzen
                    col |= (1 << (y + 1))
            cols.append(col)
        # 1 Spalte Abstand zwischen Zeichen
        cols.append(0)

    # End-Padding zum Ausscrollen
    cols += [0] * WIDTH
    return cols

class AppQuotes:
    name = "Quotes"

    def __init__(self, filename=FILENAME):
        self.filename = filename
        self.lines = ["KEIN SPRUCH"]
        self.scroll_cols = []
        self.scroll_ofs = 0
        self.scroll_timer = 0
        self.bright = DEFAULT_BRIGHT
        self.last_idx = -1
        # verzögerter Start
        self.pending_text = None
        self.pending_delay = 0   # ms

    def _load_file(self):
        try:
            with open(self.filename, "r") as f:
                raw = f.read().splitlines()
            lines = [ln.strip() for ln in raw if ln.strip()]
            if lines:
                self.lines = lines
        except Exception:
            self.lines = [
                "SPRUeCHE.TXT FEHLT",
                "EINE ZEILE = EIN SPRUCH",
            ]

    def _start_scroll_now(self, text: str):
        self.scroll_cols = text_to_columns(text)
        self.scroll_ofs = 0
        self.scroll_timer = 0

    def _pick_random(self):
        if len(self.lines) == 1:
            self.last_idx = 0
            return self.lines[0]
        while True:
            idx = random.getrandbits(16) % len(self.lines)
            if idx != self.last_idx:
                self.last_idx = idx
                return self.lines[idx]

    def init(self):
        clear()
        self._load_file()
        # ersten Spruch nur planen
        self.pending_text = self.lines[0]
        self.pending_delay = START_DELAY_MS
        self.scroll_cols = []

    def _update_pending(self, dt_ms):
        if self.pending_text is None:
            return
        self.pending_delay -= dt_ms
        if self.pending_delay <= 0:
            self._start_scroll_now(self.pending_text)
            self.pending_text = None
            self.pending_delay = 0

    def _scroll_step(self, dt_ms):
        if not self.scroll_cols:
            return
        self.scroll_timer += dt_ms
        if self.scroll_timer < SCROLL_MS:
            return
        self.scroll_timer = 0
        self.scroll_ofs += 1
        if self.scroll_ofs >= len(self.scroll_cols):
            # fertig; stehen lassen
            self.scroll_ofs = len(self.scroll_cols) - 1
            return
        sc.clear()
        base = self.scroll_ofs
        for x in range(WIDTH):
            idx = base + x
            col = self.scroll_cols[idx] if idx < len(self.scroll_cols) else 0
            for y in range(7):
                if col & (1 << y):
                    sc.set_pixel(x, y, self.bright)
        _commit()

    def update(self, dt_ms, buttons, events):
        # Helligkeit
        if buttons.get("A"):
            self.bright = max(0, self.bright - 3)
        if buttons.get("B"):
            self.bright = min(255, self.bright + 3)

        # X → zufälligen Spruch (mit 2 s Delay)
        if events.get("x_single") or (buttons.get("X") and not events.get("x_double")):
            q = self._pick_random()
            self.pending_text = q
            self.pending_delay = START_DELAY_MS
            self.scroll_cols = []

        # Y → nächster in der Datei
        if buttons.get("Y"):
            if not hasattr(self, "_seq_idx"):
                self._seq_idx = 0
            self._seq_idx = (self._seq_idx + 1) % len(self.lines)
            self.last_idx = self._seq_idx
            self.pending_text = self.lines[self._seq_idx]
            self.pending_delay = START_DELAY_MS
            self.scroll_cols = []

        # zuerst evtl. wartenden Spruch starten
        self._update_pending(dt_ms)
        # dann scrollen
        self._scroll_step(dt_ms)
