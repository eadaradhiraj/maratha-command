"""Scenario data: the Deccan map, terrain, unit types and the 1700 campaign."""
from . import hexgrid

MARATHA = "maratha"
MUGHAL = "mughal"

SIDE_NAMES = {MARATHA: "Marathas", MUGHAL: "Mughals"}
SIDE_COLORS = {MARATHA: (233, 128, 32), MUGHAL: (38, 122, 74)}
SIDE_DARK = {MARATHA: (110, 52, 8), MUGHAL: (12, 56, 30)}


def other(side):
    return MUGHAL if side == MARATHA else MARATHA


TERRAIN = {
    "~": dict(name="Sea", move=None, supply=None, defense=1.0, color=(58, 98, 140)),
    ".": dict(name="Plains", move=1, supply=1, defense=1.0, color=(201, 184, 128)),
    "f": dict(name="Forest", move=2, supply=2, defense=1.3, color=(150, 160, 98)),
    "h": dict(name="Hills", move=2, supply=2, defense=1.5, color=(176, 150, 106)),
    "m": dict(name="Sahyadri Ghats", move=3, supply=3, defense=1.8, color=(146, 124, 96)),
    "r": dict(name="River", move=2, supply=1, defense=1.25, color=(186, 184, 126)),
}
for _k, _t in TERRAIN.items():
    _t["key"] = _k

COLS = 26
_BASE_ROWS = [
    "~~.ff.......hh...fff..fff.",
    "~~..ff..........ff...fff..",
    "~~.hff.......hhh.....ffff.",
    "~~hh.f......hhhhh.....fff.",
    "~~hmh........hh........ff.",
    "~~hmh....................f",
    "~~hmh.....f..........f....",
    "~~hmmh............ff......",
    "~~hmmh....................",
    "~~hmmh.......hhh..........",
    "~~hhmh.....hhhhh.....ff...",
    "~~hhmh.........hh...fff...",
    "~~~hmh....................",
    "~~~hmmh...........ff......",
    "~~~hmh.....ff.............",
    "~~~hmh......f.......hh....",
    "~~~hmhh.............hh....",
    "~~~hmh....ff..............",
]
ROWS = len(_BASE_ROWS)
GRID = [list(row.ljust(COLS, ".")[:COLS]) for row in _BASE_ROWS]

_RIVER_WAYPOINTS = {
    "Tapti": [(1, 1), (15, 1), (22, -1)],
    "Godavari": [(5, 5), (11, 7), (18, 8), (26, 10)],
    "Bhima": [(5, 8), (12, 12), (18, 18)],
    "Krishna": [(5, 12), (8, 15), (10, 18)],
}


def _polyline(points):
    path = []
    for a, b in zip(points, points[1:]):
        seg = hexgrid.hex_line(a, b)
        path.extend(seg[1:] if path else seg)
    return path


def in_bounds(pos):
    return 0 <= pos[0] < COLS and 0 <= pos[1] < ROWS


RIVER_PATHS = {name: _polyline(pts) for name, pts in _RIVER_WAYPOINTS.items()}


def terrain_char(pos):
    return GRID[pos[1]][pos[0]]


def terrain(pos):
    return TERRAIN[GRID[pos[1]][pos[0]]]


def passable(pos):
    return in_bounds(pos) and GRID[pos[1]][pos[0]] != "~"


