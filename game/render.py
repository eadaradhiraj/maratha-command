"""All pygame drawing: the hex map, counters, side panel and overlays."""
import math
import random
import time

import pygame

from . import data, hexgrid
from .data import MARATHA, MUGHAL, SIDE_COLORS, SIDE_DARK

PANEL_W = 340
ZOOMS = (18, 22, 27, 33, 40, 48)

BG = (26, 22, 18)
PANEL_BG = (36, 30, 24)
GOLD = (218, 178, 80)
TEXT = (236, 226, 204)
MUTED = (164, 152, 130)
RED = (222, 78, 60)
GREEN = (120, 200, 120)
BLUE = (120, 178, 236)
RIVER = (72, 128, 186)
RIVER_HI = (124, 176, 226)
STONE = (226, 214, 186)
INK = (40, 30, 22)


def _jitter(color, col, row, amt=7):
    h = ((col * 73856093) ^ (row * 19349663)) & 0xFFFF
    d = h % (2 * amt + 1) - amt
    return tuple(max(0, min(255, c + d)) for c in color)


def wrap(text, font, width):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if font.size(trial)[0] <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.W, self.H = screen.get_size()
        self.map_w = self.W - PANEL_W
        self.zoom_i = 3
        self.size = ZOOMS[self.zoom_i]
        self.cam = [0.0, 0.0]
        self.cache = {}
        self.fonts = {}
        self.buttons = {}

    # ------------------------------------------------------------ utilities
    def font(self, size, bold=False, serif=False):
        key = (size, bold, serif)
        if key not in self.fonts:
            name = "georgia,palatinolinotype,timesnewroman" if serif else "segoeui,arial,helvetica"
            self.fonts[key] = pygame.font.SysFont(name, size, bold=bold)
        return self.fonts[key]

    def origin(self, size=None):
        s = size or self.size
        return s * hexgrid.SQRT3 / 2 + 6, s + 6

    def map_pixel_size(self, size):
        return (int(size * hexgrid.SQRT3 * (data.COLS + 0.5) + 12),
                int(size * 1.5 * (data.ROWS - 1) + 2 * size + 12))

    def hex_center(self, pos, size=None):
        s = size or self.size
        x, y = hexgrid.hex_to_pixel(pos[0], pos[1], s)
        ox, oy = self.origin(s)
        return x + ox, y + oy

    def to_screen(self, pos):
        x, y = self.hex_center(pos)
        return x - self.cam[0], y - self.cam[1]

    def screen_to_hex(self, mx, my):
        ox, oy = self.origin()
        return hexgrid.pixel_to_hex(mx + self.cam[0] - ox, my + self.cam[1] - oy, self.size)

    def clamp_cam(self):
        w, h = self.map_pixel_size(self.size)
        m = 80
        self.cam[0] = max(-m, min(self.cam[0], max(-m, w - self.map_w + m)))
        self.cam[1] = max(-m, min(self.cam[1], max(-m, h - self.H + m)))

    def center_on(self, pos):
        x, y = self.hex_center(pos)
        self.cam = [x - self.map_w / 2, y - self.H / 2]
        self.clamp_cam()

    def is_visible(self, pos, margin=40):
        x, y = self.to_screen(pos)
        return -margin < x < self.map_w + margin and -margin < y < self.H + margin

    def zoom(self, direction, mx, my):
        ni = max(0, min(len(ZOOMS) - 1, self.zoom_i + direction))
        if ni == self.zoom_i:
            return
        ox, oy = self.origin()
        wx = (mx + self.cam[0] - ox) / self.size
        wy = (my + self.cam[1] - oy) / self.size
        self.zoom_i = ni
        self.size = ZOOMS[ni]
        ox, oy = self.origin()
        self.cam = [wx * self.size + ox - mx, wy * self.size + oy - my]
        self.clamp_cam()

    def _text(self, text, x, y, font, color, shadow=False):
        if shadow:
            self.screen.blit(font.render(text, True, (0, 0, 0)), (x + 1, y + 1))
        img = font.render(text, True, color)
        self.screen.blit(img, (x, y))
        return y + img.get_height()

    def _label(self, text, cx, cy, font, color=TEXT):
        img = font.render(text, True, color)
        outline = font.render(text, True, (20, 14, 8))
        r = img.get_rect(center=(int(cx), int(cy)))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.screen.blit(outline, r.move(dx, dy))
        self.screen.blit(img, r)

    # -------------------------------------------------------------- terrain
    def terrain_surface(self):
        s = self.size
        if s in self.cache:
            return self.cache[s]
        surf = pygame.Surface(self.map_pixel_size(s))
        surf.fill(data.TERRAIN["~"]["color"])
        for r in range(data.ROWS):
            for c in range(data.COLS):
                self._draw_terrain_hex(surf, c, r, s)
        width = max(3, int(s * 0.2))
        for path in data.RIVER_PATHS.values():
            pts = [self.hex_center(p, s) for p in path]
            pygame.draw.lines(surf, RIVER, False, pts, width)
            for x, y in pts:
                pygame.draw.circle(surf, RIVER, (int(x), int(y)), width // 2)
            pygame.draw.lines(surf, RIVER_HI, False, pts, max(1, width // 3))
        grid = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        for r in range(data.ROWS):
            for c in range(data.COLS):
                cx, cy = self.hex_center((c, r), s)
                pygame.draw.polygon(grid, (30, 20, 10, 46), hexgrid.hex_corners(cx, cy, s), 1)
        surf.blit(grid, (0, 0))
        self.cache[s] = surf
        return surf

    def _draw_terrain_hex(self, surf, c, r, s):
        ch = data.GRID[r][c]
        cx, cy = self.hex_center((c, r), s)
        pygame.draw.polygon(surf, _jitter(data.TERRAIN[ch]["color"], c, r),
                            hexgrid.hex_corners(cx, cy, s + 0.7))
        rnd = random.Random(c * 1009 + r * 7919)
        if ch == "~":
            for _ in range(2):
                x = cx + rnd.uniform(-0.5, 0.2) * s
                y = cy + rnd.uniform(-0.4, 0.3) * s
                pygame.draw.arc(surf, (96, 140, 184), (x, y, s * 0.4, s * 0.22), 0.4, 2.7, 1)
        elif ch == "f":
            for _ in range(5):
                x = int(cx + rnd.uniform(-0.5, 0.5) * s)
                y = int(cy + rnd.uniform(-0.45, 0.45) * s)
                rr = max(2, int(s * rnd.uniform(0.13, 0.19)))
                pygame.draw.circle(surf, (50, 78, 40), (x, y + 1), rr)
                pygame.draw.circle(surf, (78, 114, 56), (x, y), rr)
                pygame.draw.circle(surf, (106, 142, 72), (x - rr // 3, y - rr // 3), max(1, rr // 2))
        elif ch == "h":
            for _ in range(2):
                x = cx + rnd.uniform(-0.5, 0.05) * s
                y = cy + rnd.uniform(-0.25, 0.3) * s
                w, h = s * rnd.uniform(0.55, 0.75), s * 0.45
                pygame.draw.arc(surf, (118, 94, 60), (x, y - h / 2, w, h), 0.15, math.pi - 0.15,
                                max(1, s // 12))
        elif ch == "m":
            for dx, sc in ((-0.28, 1.0), (0.26, 0.78)):
                bx, by = cx + dx * s, cy + 0.38 * s
                h, w = s * 0.8 * sc, s * 0.48 * sc
                top = (bx, by - h)
                pygame.draw.polygon(surf, (168, 148, 120), [(bx - w, by), top, (bx, by)])
                pygame.draw.polygon(surf, (104, 86, 66), [top, (bx + w, by), (bx, by)])
                pygame.draw.lines(surf, (72, 58, 44), False, [(bx - w, by), top, (bx + w, by)], 1)

    # --------------------------------------------------------------- frame
    def draw(self, g):
        now = time.time()
        scr = self.screen
        scr.fill(BG)
        scr.set_clip(pygame.Rect(0, 0, self.map_w, self.H))
        scr.blit(self.terrain_surface(), (-self.cam[0], -self.cam[1]))
        self._draw_overlays(g)
        self._draw_path_preview(g)
        for loc in g.state.locations.values():
            if self.is_visible(loc.pos):
                self._draw_location(loc)
        self._draw_units(g, now)
        self._draw_targets(g, now)
        for loc in g.state.locations.values():
            if self.is_visible(loc.pos, 80):
                x, y = self.to_screen(loc.pos)
                self._label(loc.name, x, y + self.size * 0.72,
                            self.font(max(10, int(self.size * 0.4)), True), STONE)
        self._draw_floaters(g, now)
        scr.set_clip(None)
        self._draw_panel(g)
        self._draw_tooltip(g)
        if g.mode == "briefing":
            self._draw_briefing()
        elif g.mode == "gameover":
            self._draw_gameover(g)
        elif g.mode == "ai":
            self._draw_banner("Mughal turn...")

    def _draw_overlays(self, g):
        s = g.state
        layer = pygame.Surface((self.map_w, self.H), pygame.SRCALPHA)
        if g.supply_mode:
            side = MARATHA if g.supply_mode == 1 else MUGHAL
            col = SIDE_COLORS[side] + (78,)
            for pos in s.supply[side]:
                if self.is_visible(pos):
                    x, y = self.to_screen(pos)
                    pygame.draw.polygon(layer, col, hexgrid.hex_corners(x, y, self.size - 1))
        if g.selected is not None:
            for pos in g.reach:
                x, y = self.to_screen(pos)
                pygame.draw.polygon(layer, (255, 250, 230, 70), hexgrid.hex_corners(x, y, self.size - 1))
            x, y = self.to_screen(g.selected.pos)
            pygame.draw.polygon(layer, (255, 230, 120, 90), hexgrid.hex_corners(x, y, self.size - 1))
        if g.hover is not None and data.in_bounds(g.hover):
            x, y = self.to_screen(g.hover)
            pygame.draw.polygon(layer, (255, 255, 255, 170), hexgrid.hex_corners(x, y, self.size - 1), 2)
        self.screen.blit(layer, (0, 0))

    def _draw_path_preview(self, g):
        if g.selected is None or g.hover not in g.reach or g.mode != "player":
            return
        pts = [self.to_screen(p) for p in g.state.path(g.prev, g.hover)]
        if len(pts) > 1:
            pygame.draw.lines(self.screen, (255, 236, 160), False, pts, 3)
            pygame.draw.circle(self.screen, (255, 236, 160), [int(v) for v in pts[-1]], 5)

    def _draw_location(self, loc):
        x, y = self.to_screen(loc.pos)
        s = self.size
        owner = SIDE_COLORS[loc.owner]
        pygame.draw.polygon(self.screen, owner, hexgrid.hex_corners(x, y, s - 2), max(2, s // 10))
        if loc.kind == "city":
            for rx, ry, rw, rh in ((-0.5, -0.05, 0.3, 0.32), (-0.16, -0.22, 0.34, 0.5), (0.22, 0.0, 0.28, 0.27)):
                rect = pygame.Rect(int(x + rx * s), int(y + ry * s), int(rw * s), int(rh * s))
                pygame.draw.rect(self.screen, STONE, rect)
                pygame.draw.rect(self.screen, INK, rect, 1)
            pygame.draw.circle(self.screen, STONE, (int(x + 0.01 * s), int(y - 0.22 * s)), int(0.16 * s))
            pygame.draw.circle(self.screen, INK, (int(x + 0.01 * s), int(y - 0.22 * s)), int(0.16 * s), 1)
        elif loc.kind == "fort":
            w, h, t = 0.62 * s, 0.42 * s, 0.12 * s
            left, top = x - w / 2, y - h / 2 + 0.05 * s
            pts = [(left, top + h), (left, top)]
            n = 4
            for i in range(n):
                x0 = left + w * i / n
                x1 = left + w * (i + 0.5) / n
                pts += [(x0, top), (x0, top - t), (x1, top - t), (x1, top)]
            pts += [(left + w, top), (left + w, top + h)]
            pygame.draw.polygon(self.screen, (176, 164, 140), pts)
            pygame.draw.polygon(self.screen, INK, pts, 1)
            gate = pygame.Rect(int(x - 0.08 * s), int(top + h * 0.45), int(0.16 * s), int(h * 0.55))
            pygame.draw.rect(self.screen, INK, gate)
        else:
            for dx, sc in ((-0.25, 0.9), (0.2, 1.0)):
                bx, by, w, h = x + dx * s, y + 0.25 * s, 0.3 * s * sc, 0.45 * s * sc
                pts = [(bx - w, by), (bx, by - h), (bx + w, by)]
                pygame.draw.polygon(self.screen, (238, 226, 196), pts)
                pygame.draw.polygon(self.screen, INK, pts, 1)
        px, py = x + 0.42 * s, y - 0.2 * s
        pygame.draw.line(self.screen, INK, (px, py), (px, py - 0.65 * s), 2)
        if loc.owner == MARATHA:
            flag = [(px, py - 0.65 * s), (px + 0.42 * s, py - 0.55 * s), (px + 0.22 * s, py - 0.47 * s),
                    (px + 0.42 * s, py - 0.38 * s), (px, py - 0.3 * s)]
        else:
            flag = [(px, py - 0.65 * s), (px + 0.4 * s, py - 0.65 * s), (px + 0.4 * s, py - 0.37 * s),
                    (px, py - 0.37 * s)]
        pygame.draw.polygon(self.screen, owner, flag)
        pygame.draw.polygon(self.screen, INK, flag, 1)
        if loc.vp:
            bx, by = int(x - 0.55 * s), int(y - 0.55 * s)
            pygame.draw.circle(self.screen, GOLD, (bx, by), max(6, int(s * 0.22)))
            pygame.draw.circle(self.screen, INK, (bx, by), max(6, int(s * 0.22)), 1)
            self._label(str(loc.vp), bx, by, self.font(max(9, int(s * 0.3)), True), (255, 255, 255))

    def _draw_units(self, g, now):
        anim = g.anim
        for u in g.state.units:
            if anim is not None and anim["unit"] is u:
                path = anim["path"]
                f = max(0.0, min(1.0, (now - anim["t0"]) / anim["dur"])) * (len(path) - 1)
                i = min(int(f), len(path) - 2)
                (x0, y0), (x1, y1) = self.to_screen(path[i]), self.to_screen(path[i + 1])
                k = f - i
                x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
            else:
                if not self.is_visible(u.pos):
                    continue
                x, y = self.to_screen(u.pos)
            self._draw_counter(g, u, x, y, now)

    def _draw_counter(self, g, u, x, y, now):
        s = self.size
        w, h = int(s * 1.3), int(s * 0.92)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (int(x), int(y))
        col, dark = SIDE_COLORS[u.side], SIDE_DARK[u.side]
        pygame.draw.rect(self.screen, (16, 10, 6), rect.move(2, 3), border_radius=4)
        pygame.draw.rect(self.screen, col, rect, border_radius=4)
        pygame.draw.rect(self.screen, dark, rect, 2, border_radius=4)

        box = pygame.Rect(0, 0, int(w * 0.5), int(h * 0.42))
        box.midtop = (rect.centerx, rect.top + int(h * 0.1))
        pygame.draw.rect(self.screen, (246, 240, 226), box)
        pygame.draw.rect(self.screen, INK, box, 1)
        sym = u.t["symbol"]
        lw = max(1, s // 18)
        if sym in ("inf", "mtn_inf"):
            pygame.draw.line(self.screen, INK, box.topleft, box.bottomright, lw)
            pygame.draw.line(self.screen, INK, box.bottomleft, box.topright, lw)
            if sym == "mtn_inf":
                tri = [(box.centerx - box.h * 0.35, box.bottom - 1), (box.centerx, box.bottom - box.h * 0.4),
                       (box.centerx + box.h * 0.35, box.bottom - 1)]
                pygame.draw.polygon(self.screen, INK, tri)
        elif sym in ("cav", "ele"):
            pygame.draw.line(self.screen, INK, box.bottomleft, box.topright, lw)
            if sym == "ele":
                pygame.draw.circle(self.screen, INK, box.center, max(2, box.h // 4))
        elif sym == "art":
            pygame.draw.circle(self.screen, INK, box.center, max(2, box.h // 3))

        fnt = self.font(max(9, int(s * 0.36)), True)
        self.screen.blit(fnt.render(str(u.steps), True, (255, 255, 255)), (rect.left + 3, rect.bottom - fnt.get_height()))
        if u.side == MARATHA:
            mp = self.font(max(8, int(s * 0.3))).render(str(u.mp), True, (255, 245, 220))
            self.screen.blit(mp, (rect.right - mp.get_width() - 3, rect.bottom - mp.get_height()))
        bar = pygame.Rect(rect.left + 2, rect.top + 2, int((w - 4) * u.steps / u.max_steps), max(2, s // 14))
        pygame.draw.rect(self.screen, (250, 240, 200), bar)

        if u.side == g.state.side_to_move and u.side == MARATHA and u.attacked and u.mp == 0:
            veil = pygame.Surface(rect.size, pygame.SRCALPHA)
            veil.fill((0, 0, 0, 90))
            self.screen.blit(veil, rect)
        if u.oos:
            c = (rect.left + 2, rect.top + 2)
            pygame.draw.circle(self.screen, RED, c, max(5, s // 5))
            self._label("!", c[0], c[1], self.font(max(9, s // 3), True), (255, 255, 255))
        if g.selected is u:
            pulse = 2 + int(1.5 * (1 + math.sin(now * 6)))
            pygame.draw.rect(self.screen, (255, 230, 90), rect.inflate(4, 4), pulse, border_radius=6)

    def _draw_targets(self, g, now):
        if g.selected is None or g.mode != "player":
            return
        for e in g.targets:
            x, y = self.to_screen(e.pos)
            pygame.draw.polygon(self.screen, RED, hexgrid.hex_corners(x, y, self.size - 2),
                                2 + int(1.5 * (1 + math.sin(now * 5))))

    def _draw_floaters(self, g, now):
        for f in g.floaters:
            k = (now - f["t0"]) / f["dur"]
            if not 0 <= k <= 1:
                continue
            x, y = self.to_screen(f["pos"])
            self._label(f["text"], x, y - self.size * (0.4 + 0.9 * k), self.font(max(14, int(self.size * 0.55)), True),
                        f["color"])

    # ---------------------------------------------------------------- panel
    def _sep(self, x, y, w):
        pygame.draw.line(self.screen, (90, 74, 52), (x, y), (x + w, y), 1)

    def _draw_panel(self, g):
        s = g.state
        x0 = self.map_w
        pygame.draw.rect(self.screen, PANEL_BG, (x0, 0, PANEL_W, self.H))
        pygame.draw.line(self.screen, GOLD, (x0, 0), (x0, self.H), 2)
        x, w = x0 + 16, PANEL_W - 32
        y = self._text("MARATHA COMMAND", x, 10, self.font(26, True, True), GOLD)
        y = self._text("The Deccan War, 1700-1701", x, y - 2, self.font(14, False, True), MUTED) + 6
        month, year = data.turn_date(s.turn)
        y = self._text("Turn %d of %d  -  %s %d" % (s.turn, data.MAX_TURNS, month, year), x, y,
                       self.font(17, True), TEXT)
        if s.monsoon:
            y = self._text("Monsoon: rivers swell, Mughals slowed", x, y, self.font(14), BLUE)
        else:
            y = self._text("Dry season", x, y, self.font(14), MUTED)
        score = s.score()
        level = data.victory_level(score)
        if level == "Defeat":
            level = "need %+d to win" % data.VICTORY_LEVELS[-1][0]
        y = self._text("Victory points: %+d  (%s)" % (score, level), x, y + 2, self.font(15, True), GOLD)
        y += 6
        self._sep(x, y, w)

        y = 140
        u = g.selected or (s.unit_at(g.hover) if g.hover else None)
        if u is not None:
            self._unit_block(g, u, x, y, w)
        else:
            self._text("Click one of your saffron counters.", x, y, self.font(14), MUTED)
        self._sep(x, 300, w)
        self._hover_block(g, x, 308, w)
        self._sep(x, 420, w)
        self._objectives(g, x, 426, w)

        by = 582
        self.buttons = {}
        labels = [("end", "End Turn", 112), ("next", "Next Unit", 92),
                  ("supply", ("Supply: off", "Supply: ours", "Supply: theirs")[g.supply_mode], 92)]
        bx = x
        mouse = pygame.mouse.get_pos()
        for key, label, bw in labels:
            rect = pygame.Rect(bx, by, bw, 32)
            active = g.mode == "player" or key == "supply"
            hot = rect.collidepoint(mouse) and active
            base = (150, 70, 20) if key == "end" else (70, 58, 44)
            pygame.draw.rect(self.screen, tuple(min(255, c + 30) for c in base) if hot else base, rect, border_radius=5)
            pygame.draw.rect(self.screen, GOLD if active else MUTED, rect, 1, border_radius=5)
            self._label(label, rect.centerx, rect.centery, self.font(14, True), TEXT if active else MUTED)
            self.buttons[key] = rect
            bx += bw + 6

        self._log(g, x, by + 42, w, self.H - 52 - (by + 42))
        help_font = self.font(11)
        hy = self.H - 46
        for line in wrap("Left click: select / move / attack.  Right drag or arrows: pan.  Wheel: zoom.  "
                         "Z undo move, N next unit, S supply, C centre, Space end turn.", help_font, w):
            hy = self._text(line, x, hy, help_font, MUTED)

    def _unit_block(self, g, u, x, y, w):
        s = g.state
        y = self._text(u.name, x, y, self.font(18, True, True), SIDE_COLORS[u.side])
        kind = u.t["name"] + ("  (garrison)" if u.garrison else "")
        y = self._text(kind, x, y, self.font(13), MUTED)
        y = self._text("Strength %d/%d    Attack %d    Defence %d" % (u.steps, u.max_steps, u.t["atk"], u.t["dfn"]),
                       x, y + 2, self.font(14), TEXT)
        moves = "Moves %d/%d" % (u.mp, s.max_mp(u)) if u.side == s.side_to_move else "Moves %d" % s.max_mp(u)
        if u.side == s.side_to_move and u.attacked:
            moves += "    (has attacked)"
        y = self._text(moves, x, y, self.font(14), TEXT)
        if u.oos:
            y = self._text("OUT OF SUPPLY for %d turn%s" % (u.oos, "s" if u.oos > 1 else ""), x, y,
                           self.font(14, True), RED)
        elif u.pos in s.supply[u.side]:
            y = self._text("In supply", x, y, self.font(14), GREEN)
        elif s.in_supply(u):
            y = self._text("Living off enemy land", x, y, self.font(14), GREEN)
        else:
            y = self._text("Supply line cut: out of supply next turn", x, y, self.font(14, True), (240, 170, 60))
        f = self.font(12)
        for trait in u.t["traits"]:
            for line in wrap(data.TRAIT_TEXT[trait], f, w)[:2]:
                if y > 286:
                    return
                y = self._text(line, x, y, f, MUTED)

    def _hover_block(self, g, x, y, w):
        s = g.state
        h = g.hover
        if h is None or not data.in_bounds(h):
            return
        target = s.unit_at(h)
        if g.selected is not None and target is not None and target in g.targets:
            p = s.combat_preview(g.selected, target)
            color = GREEN if p["ratio"] >= 1.5 else (TEXT if p["ratio"] >= 0.9 else RED)
            y = self._text("Attack %s: odds %.1f : 1" % (target.name, p["ratio"]), x, y, self.font(15, True), color)
            y = self._text("Expected losses: you %.1f, enemy %.1f" % (p["att_loss"], p["def_loss"]), x, y,
                           self.font(14), TEXT)
            if p["evade"]:
                y = self._text("Light horse will evade and fall back", x, y, self.font(13), MUTED)
            f = self.font(12)
            for note in p["notes"][:4]:
                y = self._text("- " + note, x, y, f, MUTED)
            return
        ter = data.terrain(h)
        loc = s.locations.get(h)
        line = ter["name"]
        if ter["move"]:
            line += "  (move %d, defence x%g)" % (ter["move"], ter["defense"])
        y = self._text(line, x, y, self.font(14, True), TEXT)
        if loc is not None:
            kind = {"fort": "Hill fort", "city": "City", "camp": "Imperial camp"}[loc.kind]
            y = self._text("%s: %s (%s)" % (kind, loc.name, data.SIDE_NAMES[loc.owner]), x, y, self.font(14),
                           SIDE_COLORS[loc.owner])
            extra = "Victory points %d" % loc.vp
            if loc.supply > 0:
                extra += ", supply source (range %d)" % loc.supply
            elif loc.kind == "fort":
                extra += ", stores supply its garrison"
            y = self._text(extra, x, y, self.font(13), MUTED)
        for side in (MARATHA, MUGHAL):
            if h in s.supply[side]:
                y = self._text("Within %s supply" % data.SIDE_NAMES[side], x, y, self.font(13), SIDE_COLORS[side])
        if target is not None and target is not g.selected and target.side == MUGHAL:
            y = self._text("%s - %s, strength %d" % (target.name, target.t["short"], target.steps), x, y + 2,
                           self.font(13, True), SIDE_COLORS[MUGHAL])

    def _objectives(self, g, x, y, w):
        y = self._text("Strongholds", x, y, self.font(15, True), GOLD)
        locs = sorted(g.state.locations.values(), key=lambda l: (l.orig_owner == MARATHA, -l.vp, l.name))
        f = self.font(13)
        col_w = w // 2
        for i, loc in enumerate(locs):
            cx = x + (i % 2) * col_w
            cy = y + 2 + (i // 2) * 17
            pygame.draw.rect(self.screen, SIDE_COLORS[loc.owner], (cx, cy + 4, 10, 10))
            flipped = loc.owner != loc.orig_owner
            self._text("%s (%d)%s" % (loc.name, loc.vp, " *" if flipped else ""), cx + 15, cy, f,
                       TEXT if flipped else MUTED)

    def _log(self, g, x, y, w, height):
        f = self.font(12)
        lines = []
        for text, side in reversed(g.state.log):
            color = SIDE_COLORS[side] if side else TEXT
            color = tuple(min(255, c + 40) for c in color)
            for line in wrap(text, f, w):
                lines.append((line, color))
            if len(lines) * 15 > height:
                break
        for line, color in lines[: max(0, height // 15)]:
            y = self._text(line, x, y, f, color)

    def _draw_tooltip(self, g):
        if g.selected is None or g.hover is None or g.mode != "player":
            return
        target = g.state.unit_at(g.hover)
        if target is None or target not in g.targets:
            return
        p = g.state.combat_preview(g.selected, target)
        text = "%.1f : 1   -%.0f / -%.0f" % (p["ratio"], p["att_loss"], p["def_loss"])
        img = self.font(14, True).render(text, True, TEXT)
        mx, my = pygame.mouse.get_pos()
        r = img.get_rect(topleft=(mx + 16, my + 12)).inflate(12, 8)
        pygame.draw.rect(self.screen, (20, 16, 12), r, border_radius=4)
        pygame.draw.rect(self.screen, GOLD, r, 1, border_radius=4)
        self.screen.blit(img, (r.left + 6, r.top + 4))

    # ------------------------------------------------------------- overlays
    def _veil(self, alpha=170):
        veil = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        veil.fill((10, 8, 6, alpha))
        self.screen.blit(veil, (0, 0))

    def _box(self, w, h):
        r = pygame.Rect(0, 0, w, h)
        r.center = (self.W // 2, self.H // 2)
        pygame.draw.rect(self.screen, (40, 32, 24), r, border_radius=8)
        pygame.draw.rect(self.screen, GOLD, r, 2, border_radius=8)
        return r

    def _draw_banner(self, text):
        img = self.font(18, True, True).render(text, True, TEXT)
        r = img.get_rect(midtop=(self.map_w // 2, 12)).inflate(24, 10)
        pygame.draw.rect(self.screen, (40, 24, 16), r, border_radius=6)
        pygame.draw.rect(self.screen, SIDE_COLORS[MUGHAL], r, 2, border_radius=6)
        self.screen.blit(img, (r.left + 12, r.top + 5))

    def _draw_briefing(self):
        self._veil()
        r = self._box(min(820, self.W - 60), min(580, self.H - 60))
        x, w = r.left + 36, r.width - 72
        y = self._text("Maratha Command", x, r.top + 24, self.font(36, True, True), GOLD)
        y = self._text("The Deccan, March 1700", x, y, self.font(18, False, True), MUTED) + 14
        f = self.font(16)
        for para in data.BRIEFING:
            for line in wrap(para, f, w):
                y = self._text(line, x, y, f, TEXT)
            y += 10
        self._label("Click or press Enter to take command", r.centerx, r.bottom - 34, self.font(18, True), GOLD)

    def _draw_gameover(self, g):
        self._veil(150)
        r = self._box(560, 280)
        title, text = g.state.result
        color = RED if title == "Defeat" else GOLD
        self._label(title, r.centerx, r.top + 54, self.font(40, True, True), color)
        f = self.font(16)
        y = r.top + 100
        for line in wrap(text, f, r.width - 60):
            self._label(line, r.centerx, y, f, TEXT)
            y += 22
        self._label("Final victory points: %+d" % g.state.score(), r.centerx, y + 16, self.font(18, True), TEXT)
        self._label("Press R for a new campaign, Esc to quit", r.centerx, r.bottom - 30, self.font(15), MUTED)
