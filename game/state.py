"""Game rules: movement, zones of control, supply, combat and turn flow."""
import heapq
import random

from . import data, hexgrid
from .data import MARATHA, MUGHAL, other


class Unit:
    _ids = 0

    def __init__(self, tkey, side, pos, name, garrison=False, steps=None):
        Unit._ids += 1
        self.id = Unit._ids
        self.tkey = tkey
        self.t = data.UNIT_TYPES[tkey]
        self.side = side
        self.pos = pos
        self.name = name
        self.garrison = garrison
        self.steps = steps if steps is not None else self.t["steps"]
        self.mp = 0
        self.attacked = False
        self.engaged = False
        self.oos = 0

    @property
    def max_steps(self):
        return self.t["steps"]

    def has(self, trait):
        return trait in self.t["traits"]


class Location:
    def __init__(self, spec):
        self.name = spec["name"]
        self.pos = spec["pos"]
        self.kind = spec["kind"]
        self.owner = spec["owner"]
        self.orig_owner = spec["owner"]
        self.base_supply = spec["supply"]
        self.supply = spec["supply"]
        self.vp = spec["vp"]
        self.capital = spec.get("capital", False)


class GameState:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.turn = 1
        self.side_to_move = MARATHA
        self.locations = {}
        for spec in data.LOCATIONS:
            loc = Location(spec)
            self.locations[loc.pos] = loc
        self.loc_by_name = {loc.name: loc for loc in self.locations.values()}
        self.units = [Unit(*spec) for spec in data.START_UNITS]
        self.log = []
        self.result = None
        self.supply = {MARATHA: set(), MUGHAL: set()}
        self.mughal_lands = set()
        self._validate()
        self.add_log("March 1700: Satara is besieged by the Emperor himself.", MARATHA)
        self.start_side_turn(MARATHA, first=True)

    def _validate(self):
        seen = set()
        for u in self.units:
            assert data.passable(u.pos), "%s placed on impassable hex %s" % (u.name, u.pos)
            assert u.pos not in seen, "two units at %s" % (u.pos,)
            seen.add(u.pos)
        for loc in self.locations.values():
            assert data.passable(loc.pos), "%s on impassable hex" % loc.name

    # ------------------------------------------------------------------ basics
    def add_log(self, text, side=None):
        self.log.append((text, side))
        del self.log[:-60]

    @property
    def monsoon(self):
        return data.is_monsoon(self.turn)

    def unit_at(self, pos):
        for u in self.units:
            if u.pos == pos:
                return u
        return None

    def units_of(self, side):
        return [u for u in self.units if u.side == side]

    def zoc(self, side):
        hexes = set()
        for u in self.units:
            if u.side == side:
                hexes.update(hexgrid.neighbors(*u.pos))
        return hexes

    def max_mp(self, u):
        mp = u.t["mp"]
        if u.oos:
            mp -= 1
        if self.monsoon and u.side == MUGHAL:
            mp -= 1
        return max(1, mp)

    def move_cost(self, u, pos):
        ter = data.terrain(pos)
        cost = ter["move"]
        if cost is None:
            return None
        key = ter["key"]
        loc = self.locations.get(pos)
        if loc is not None and loc.kind != "fort":
            cost = 1
        if u.has("mountain") and key in "hm":
            cost -= 1
        if u.has("heavy") and key in "hmf":
            cost += 1
        if self.monsoon and key == "r":
            cost += 1
        return cost

    # --------------------------------------------------------------- movement
    def reachable(self, u):
        """Return ({hex: cost} of legal destinations, predecessor map for paths)."""
        enemy_zoc = self.zoc(other(u.side))
        occupied = {x.pos: x for x in self.units}
        skirmish = u.has("skirmish")
        full_mp = u.mp >= self.max_mp(u)
        start = u.pos
        best = {start: 0}
        prev = {start: None}
        heap = [(0, start)]
        while heap:
            cost, pos = heapq.heappop(heap)
            if cost > best[pos]:
                continue
            if pos != start and pos in enemy_zoc and not skirmish:
                continue
            for n in hexgrid.neighbors(*pos):
                if not data.passable(n):
                    continue
                o = occupied.get(n)
                if o is not None and o.side != u.side:
                    continue
                step = self.move_cost(u, n)
                if skirmish and n in enemy_zoc:
                    step += 1
                nc = cost + step
                if nc > u.mp:
                    if pos == start and full_mp and u.mp > 0:
                        nc = u.mp
                    else:
                        continue
                if nc < best.get(n, 1e9):
                    best[n] = nc
                    prev[n] = pos
                    heapq.heappush(heap, (nc, n))
        dests = {p: c for p, c in best.items() if p != start and p not in occupied}
        return dests, prev

    @staticmethod
    def path(prev, dest):
        out = [dest]
        while prev.get(out[-1]) is not None:
            out.append(prev[out[-1]])
        return out[::-1]

    def move_unit(self, u, dest, cost):
        enemy_zoc = self.zoc(other(u.side))
        u.pos = dest
        u.mp = max(0, u.mp - cost)
        if dest in enemy_zoc and not u.has("skirmish"):
            u.mp = 0
        captured = self._capture(u)
        self.recompute_supply()
        self.check_end()
        return captured

    def _capture(self, u):
        loc = self.locations.get(u.pos)
        if loc is None or loc.owner == u.side:
            return False
        loc.owner = u.side
        loc.supply = loc.base_supply if loc.orig_owner == u.side else min(loc.base_supply, 3)
        verb = "liberate" if loc.orig_owner == u.side else "capture"
        self.add_log("The %s %s %s!" % (data.SIDE_NAMES[u.side], verb, loc.name), u.side)
        return True

    # ----------------------------------------------------------------- supply
    def compute_supply(self, side, blocking=True):
        """Hexes reachable from `side`'s supply sources. With blocking=False, enemy units and
        zones of control are ignored, which gives the land the side's logistics feed off."""
        enemy_zoc = self.zoc(other(side)) if blocking else set()
        occupied = {u.pos: u for u in self.units} if blocking else {}
        bonus = data.MARATHA_SUPPLY_BONUS if side == MARATHA else 0
        monsoon = self.monsoon
        best = {}
        heap = []
        for loc in self.locations.values():
            if loc.owner != side:
                continue
            o = occupied.get(loc.pos)
            if o is not None and o.side != side:
                continue
            if loc.supply > 0:
                rng = loc.supply + bonus
            elif loc.kind == "fort":
                rng = 0
            else:
                continue
            if rng > best.get(loc.pos, -1):
                best[loc.pos] = rng
                heapq.heappush(heap, (-rng, loc.pos))
        while heap:
            neg, pos = heapq.heappop(heap)
            rng = -neg
            if rng < best.get(pos, -1):
                continue
            for n in hexgrid.neighbors(*pos):
                if not data.passable(n):
                    continue
                o = occupied.get(n)
                if o is not None and o.side != side:
                    continue
                if n in enemy_zoc and o is None:
                    continue
                ter = data.terrain(n)
                cost = ter["supply"] + (1 if monsoon and ter["key"] == "r" else 0)
                nr = rng - cost
                if nr >= 0 and nr > best.get(n, -1):
                    best[n] = nr
                    heapq.heappush(heap, (-nr, n))
        return set(best)

    def recompute_supply(self):
        self.supply[MARATHA] = self.compute_supply(MARATHA)
        self.supply[MUGHAL] = self.compute_supply(MUGHAL)
        self.mughal_lands = self.compute_supply(MUGHAL, blocking=False)

    def in_supply(self, u):
        if u.pos in self.supply[u.side]:
            return True
        return u.has("skirmish") and u.side == MARATHA and u.pos in self.mughal_lands

    # ----------------------------------------------------------------- combat
    def can_attack(self, att, dfn):
        return (att.side != dfn.side and not att.attacked and att.steps > 0
                and hexgrid.distance(att.pos, dfn.pos) == 1)

    @staticmethod
    def _supply_factor(u):
        return (1.0, 0.67, 0.5)[min(u.oos, 2)]

    def combat_preview(self, att, dfn):
        notes = []
        a = att.t["atk"] * att.steps * self._supply_factor(att)
        if att.oos:
            notes.append("Attacker out of supply")
        flank = min(3, sum(1 for u in self.units if u.side == att.side and u is not att
                           and hexgrid.distance(u.pos, dfn.pos) == 1))
        if flank:
            a *= 1 + 0.2 * flank
            notes.append("Flanking support +%d%%" % (20 * flank))
        ter = data.terrain(dfn.pos)
        key = ter["key"]
        loc = self.locations.get(dfn.pos)
        if att.has("shock"):
            if key in "hmf":
                a *= 0.7
                notes.append("Elephants in rough terrain -30%")
            elif loc is None:
                a *= 1.3
                notes.append("Elephant charge +30%")
        if att.has("raider") and dfn.has("heavy"):
            a *= 1.5
            notes.append("Raid on slow column +50%")
        if att.has("siege") and self.monsoon:
            a *= 0.6
            notes.append("Wet powder (monsoon) -40%")

        d = dfn.t["dfn"] * dfn.steps * self._supply_factor(dfn)
        if dfn.oos:
            notes.append("Defender out of supply")
        if ter["defense"] != 1.0:
            d *= ter["defense"]
            notes.append("%s x%g" % (ter["name"], ter["defense"]))
        in_fort = loc is not None and loc.kind == "fort"
        if loc is not None:
            if in_fort:
                mult = 1.25 if att.has("siege") else 2.5
                label = "Fort walls vs siege guns" if att.has("siege") else "Fort walls"
            elif loc.kind == "city":
                mult, label = 1.4, "City"
            else:
                mult, label = 1.2, "Fortified camp"
            d *= mult
            notes.append("%s x%g" % (label, mult))
        if dfn.has("mountain") and key in "hm" and not in_fort:
            d *= 1.3
            notes.append("Mavalas in the hills +30%")

        ratio = a / max(d, 0.1)
        rc = max(0.25, min(4.0, ratio))
        att_loss = 2.0 / rc
        def_loss = 2.0 * rc
        if att.has("siege"):
            att_loss *= 0.3
        evade = dfn.has("skirmish") and ratio >= 1.0 and not in_fort
        if evade:
            def_loss = min(def_loss, 4.0) * 0.35
        return dict(attack=a, defense=d, ratio=ratio, notes=notes, evade=evade, in_fort=in_fort,
                    att_loss=min(att_loss, att.steps), def_loss=min(def_loss, dfn.steps))

    def _roll(self, expected):
        x = expected * self.rng.uniform(0.75, 1.25)
        n = int(x)
        return n + (1 if self.rng.random() < x - n else 0)

    def _retreat_hex(self, dfn, att):
        enemy_zoc = self.zoc(att.side)
        best, best_score = None, -1e9
        for n in hexgrid.neighbors(*dfn.pos):
            if not data.passable(n) or self.unit_at(n) is not None:
                continue
            loc = self.locations.get(n)
            if loc is not None and loc.owner != dfn.side:
                continue
            score = hexgrid.distance(n, att.pos) * 3 + data.terrain(n)["defense"]
            if n in enemy_zoc:
                score -= 4
            if n in self.supply[dfn.side]:
                score += 2
            if score > best_score:
                best, best_score = n, score
        return best

    def resolve_combat(self, att, dfn):
        p = self.combat_preview(att, dfn)
        la = min(att.steps, self._roll(p["att_loss"]))
        ld = min(dfn.steps, self._roll(p["def_loss"]))
        att.steps -= la
        dfn.steps -= ld
        att.attacked = att.engaged = dfn.engaged = True
        att.mp = max(0, att.mp - 1) if att.has("skirmish") else 0
        def_pos = dfn.pos
        res = dict(att=att, dfn=dfn, att_loss=la, def_loss=ld, ratio=p["ratio"], def_pos=def_pos,
                   att_pos=att.pos, retreat=None, evaded=False, advanced=False,
                   att_dead=False, def_dead=False)
        self.add_log("%s attacks %s at %.1f:1 (losses %d / %d)"
                     % (att.name, dfn.name, p["ratio"], la, ld), att.side)

        if dfn.steps <= 0:
            self.units.remove(dfn)
            res["def_dead"] = True
            self.add_log("%s is destroyed!" % dfn.name, att.side)
        elif att.steps > 0 and (p["evade"] or (not p["in_fort"] and ld >= 3 and p["ratio"] >= 1.5)):
            h = self._retreat_hex(dfn, att)
            if h is not None:
                dfn.pos = h
                res["retreat"] = h
                res["evaded"] = p["evade"]
                self.add_log("%s %s." % (dfn.name, "melts away into the countryside" if p["evade"]
                                         else "falls back"), dfn.side)
            elif not p["evade"]:
                dfn.steps -= 1
                self.add_log("%s is cut off and suffers extra losses." % dfn.name, att.side)
                if dfn.steps <= 0:
                    self.units.remove(dfn)
                    res["def_dead"] = True
                    self.add_log("%s is destroyed!" % dfn.name, att.side)

        if att.steps <= 0:
            self.units.remove(att)
            res["att_dead"] = True
            self.add_log("%s is destroyed in the assault." % att.name, dfn.side)
        elif ((res["def_dead"] or res["retreat"]) and not att.has("siege") and not att.garrison
              and att.pos not in self.locations and self.unit_at(def_pos) is None):
            att.pos = def_pos
            res["advanced"] = True
            self._capture(att)

        self.recompute_supply()
        self.check_end()
        return res

    # -------------------------------------------------------------- turn flow
    def start_side_turn(self, side, first=False):
        self.side_to_move = side
        self.recompute_supply()
        for u in list(self.units):
            if u.side != side:
                continue
            if not first:
                if self.in_supply(u):
                    if u.oos:
                        self.add_log("%s is back in supply." % u.name, side)
                    u.oos = 0
                    if not u.engaged and u.steps < u.max_steps:
                        u.steps += 1
                else:
                    u.oos += 1
                    if u.oos == 1:
                        self.add_log("%s is out of supply!" % u.name, other(side))
                    else:
                        u.steps -= 1
                        if u.steps <= 0:
                            self.units.remove(u)
                            self.add_log("%s has starved and dispersed." % u.name, other(side))
                            continue
            u.engaged = False
            u.attacked = False
            u.mp = self.max_mp(u)
        self._reinforce(side)
        self.recompute_supply()

    def _reinforce(self, side):
        for tkey, s, places, name in data.REINFORCEMENTS.get(self.turn, []):
            if s != side:
                continue
            pos = self._arrival_hex(side, places)
            if pos is None:
                self.add_log("%s could not reach the front." % name, side)
                continue
            u = Unit(tkey, side, pos, name)
            u.mp = self.max_mp(u)
            self.units.append(u)
            self.add_log("Reinforcements: %s arrive near %s." % (name, self._nearest_name(pos)), side)

    def _arrival_hex(self, side, places):
        enemy_zoc = self.zoc(other(side))
        for name in places:
            loc = self.loc_by_name.get(name)
            if loc is None or loc.owner != side:
                continue
            if self.unit_at(loc.pos) is None:
                return loc.pos
            for n in hexgrid.neighbors(*loc.pos):
                if (data.passable(n) and self.unit_at(n) is None and n not in enemy_zoc
                        and n not in self.locations):
                    return n
        return None

    def _nearest_name(self, pos):
        return min(self.locations.values(), key=lambda l: hexgrid.distance(l.pos, pos)).name

    def end_maratha_turn(self):
        self.start_side_turn(MUGHAL)

    def end_mughal_turn(self):
        self.check_end(final=self.turn >= data.MAX_TURNS)
        if self.result:
            return
        self.turn += 1
        if data.turn_month(self.turn) == 6:
            self.add_log("The monsoon breaks over the Deccan. Rivers swell.", MARATHA)
        elif data.turn_month(self.turn) == 10:
            self.add_log("The monsoon ends. Roads dry out.", MUGHAL)
        self.start_side_turn(MARATHA)
        self.check_end()

    # ----------------------------------------------------------------- scoring
    def score(self):
        total = 0
        for loc in self.locations.values():
            if loc.orig_owner == MUGHAL and loc.owner == MARATHA:
                total += loc.vp
            elif loc.orig_owner == MARATHA and loc.owner == MUGHAL:
                total -= loc.vp
        return total

    def check_end(self, final=False):
        if self.result:
            return
        locs = list(self.locations.values())
        if not any(l.owner == MARATHA for l in locs):
            self.result = ("Defeat", "Every Maratha stronghold has fallen to the Mughals.")
        elif not self.units_of(MARATHA):
            self.result = ("Defeat", "The Maratha armies have been destroyed.")
        elif all(l.owner == MARATHA for l in locs if l.orig_owner == MUGHAL):
            self.result = ("Decisive Victory", "Every Mughal stronghold in the Deccan has fallen.")
        elif final:
            score = self.score()
            level = data.victory_level(score)
            if level == "Defeat":
                text = "The Mughals still dominate the Deccan. Swarajya hangs by a thread."
            else:
                text = "Aurangzeb's Deccan war is bleeding the empire dry. Swarajya endures."
            self.result = (level, text)
