"""Pointy-top hex grid helpers using "odd-r" offset coordinates (col, row)."""
import math

SQRT3 = math.sqrt(3)

_EVEN_DIRS = ((1, 0), (0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1))
_ODD_DIRS = ((1, 0), (1, -1), (0, -1), (-1, 0), (0, 1), (1, 1))


def offset_to_cube(col, row):
    x = col - (row - (row & 1)) // 2
    z = row
    return x, -x - z, z


def cube_to_offset(x, y, z):
    return x + (z - (z & 1)) // 2, z


def cube_round(x, y, z):
    rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(ry), int(rz)


def distance(a, b):
    ax, ay, az = offset_to_cube(*a)
    bx, by, bz = offset_to_cube(*b)
    return max(abs(ax - bx), abs(ay - by), abs(az - bz))


def neighbors(col, row):
    dirs = _ODD_DIRS if row & 1 else _EVEN_DIRS
    return [(col + dc, row + dr) for dc, dr in dirs]


def hex_line(a, b):
    n = distance(a, b)
    ax, ay, az = offset_to_cube(*a)
    bx, by, bz = offset_to_cube(*b)
    out = []
    for i in range(n + 1):
        t = i / n if n else 0.0
        out.append(cube_to_offset(*cube_round(
            ax + (bx - ax) * t + 1e-6,
            ay + (by - ay) * t + 1e-6,
            az + (bz - az) * t - 2e-6,
        )))
    return out


def hex_to_pixel(col, row, size):
    return size * SQRT3 * (col + 0.5 * (row & 1)), size * 1.5 * row


def pixel_to_hex(x, y, size):
    q = (SQRT3 / 3 * x - y / 3) / size
    r = (2 / 3 * y) / size
    return cube_to_offset(*cube_round(q, -q - r, r))


def hex_corners(cx, cy, size):
    return [
        (cx + size * math.cos(math.radians(60 * i - 30)),
         cy + size * math.sin(math.radians(60 * i - 30)))
        for i in range(6)
    ]
