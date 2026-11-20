"""Maratha Command: an operational wargame of the Mughal-Maratha War, 1700-1701."""
import time

import pygame

from game import ai, data, hexgrid
from game.data import MARATHA
from game.render import Renderer
from game.state import GameState

PAN_SPEED = 700


class Game:
    def __init__(self, screen):
        self.renderer = Renderer(screen)
        self.running = True
        self.supply_mode = 0
        self.new_game()

    def new_game(self):
        self.state = GameState()
        self.mode = "briefing"
        self.selected = None
        self.reach, self.prev, self.targets = {}, {}, []
        self.hover = None
        self.anim = None
        self.floaters = []
        self.ai_gen = None
        self.ai_wait = 0.0
        self.undo = []
        self.drag = None
        self.renderer.center_on((8, 11))

    # ------------------------------------------------------------ selection
    def select(self, u):
        self.selected = u
        self.refresh_selection()

    def deselect(self):
        self.selected = None
        self.reach, self.prev, self.targets = {}, {}, []

    def refresh_selection(self):
        u = self.selected
        if u is None or u not in self.state.units:
            self.deselect()
            return
        if u.mp > 0:
            self.reach, self.prev = self.state.reachable(u)
        else:
            self.reach, self.prev = {}, {}
        self.targets = []
        if not u.attacked:
            for n in hexgrid.neighbors(*u.pos):
                e = self.state.unit_at(n)
                if e is not None and e.side != u.side:
                    self.targets.append(e)

    def next_unit(self):
        units = [u for u in self.state.units_of(MARATHA) if u.mp > 0 or not u.attacked]
        if not units:
            return
        if self.selected in units:
            u = units[(units.index(self.selected) + 1) % len(units)]
        else:
            u = units[0]
        self.select(u)
        self.renderer.center_on(u.pos)

    # --------------------------------------------------------------- actions
    def start_anim(self, u, path, per_hex):
        if len(path) > 1:
            self.anim = dict(unit=u, path=path, t0=time.time(), dur=per_hex * (len(path) - 1))

    def add_floater(self, pos, text, color):
        self.floaters.append(dict(pos=pos, text=text, color=color, t0=time.time(), dur=1.2))

    def show_combat(self, res):
        if res["def_loss"]:
            self.add_floater(res["def_pos"], "-%d" % res["def_loss"], (255, 120, 90))
        if res["att_loss"]:
            self.add_floater(res["att_pos"], "-%d" % res["att_loss"], (255, 200, 120))
        if res["evaded"]:
            self.add_floater(res["retreat"], "evaded", (255, 240, 200))

    def player_move(self, dest):
        u = self.selected
        path = self.state.path(self.prev, dest)
        snapshot = (u, u.pos, u.mp)
        if self.state.move_unit(u, dest, self.reach[dest]):
            self.undo.clear()
        else:
            self.undo.append(snapshot)
        self.start_anim(u, path, 0.06)
        self.refresh_selection()

    def player_attack(self, target):
        res = self.state.resolve_combat(self.selected, target)
        self.undo.clear()
        self.show_combat(res)
        self.refresh_selection()
        self.after_action()

    def undo_move(self):
        if self.mode != "player" or not self.undo or self.anim:
            return
        u, pos, mp = self.undo.pop()
        if u in self.state.units and self.state.unit_at(pos) is None:
            u.pos, u.mp = pos, mp
            self.state.recompute_supply()
            self.select(u)

    def end_turn(self):
        if self.mode != "player" or self.anim:
            return
        self.deselect()
        self.undo.clear()
        self.state.end_maratha_turn()
        self.mode = "ai"
        self.ai_gen = ai.mughal_turn(self.state)
        self.ai_wait = time.time() + 0.3

    def after_action(self):
        if self.state.result:
            self.mode = "gameover"
            self.deselect()

    def run_ai_step(self):
        try:
            action = next(self.ai_gen)
        except StopIteration:
            self.state.end_mughal_turn()
            self.ai_gen = None
            self.mode = "gameover" if self.state.result else "player"
            return
        kind, u, arg = action
        if kind == "move":
            dests, prev = self.state.reachable(u)
            if arg not in dests:
                return
            path = self.state.path(prev, arg)
            self.state.move_unit(u, arg, dests[arg])
            if not self.renderer.is_visible(arg, -60):
                self.renderer.center_on(arg)
            self.start_anim(u, path, 0.09)
            self.ai_wait = time.time() + 0.09 * (len(path) - 1) + 0.08
        elif kind == "attack":
            if u in self.state.units and arg in self.state.units and self.state.can_attack(u, arg):
                if not self.renderer.is_visible(arg.pos, -60):
                    self.renderer.center_on(arg.pos)
                self.show_combat(self.state.resolve_combat(u, arg))
                self.ai_wait = time.time() + 0.7
        if self.state.result:
            self.mode = "gameover"

    # ---------------------------------------------------------------- input
    def handle(self, ev):
        r = self.renderer
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.KEYDOWN:
            self.on_key(ev.key)
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:
                self.on_click(ev.pos)
            elif ev.button == 3:
                self.drag = (ev.pos, tuple(r.cam), False)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 3:
            if self.drag is not None and not self.drag[2] and self.mode == "player":
                self.deselect()
            self.drag = None
        elif ev.type == pygame.MOUSEMOTION:
            if self.drag is not None:
                (sx, sy), (cx, cy), _ = self.drag
                dx, dy = ev.pos[0] - sx, ev.pos[1] - sy
                if abs(dx) + abs(dy) > 4:
                    self.drag = ((sx, sy), (cx, cy), True)
                r.cam = [cx - dx, cy - dy]
                r.clamp_cam()
            self.update_hover(ev.pos)
        elif ev.type == pygame.MOUSEWHEEL and ev.y:
            mx, my = pygame.mouse.get_pos()
            if mx < r.map_w:
                r.zoom(1 if ev.y > 0 else -1, mx, my)
                self.update_hover((mx, my))

    def update_hover(self, pos):
        r = self.renderer
        h = r.screen_to_hex(*pos) if pos[0] < r.map_w else None
        self.hover = h if h is not None and data.in_bounds(h) else None

    def on_key(self, key):
        if self.mode == "briefing":
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.mode = "player"
            elif key == pygame.K_ESCAPE:
                self.running = False
            return
        if key == pygame.K_ESCAPE:
            if self.mode == "gameover":
                self.running = False
            else:
                self.deselect()
        elif key == pygame.K_r and self.mode == "gameover":
            self.new_game()
        elif key == pygame.K_s:
            self.supply_mode = (self.supply_mode + 1) % 3
        elif self.mode != "player":
            return
        elif key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.end_turn()
        elif key == pygame.K_n:
            self.next_unit()
        elif key == pygame.K_z:
            self.undo_move()
        elif key == pygame.K_c and self.selected is not None:
            self.renderer.center_on(self.selected.pos)

    def on_click(self, pos):
        r = self.renderer
        if self.mode == "briefing":
            self.mode = "player"
            return
        for key, rect in r.buttons.items():
            if rect.collidepoint(pos):
                if key == "supply":
                    self.supply_mode = (self.supply_mode + 1) % 3
                elif key == "end":
                    self.end_turn()
                elif key == "next" and self.mode == "player":
                    self.next_unit()
                return
        if pos[0] >= r.map_w or self.mode != "player" or self.anim is not None:
            return
        h = r.screen_to_hex(*pos)
        if not data.in_bounds(h):
            self.deselect()
            return
        u = self.state.unit_at(h)
        if self.selected is not None and u is not None and u in self.targets:
            self.player_attack(u)
        elif u is not None and u.side == MARATHA:
            self.select(u)
        elif self.selected is not None and h in self.reach:
            self.player_move(h)
        else:
            self.deselect()

    # --------------------------------------------------------------- update
    def update(self, dt):
        now = time.time()
        keys = pygame.key.get_pressed()
        r = self.renderer
        dx = (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * PAN_SPEED * dt
        dy = (keys[pygame.K_DOWN] - keys[pygame.K_UP]) * PAN_SPEED * dt
        if dx or dy:
            r.cam[0] += dx
            r.cam[1] += dy
            r.clamp_cam()
        if self.anim is not None and now >= self.anim["t0"] + self.anim["dur"]:
            self.anim = None
            self.after_action()
        self.floaters = [f for f in self.floaters if now - f["t0"] < f["dur"]]
        if self.mode == "ai" and self.anim is None and now >= self.ai_wait:
            self.run_ai_step()


def main():
    pygame.init()
    info = pygame.display.Info()
    size = (min(1280, info.current_w - 40), min(800, info.current_h - 80))
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Maratha Command - The Deccan War, 1700")
    game = Game(screen)
    clock = pygame.time.Clock()
    while game.running:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            game.handle(ev)
        game.update(dt)
        game.renderer.draw(game)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
