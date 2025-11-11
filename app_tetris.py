# app_tetris.py — nicht-blockierendes Tetris für Pico Scroll Pack
# Mapping:
#   B = links
#   A = rechts
#   Y = drehen
#   X = schneller nach unten (soft drop)

import time
import picoscroll as scroll
try:
    import urandom as random
except ImportError:
    import random

sc = scroll.PicoScroll()
DISP_W, DISP_H = scroll.WIDTH, scroll.HEIGHT   # 17 x 7
BRIGHT_ON    = 80
BRIGHT_GHOST = 30

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

def clear_display():
    sc.clear(); _commit()

W, H = 7, 17  # Spielfeld hochkant 7 breit, 17 hoch

PIECES = {
    "I":[[(0,0),(1,0),(2,0),(3,0)],[(2,-1),(2,0),(2,1),(2,2)],[(0,1),(1,1),(2,1),(3,1)],[(1,-1),(1,0),(1,1),(1,2)]],
    "O":[[(0,0),(1,0),(0,1),(1,1)]]*4,
    "T":[[(0,0),(1,0),(2,0),(1,1)],[(1,-1),(1,0),(1,1),(2,0)],[(0,0),(1,0),(2,0),(1,-1)],[(1,-1),(1,0),(1,1),(0,0)]],
    "L":[[(0,0),(1,0),(2,0),(0,1)],[(1,-1),(1,0),(1,1),(2,1)],[(2,0),(1,0),(0,0),(2,-1)],[(1,1),(1,0),(1,-1),(0,-1)]],
    "J":[[(0,0),(1,0),(2,0),(2,1)],[(1,-1),(1,0),(1,1),(2,-1)],[(2,0),(1,0),(0,0),(0,-1)],[(1,1),(1,0),(1,-1),(0,1)]],
    "S":[[(1,0),(2,0),(0,1),(1,1)],[(1,-1),(1,0),(2,0),(2,1)],[(1,0),(2,0),(0,1),(1,1)],[(1,-1),(1,0),(2,0),(2,1)]],
    "Z":[[(0,0),(1,0),(1,1),(2,1)],[(2,-1),(1,0),(2,0),(1,1)],[(0,0),(1,0),(1,1),(2,1)],[(2,-1),(1,0),(2,0),(1,1)]],
}
ORDER = ["I","J","L","O","S","T","Z"]

def new_bag():
    bag = ORDER[:]
    for i in range(len(bag)-1, 0, -1):
        j = random.getrandbits(16) % (i+1)
        bag[i], bag[j] = bag[j], bag[i]
    return bag

def in_bounds(x,y): return 0 <= x < W and 0 <= y < H

def can_place(field, shape, px, py):
    for (dx,dy) in shape:
        x = px + dx; y = py + dy
        if not in_bounds(x,y): return False
        if field[x][y]: return False
    return True

def lock_piece(field, shape, px, py, v=BRIGHT_ON):
    for (dx,dy) in shape:
        x = px + dx; y = py + dy
        if in_bounds(x,y): field[x][y] = v

def clear_lines(field):
    cleared = 0
    for y in range(H):
        if all(field[x][y] for x in range(W)):
            cleared += 1
            for yy in range(y, H-1):
                for x in range(W):
                    field[x][yy] = field[x][yy+1]
            for x in range(W):
                field[x][H-1] = 0
    return cleared