LOCATIONS = [
    dict(name="Satara", pos=(6, 13), kind="fort", owner=MARATHA, supply=4, vp=3, capital=True),
    dict(name="Sinhagad", pos=(5, 10), kind="fort", owner=MARATHA, supply=3, vp=1),
    dict(name="Rajgad", pos=(4, 12), kind="fort", owner=MARATHA, supply=3, vp=1),
    dict(name="Panhala", pos=(6, 16), kind="fort", owner=MARATHA, supply=4, vp=2),
    dict(name="Vishalgad", pos=(4, 15), kind="fort", owner=MARATHA, supply=3, vp=1),
    dict(name="Raigad", pos=(3, 10), kind="fort", owner=MUGHAL, supply=0, vp=2),
    dict(name="Pune", pos=(6, 9), kind="city", owner=MUGHAL, supply=0, vp=1),
    dict(name="Ahmednagar", pos=(9, 8), kind="fort", owner=MUGHAL, supply=0, vp=2),
    dict(name="Aurangabad", pos=(11, 5), kind="city", owner=MUGHAL, supply=7, vp=3),
    dict(name="Burhanpur", pos=(15, 1), kind="city", owner=MUGHAL, supply=6, vp=2),
    dict(name="Surat", pos=(3, 1), kind="city", owner=MUGHAL, supply=4, vp=2),
    dict(name="Bijapur", pos=(13, 16), kind="city", owner=MUGHAL, supply=3, vp=2),
    dict(name="Hyderabad", pos=(24, 14), kind="city", owner=MUGHAL, supply=4, vp=2),
    dict(name="Brahmapuri", pos=(12, 13), kind="camp", owner=MUGHAL, supply=6, vp=2),
]

_LOCATION_HEXES = {loc["pos"] for loc in LOCATIONS}
for _path in RIVER_PATHS.values():
    for _c, _r in _path:
        if in_bounds((_c, _r)) and GRID[_r][_c] != "~" and (_c, _r) not in _LOCATION_HEXES:
            GRID[_r][_c] = "r"

UNIT_TYPES = {
    "m_cav": dict(name="Maratha Light Horse", short="Light Horse", mp=6, atk=4, dfn=3, steps=8,
                  traits=("skirmish", "raider"), symbol="cav"),
    "m_inf": dict(name="Mavala Infantry", short="Mavalas", mp=4, atk=3, dfn=5, steps=8,
                  traits=("mountain",), symbol="mtn_inf"),
    "g_cav": dict(name="Mughal Heavy Cavalry", short="Heavy Cavalry", mp=4, atk=6, dfn=4, steps=10,
                  traits=(), symbol="cav"),
    "g_inf": dict(name="Mughal Musketeers", short="Musketeers", mp=3, atk=4, dfn=5, steps=10,
                  traits=(), symbol="inf"),
    "g_art": dict(name="Mughal Siege Train", short="Siege Guns", mp=2, atk=6, dfn=2, steps=6,
                  traits=("siege", "heavy"), symbol="art"),
    "g_ele": dict(name="Mughal War Elephants", short="Elephants", mp=3, atk=7, dfn=4, steps=6,
                  traits=("shock", "heavy"), symbol="ele"),
}

TRAIT_TEXT = {
    "skirmish": "Ganimi kava: ignores enemy zones of control, can move after attacking, evades strong attacks "
                "and lives off the land inside enemy supply.",
    "raider": "+50% attack against siege guns and elephants.",
    "mountain": "Moves quickly through hills and ghats, +30% defence there.",
    "siege": "Halves the fort bonus and takes few losses when bombarding. Weak in the monsoon.",
    "heavy": "Slow in hills, forest and ghats.",
    "shock": "+30% attack on open ground, -30% in rough terrain.",
}

_FORTS = ["Satara", "Panhala", "Vishalgad", "Rajgad", "Sinhagad"]

