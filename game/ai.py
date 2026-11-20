"""Mughal AI. `mughal_turn` is a generator yielding actions for the UI to execute one at a time."""
from . import data, hexgrid
from .data import MARATHA, MUGHAL

ATTACK_THRESHOLD = {"g_cav": 0.9, "g_ele": 0.9, "g_inf": 1.1, "g_art": 0.5}
GARRISON_THRESHOLD = 1.6
SIEGE_TYPES = ("g_inf", "g_art", "g_ele")


def mughal_turn(state):
    claimed = {}
    enemies = state.units_of(MARATHA)

    def nearest_enemy(u):
        return min((hexgrid.distance(u.pos, e.pos) for e in enemies), default=99)

    movers = sorted((u for u in state.units_of(MUGHAL) if not u.garrison), key=nearest_enemy)
    for u in movers:
        if u not in state.units or u.mp <= 0:
            continue
        goal = _pick_goal(state, u, claimed)
        if goal is None:
            continue
        claimed[goal] = claimed.get(goal, 0) + 1
        dest = _pick_destination(state, u, goal)
        if dest != u.pos:
            yield ("move", u, dest)

    while True:
        best = None
        for u in state.units_of(MUGHAL):
            if u.attacked:
                continue
            threshold = GARRISON_THRESHOLD if u.garrison else ATTACK_THRESHOLD[u.tkey]
            for n in hexgrid.neighbors(*u.pos):
                e = state.unit_at(n)
                if e is None or e.side != MARATHA:
                    continue
                p = state.combat_preview(u, e)
                if p["ratio"] < threshold:
                    continue
                value = p["def_loss"] - 0.8 * p["att_loss"] + (2 if n in state.locations else 0)
                if best is None or value > best[0]:
                    best = (value, u, e)
        if best is None:
            break
        yield ("attack", best[1], best[2])


def _pick_goal(state, u, claimed):
    enemies = state.units_of(MARATHA)
    if u.steps <= u.max_steps * 0.3:
        bases = [l.pos for l in state.locations.values() if l.owner == MUGHAL and l.supply > 0]
        if bases:
            return min(bases, key=lambda p: hexgrid.distance(u.pos, p))

    siege = u.tkey in SIEGE_TYPES
    cands = []
    for loc in state.locations.values():
        d = hexgrid.distance(u.pos, loc.pos)
        n_claimed = claimed.get(loc.pos, 0)
        if loc.owner == MUGHAL:
            threatened = (state.unit_at(loc.pos) is None
                          and any(hexgrid.distance(e.pos, loc.pos) <= 3 for e in enemies))
            if threatened and d <= 8:
                cands.append((d - 3 + 3 * n_claimed, loc.pos))
        elif loc.orig_owner == MUGHAL and d <= 10:
            cands.append((d - 3 + 2 * n_claimed, loc.pos))
        elif siege:
            cands.append((d + 3 * max(0, n_claimed - 3), loc.pos))
        else:
            cands.append((d + 4 + 2 * n_claimed, loc.pos))
    if not siege:
        for e in enemies:
            loc = state.locations.get(e.pos)
            if loc is not None and loc.kind == "fort":
                continue
            cands.append((hexgrid.distance(u.pos, e.pos) + 2 * claimed.get(e.pos, 0), e.pos))
    if not cands:
        return None
    return min(cands)[1]


def _pick_destination(state, u, goal):
    dests, _ = state.reachable(u)
    supply = state.supply[MUGHAL]
    raiders = [e for e in state.units_of(MARATHA) if e.has("raider")]
    threshold = ATTACK_THRESHOLD[u.tkey]
    home = u.pos
    best, best_score = home, -1e9
    for h in list(dests) + [home]:
        score = -3.0 * hexgrid.distance(h, goal)
        score += 2.0 * (data.terrain(h)["defense"] - 1.0)
        if h not in supply:
            score -= 4
        loc = state.locations.get(h)
        if loc is not None and loc.owner == MARATHA:
            score += 25
        u.pos = h
        for n in hexgrid.neighbors(*h):
            e = state.unit_at(n)
            if e is None or e.side != MARATHA:
                continue
            p = state.combat_preview(u, e)
            if p["ratio"] >= threshold:
                score += 3 + min(p["ratio"], 3)
            elif u.tkey == "g_cav":
                score -= 1.5
        u.pos = home
        if u.has("siege"):
            score -= 2 * sum(1 for e in raiders if hexgrid.distance(e.pos, h) <= 2)
        if h == home:
            score += 0.3
        if score > best_score:
            best, best_score = h, score
    return best