class Active:
    def __init__(self, kind):
        self.kind = kind
        self.rot = 0
        self.shape = PIECES[kind][self.rot]
        self.x = (W//2) - 1
        self.y = H - 3
        if not can_place([[0]*H for _ in range(W)], self.shape, self.x, self.y):
            self.y = H - 4
    def rotated(self):
        r = (self.rot + 1) % len(PIECES[self.kind])
        return PIECES[self.kind][r], r
    def apply_rot(self, r):
        self.rot = r
        self.shape = PIECES[self.kind][self.rot]

def draw(field, cur=None):
    sc.clear()
    # fest
    for x in range(W):
        for y in range(H):
            v = field[x][y]
            if v:
                dx = y
                dy = (DISP_H-1) - x
                if 0 <= dx < DISP_W and 0 <= dy < DISP_H:
                    sc.set_pixel(dx, dy, v)
    # aktiv
    if cur:
        # ghost
        gx, gy = cur.x, cur.y
        while can_place(field, cur.shape, gx, gy-1):
            gy -= 1
        for (dx0,dy0) in cur.shape:
            dx = gy + dy0
            dy = (DISP_H-1) - (gx + dx0)
            if 0 <= dx < DISP_W and 0 <= dy < DISP_H:
                sc.set_pixel(dx, dy, BRIGHT_GHOST)
        # real
        for (dx0,dy0) in cur.shape:
            dx = cur.y + dy0
            dy = (DISP_H-1) - (cur.x + dx0)
            if 0 <= dx < DISP_W and 0 <= dy < DISP_H:
                sc.set_pixel(dx, dy, BRIGHT_ON)
    _commit()

class AppTetris:
    name = "Tetris"
    def __init__(self):
        self.field = [[0]*H for _ in range(W)]
        self.drop_ms = 700
        self.bag = new_bag()
        self.cur = Active(self.bag.pop())
        if not self.bag: self.bag = new_bag()
        self.prev = {"A":False,"B":False,"X":False,"Y":False}
        self.last_step = time.ticks_ms()
        self.last_soft_ms = 0
        self.lines = 0
        self.state = "play"  # "play" | "go_fill" | "go_clear"
        self.go_row = H-1
        self.timer = 0

    def init(self):
        self.field = [[0]*H for _ in range(W)]
        self.drop_ms = 700
        self.bag = new_bag()
        self.cur = Active(self.bag.pop())
        if not self.bag: self.bag = new_bag()
        self.prev = {"A":False,"B":False,"X":False,"Y":False}
        self.last_step = time.ticks_ms()
        self.last_soft_ms = 0
        self.lines = 0
        self.state = "play"; self.go_row = H-1; self.timer = 0
        clear_display()
        draw(self.field, self.cur)

    def _edges(self, buttons):
        return {
            "A": buttons.get("A",False) and not self.prev.get("A",False),
            "B": buttons.get("B",False) and not self.prev.get("B",False),
            "X": buttons.get("X",False) and not self.prev.get("X",False),
            "Y": buttons.get("Y",False) and not self.prev.get("Y",False),
        }

    def _spawn(self):
        if not self.bag:
            self.bag = new_bag()
        self.cur = Active(self.bag.pop())

    def _game_over_start(self):
        self.state = "go_fill"
        self.go_row = H-1
        self.timer = 0

    def update(self, dt_ms, buttons, events):
        # Game-Over-Animation non-blocking
        if self.state in ("go_fill", "go_clear"):
            self.timer += dt_ms
            step_ms = 40 if self.state == "go_fill" else 25
            if self.timer >= step_ms:
                self.timer = 0
                if self.state == "go_fill":
                    for x in range(W):
                        self.field[x][self.go_row] = BRIGHT_ON
                    self.go_row -= 1
                    if self.go_row < 0:
                        self.state = "go_clear"
                        self.go_row = 0
                    draw(self.field, None)
                else:
                    for x in range(W):
                        self.field[x][self.go_row] = 0
                    self.go_row += 1
                    if self.go_row >= H:
                        self.init()
                        return
                    draw(self.field, None)
            self.prev = buttons.copy()
            return

        edges = self._edges(buttons)
        need_redraw = False
        now = time.ticks_ms()

        # --- MAPPING ---
        # B -> LINKS
        if edges["B"] and can_place(self.field, self.cur.shape, self.cur.x - 1, self.cur.y):
            self.cur.x -= 1
            need_redraw = True

        # A -> RECHTS
        if edges["A"] and can_place(self.field, self.cur.shape, self.cur.x + 1, self.cur.y):
            self.cur.x += 1
            need_redraw = True

        # Y -> DREHEN
        if edges["Y"]:
            new_shape, new_rot = self.cur.rotated()
            for dx_try in (0, -1, 1):
                if can_place(self.field, new_shape, self.cur.x + dx_try, self.cur.y):
                    self.cur.apply_rot(new_rot)
                    self.cur.x += dx_try
                    need_redraw = True
                    break

        # X -> SOFT DROP (halten)
        if buttons.get("X", False):
            if time.ticks_diff(now, self.last_soft_ms) >= 60:
                self.last_soft_ms = now
                if can_place(self.field, self.cur.shape, self.cur.x, self.cur.y - 1):
                    self.cur.y -= 1
                    need_redraw = True
                else:
                    lock_piece(self.field, self.cur.shape, self.cur.x, self.cur.y, BRIGHT_ON)
                    c = clear_lines(self.field)
                    if c:
                        self.lines += c
                        self.drop_ms = max(120, self.drop_ms - 20*c)
                    self._spawn()
                    if not can_place(self.field, self.cur.shape, self.cur.x, self.cur.y):
                        self._game_over_start()
                        return
                    need_redraw = True

        # Gravitation
        if time.ticks_diff(now, self.last_step) >= self.drop_ms:
            if can_place(self.field, self.cur.shape, self.cur.x, self.cur.y - 1):
                self.cur.y -= 1
            else:
                lock_piece(self.field, self.cur.shape, self.cur.x, self.cur.y, BRIGHT_ON)
                c = clear_lines(self.field)
                if c:
                    self.lines += c
                    self.drop_ms = max(120, self.drop_ms - 20*c)
                self._spawn()
                if not can_place(self.field, self.cur.shape, self.cur.x, self.cur.y):
                    self._game_over_start()
                    return
            need_redraw = True
            self.last_step = now

        if need_redraw:
            draw(self.field, self.cur)

        self.prev = buttons.copy()