# (unit type, side, position, name, is static garrison, starting steps)
START_UNITS = [
    ("m_inf", MARATHA, (6, 13), "Prayagji Prabhu", False, None),
    ("m_inf", MARATHA, (5, 10), "Sinhagad Mavalas", False, 6),
    ("m_inf", MARATHA, (4, 12), "Rajgad Mavalas", False, 6),
    ("m_inf", MARATHA, (6, 16), "Parshuram Trimbak", False, None),
    ("m_inf", MARATHA, (4, 15), "Vishalgad Mavalas", False, 6),
    ("m_cav", MARATHA, (9, 15), "Dhanaji Jadhav", False, None),
    ("m_cav", MARATHA, (8, 16), "Haibatrao Nimbalkar", False, None),
    ("m_cav", MARATHA, (8, 6), "Nemaji Shinde", False, None),
    ("m_cav", MARATHA, (17, 12), "Parsoji Bhonsle", False, None),
    ("m_cav", MARATHA, (6, 3), "Khanderao Dabhade", False, None),

    ("g_inf", MUGHAL, (7, 13), "Aurangzeb's Army", False, None),
    ("g_art", MUGHAL, (7, 12), "Imperial Siege Train", False, None),
    ("g_cav", MUGHAL, (6, 12), "Prince Azam Shah", False, None),
    ("g_ele", MUGHAL, (7, 14), "Imperial Elephants", False, None),
    ("g_cav", MUGHAL, (8, 10), "Zulfiqar Khan", False, None),
    ("g_cav", MUGHAL, (13, 11), "Bidar Bakht", False, None),
    ("g_cav", MUGHAL, (14, 6), "Firuz Jang", False, None),
    ("g_inf", MUGHAL, (3, 10), "Raigad Qiladar", True, 6),
    ("g_inf", MUGHAL, (6, 9), "Pune Thanedar", True, 5),
    ("g_inf", MUGHAL, (9, 8), "Ahmednagar Garrison", True, 7),
    ("g_inf", MUGHAL, (11, 5), "Aurangabad Garrison", True, 8),
    ("g_inf", MUGHAL, (15, 1), "Burhanpur Garrison", True, 7),
    ("g_inf", MUGHAL, (3, 1), "Surat Garrison", True, 6),
    ("g_inf", MUGHAL, (13, 16), "Bijapur Garrison", True, 7),
    ("g_inf", MUGHAL, (24, 14), "Golconda Garrison", True, 7),
    ("g_inf", MUGHAL, (12, 13), "Camp Guard", True, 6),
]

# turn -> [(unit type, side, candidate locations in order of preference, name)]
REINFORCEMENTS = {
    3: [("g_cav", MUGHAL, ["Aurangabad", "Burhanpur"], "Mansabdar Horse")],
    4: [("m_cav", MARATHA, _FORTS, "Shankraji's Horse")],
    6: [("g_inf", MUGHAL, ["Brahmapuri", "Aurangabad"], "Imperial Reserve")],
    7: [("m_inf", MARATHA, ["Panhala", "Vishalgad", "Satara", "Rajgad", "Sinhagad"], "Tarabai's Hashams")],
    8: [("g_art", MUGHAL, ["Brahmapuri", "Aurangabad", "Burhanpur"], "Second Siege Train")],
    9: [("m_cav", MARATHA, _FORTS, "Ghorpade Horse")],
    11: [("g_cav", MUGHAL, ["Aurangabad", "Burhanpur"], "Rajput Contingent")],
    12: [("m_cav", MARATHA, _FORTS, "Dabhade Horse")],
    13: [("g_ele", MUGHAL, ["Brahmapuri", "Aurangabad", "Bijapur"], "Second Elephant Corps")],
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
START_YEAR, START_MONTH = 1700, 3
MAX_TURNS = 16
MARATHA_SUPPLY_BONUS = 2


def turn_month(turn):
    return (START_MONTH - 1 + turn - 1) % 12 + 1


def turn_date(turn):
    m = START_MONTH - 1 + turn - 1
    return MONTHS[m % 12], START_YEAR + m // 12


def is_monsoon(turn):
    return turn_month(turn) in (6, 7, 8, 9)


VICTORY_LEVELS = [(9, "Decisive Victory"), (5, "Victory"), (2, "Marginal Victory")]


def victory_level(score):
    for threshold, label in VICTORY_LEVELS:
        if score >= threshold:
            return label
    return "Defeat"


BRIEFING = [
    "March 1700. Chhatrapati Rajaram has died at Sinhagad. Emperor Aurangzeb, past eighty, has brought "
    "the full weight of the Mughal Empire into the Deccan, and his siege guns are pounding Satara.",
    "Maharani Tarabai now rules as regent for her young son. She has no army that could win a pitched "
    "battle against the imperial host, but she has the Maratha light horse and the hill forts of the "
    "Sahyadri. Use ganimi kava, the guerrilla way: raid, cut supply lines, and strike where the enemy is weak.",
    "Capture Mughal cities, forts and camps for victory points while holding your own forts. Units cut off "
    "from supply weaken and wither. Mughal columns are slow, and slower still in the monsoon (June to "
    "September). The campaign ends after 16 turns (one turn is one month).",
    "Score 9+ points for a Decisive Victory, 5+ for a Victory, 2+ for a Marginal Victory.",
]
