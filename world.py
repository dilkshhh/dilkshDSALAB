"""Arena model: 1 m column grid built from v2/world.json + v2/terrain.i16.

The match engine represents the world as a heightmap of 1 m columns plus
"overhang" intervals for bridges.  A column is blocked for a mech standing at
z when its solid top is above z + step_up, or when an overhang intersects the
mech's body.  Using the same representation (instead of a coarse 2 m bilinear
approximation) is what keeps us from walking into a slope the engine refuses
to climb and oscillating there forever.

Everything expensive is built once in hello (20 s budget).  Per-decision
queries are a handful of indexed array lookups.
"""
from __future__ import annotations

import json
import math
import os
import sys
from array import array

TAU = math.tau
NAN = float("nan")


def _spans(ring, y):
    """Horizontal inside-spans of a flat polygon ring at height y (scanline fill)."""
    n = len(ring) // 2
    xs = []
    for k in range(n):
        k2 = (k + 1) % n
        x1, y1 = ring[2 * k], ring[2 * k + 1]
        x2, y2 = ring[2 * k2], ring[2 * k2 + 1]
        if (y1 <= y < y2) or (y2 <= y < y1):
            d = y2 - y1
            xs.append(x1 + (y - y1) * (x2 - x1) / d)
    xs.sort()
    return [(xs[m], xs[m + 1]) for m in range(0, len(xs) - 1, 2)]


class World:
    def __init__(self, map_dir, cell=1.0, nav_cell=8.0, load_trees=True, cfg=None):
        self.map_dir = map_dir
        with open(os.path.join(map_dir, "v2", "world.json"), "r", encoding="utf-8") as f:
            w = json.load(f)
        self.w = w
        cfg = cfg or {}
        mech = cfg.get("mech", {}) or {}
        cubes = cfg.get("cubes", {}) or {}
        rules = w.get("rules", {}) or {}
        self.radius = float(mech.get("radius", 2.5))
        self.height = float(mech.get("height", 9.0))
        self.step_up = float(mech.get("step_up", 1.2))
        self.eye_height = float(mech.get("eye_height", 8.0))
        self.muzzle_height = float(mech.get("muzzle_height", 7.0))
        self.front_arc_deg = float(mech.get("front_arc_deg", 180.0))
        self.rear_mult = float(mech.get("rear_mult", 1.5))
        self.size_per_cube = float(cubes.get("size_per_cube", 0.05))
        self.canopy_density = float(rules.get("canopyDensity", 0.35))
        self.canopy_block_t = float(rules.get("canopyBlockT", 0.25))
        slope_deg = float(mech.get("max_slope_deg", rules.get("maxSlopeDeg", 50.0)))
        self.max_slope = math.tan(math.radians(slope_deg))
        t = w["terrain"]
        self.minx, self.miny = float(t["minX"]), float(t["minY"])
        self.tstep, self.tscale = float(t.get("step", 1.0)), float(t.get("scale", 0.01))
        self.nx, self.ny = int(t["nx"]), int(t["ny"])
        self.maxx = self.minx + self.nx - 1
        self.maxy = self.miny + self.ny - 1
        with open(os.path.join(map_dir, "v2", "terrain.i16"), "rb") as f:
            raw = f.read()
        terr = array("h")
        terr.frombytes(raw[: self.nx * self.ny * 2])
        if sys.byteorder != "little":
            terr.byteswap()
        n = self.nx * self.ny
        self.g = array("f", [0.0]) * n          # terrain height
        self.top = array("f", [0.0]) * n        # highest solid top standing on the ground
        self.ohb = array("f", [NAN]) * n        # overhang base (NaN = none)
        self.oht = array("f", [NAN]) * n        # overhang top
        sc = self.tscale
        for k in range(n):
            g = terr[k] * sc
            self.g[k] = g
            self.top[k] = g

        self._build_prisms(w.get("prisms") or [])
        self._build_trees(w.get("trees") if load_trees else None)

        self.cell = float(cell)
        # ---- coarse navigation grid -----------------------------------------
        self.nav_cell = float(nav_cell)
        self.nnx = int((self.maxx - self.minx) / self.nav_cell) + 2
        self.nny = int((self.maxy - self.miny) / self.nav_cell) + 2
        self.nav_blocked = bytearray(self.nnx * self.nny)
        self.nav_z = [0.0] * (self.nnx * self.nny)
        self._build_nav()
        self.ready = True

    # ------------------------------------------------------------------ build
    def _build_prisms(self, prisms):
        nx, ny, minx, miny = self.nx, self.ny, self.minx, self.miny
        g, top, ohb, oht = self.g, self.top, self.ohb, self.oht
        for p in prisms:
            ring = p.get("ring") or []
            if len(ring) < 6:
                continue
            holes = p.get("holes") or []
            if holes and isinstance(holes[0], (int, float)):
                holes = [holes]
            base, high = float(p["base"]), float(p["top"])
            if high <= base:
                continue
            xs, ys = ring[0::2], ring[1::2]
            j0 = max(0, int(math.floor(min(ys) - miny)) - 1)
            j1 = min(ny - 1, int(math.ceil(max(ys) - miny)) + 1)
            i0 = max(0, int(math.floor(min(xs) - minx)) - 1)
            i1 = min(nx - 1, int(math.ceil(max(xs) - minx)) + 1)
            for j in range(j0, j1 + 1):
                y = miny + j
                spans = _spans(ring, y)
                if not spans:
                    continue
                hspans = []
                for h in holes:
                    if len(h) >= 6:
                        hspans.extend(_spans(h, y))
                row = j * nx
                for s, e in spans:
                    ia = max(i0, int(math.ceil(s - minx)))
                    ib = min(i1, int(math.floor(e - minx)))
                    for i in range(ia, ib + 1):
                        x = minx + i
                        if any(hs <= x <= he for hs, he in hspans):
                            continue
                        k = row + i
                        if base <= g[k] + 1.5:
                            if high > top[k]:
                                top[k] = high
                        else:
                            b = ohb[k]
                            if math.isnan(b) or base < b:
                                ohb[k] = base
                            tt = oht[k]
                            if math.isnan(tt) or high > tt:
                                oht[k] = high

    def _build_trees(self, trees):
        self.trees = []
        self.tree_hash = {}
        self.tree_bucket = 24.0
        if not trees:
            return
        fields = trees["fields"]
        data = trees["data"]
        nf = len(fields)
        fi = {name: k for k, name in enumerate(fields)}
        bucket = self.tree_bucket
        for k in range(0, len(data) - nf + 1, nf):
            row = data[k:k + nf]
            x = float(row[fi["x"]])
            y = float(row[fi["y"]])
            z = float(row[fi.get("z", 0)])
            h = float(row[fi["height"]])
            cr = float(row[fi["crownR"]])
            cb = float(row[fi["crownBase"]])
            tr = float(row[fi["trunkR"]])
            cx = float(row[fi["crownX"]]) if "crownX" in fi else x
            cy = float(row[fi["crownY"]]) if "crownY" in fi else y
            top = z + h
            rec = (cx, cy, max(z, cb), top, cr, tr, x, y)
            self.trees.append(rec)
            self.tree_hash.setdefault((int(x // bucket), int(y // bucket)), []).append(rec)

    def _build_nav(self):
        c = self.nav_cell
        for j in range(self.nny):
            y = self.miny + j * c
            row = j * self.nnx
            for i in range(self.nnx):
                x = self.minx + i * c
                z = self.ground(x, y)
                self.nav_z[row + i] = z
                blk = self.blocked(x, y, z)
                if not blk:
                    d = self.ground(x + c, y) - z
                    d2 = self.ground(x, y + c) - z
                    if max(abs(d), abs(d2)) / c > self.max_slope:
                        blk = True
                if x < self.minx + 4 or x > self.maxx - 4 or y < self.miny + 4 or y > self.maxy - 4:
                    blk = True
                self.nav_blocked[row + i] = 1 if blk else 0

    # ------------------------------------------------------------------ queries
    def idx(self, x, y):
        i = int(round(x - self.minx))
        j = int(round(y - self.miny))
        if i < 0:
            i = 0
        elif i >= self.nx:
            i = self.nx - 1
        if j < 0:
            j = 0
        elif j >= self.ny:
            j = self.ny - 1
        return j * self.nx + i

    def in_bounds(self, x, y):
        i = int(round(x - self.minx))
        j = int(round(y - self.miny))
        return 1 <= i < self.nx - 1 and 1 <= j < self.ny - 1

    def ground(self, x, y):
        """Terrain height of the 1 m column under (x, y)."""
        return self.g[self.idx(x, y)]

    def surface(self, x, y, z, step_up=None):
        """Highest walkable surface at (x,y) at or below z + step_up."""
        step_up = self.step_up if step_up is None else step_up
        k = self.idx(x, y)
        s = self.g[k]
        if self.top[k] <= z + step_up and self.top[k] > s:
            s = self.top[k]
        return s

    def intervals(self, x, y):
        """Compatibility helper: solid intervals at the column under (x,y)."""
        k = self.idx(x, y)
        out = []
        if self.top[k] > self.g[k]:
            out.append((self.g[k], self.top[k]))
        if not math.isnan(self.ohb[k]):
            out.append((self.ohb[k], self.oht[k]))
        return out or None

    def _solid_cell(self, x, y, z, h, step_up):
        if not self.in_bounds(x, y):
            return True
        k = self.idx(x, y)
        if self.top[k] > z + step_up:
            return True
        b = self.ohb[k]
        if b < z + h and self.oht[k] > z + step_up:
            return True
        return False

    def _ring(self, x, y, z, h, radius, step_up):
        """Engine-style collision: centre + eight points on the mech's radius."""
        r = radius * 0.9
        if self._solid_cell(x, y, z, h, step_up):
            return False
        for a in range(8):
            ang = a * TAU / 8.0
            if self._solid_cell(x + math.cos(ang) * r, y + math.sin(ang) * r,
                                z, h, step_up):
                return False
        return True

    def blocked(self, x, y, z, h=None, step_up=None, radius=None):
        """True when a mech with feet at z cannot stand at (x,y)."""
        h = self.height if h is None else h
        step_up = self.step_up if step_up is None else step_up
        radius = self.radius if radius is None else radius
        return not self._ring(x, y, z, h, radius, step_up)

    def walk_clear(self, x0, y0, x1, y1, z, h=None, radius=None, step_up=None):
        """True when the straight segment is body-clear at the current height."""
        h = self.height if h is None else h
        step_up = self.step_up if step_up is None else step_up
        radius = self.radius if radius is None else radius
        dx, dy = x1 - x0, y1 - y0
        d = math.hypot(dx, dy)
        if d < 0.01:
            return self._ring(x1, y1, z, h, radius, step_up)
        n = max(1, min(20, int(d / 1.25) + 1))
        for k in range(1, n + 1):
            f = k / n
            if not self._ring(x0 + dx * f, y0 + dy * f, z, h, radius, step_up):
                return False
        return True

    def solid(self, x, y, z):
        """Point-in-solid test used for projectile / laser lines."""
        k = self.idx(x, y)
        if z < self.top[k]:
            return True
        b = self.ohb[k]
        return (b <= z <= self.oht[k]) if not math.isnan(b) else False

    def shot_clear(self, a, b, step=None):
        """Line of sight for projectiles/lasers: terrain + prisms, trees ignored."""
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return True
        st = step or 1.0
        n = max(2, min(240, int(dist / st) + 1))
        for k in range(1, n):
            f = k / n
            if self.solid(a[0] + dx * f, a[1] + dy * f, a[2] + dz * f):
                return False
        return True

    def vision_clear(self, a, b):
        """Approximate visual LOS including tree canopy and trunks."""
        if not self.shot_clear(a, b):
            return False
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        dist = math.hypot(dx, dy)
        n = max(2, min(80, int(dist / 4.0) + 1))
        density = 0.0
        seen = set()
        bk = self.tree_bucket
        for k in range(1, n):
            f = k / n
            x, y, z = a[0] + dx * f, a[1] + dy * f, a[2] + dz * f
            key = (int(x // bk), int(y // bk))
            for gi in (key, (key[0] + 1, key[1]), (key[0] - 1, key[1]),
                       (key[0], key[1] + 1), (key[0], key[1] - 1)):
                for rec in self.tree_hash.get(gi, ()):
                    rid = id(rec)
                    if rid in seen:
                        continue
                    seen.add(rid)
                    cx, cy, cb, top, cr, tr, tx, ty = rec
                    if cb <= z <= top:
                        d = math.hypot(x - cx, y - cy)
                        if d < cr:
                            density += self.canopy_density * (1.0 - d / cr)
                    if z < cb and math.hypot(x - tx, y - ty) < tr:
                        return False
            if density > self.canopy_block_t:
                return False
        return True

    def cover_score(self, x, y, z):
        """0..1: how much solid geometry is nearby (good for hiding)."""
        score = 0.0
        for ang in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
            px, py = x + math.cos(ang) * 6.0, y + math.sin(ang) * 6.0
            if self.blocked(px, py, z):
                score += 0.25
        return score


class NullWorld:
    """Permissive stand-in when the arena files cannot be read.

    A crashed mech is scored as a sitting target, so the bot must always keep
    playing even if /arena is missing.  Without a map it loses LOS/navigation
    but keeps zone logic, facing, firing and economy working.
    """

    def __init__(self, cfg=None):
        cfg = cfg or {}
        mech = cfg.get("mech", {}) or {}
        cubes = cfg.get("cubes", {}) or {}
        self.ready = False
        self.minx, self.miny = -600.0, -600.0
        self.maxx, self.maxy = 600.0, 600.0
        self.nav_cell = 8.0
        self.radius = float(mech.get("radius", 2.5))
        self.height = float(mech.get("height", 9.0))
        self.step_up = float(mech.get("step_up", 1.2))
        self.eye_height = float(mech.get("eye_height", 8.0))
        self.muzzle_height = float(mech.get("muzzle_height", 7.0))
        self.front_arc_deg = float(mech.get("front_arc_deg", 180.0))
        self.rear_mult = float(mech.get("rear_mult", 1.5))
        self.size_per_cube = float(cubes.get("size_per_cube", 0.05))
        self.canopy_density = 0.35
        self.canopy_block_t = 0.25
        self.max_slope = 1.19
        self.nx = self.ny = self.nnx = self.nny = 0
        self.nav_blocked = bytearray(0)
        self.nav_z = []
        self.trees = []
        self.tree_hash = {}
        self.tree_bucket = 24.0

    def ground(self, x, y):
        return 0.0

    def surface(self, x, y, z, step_up=None):
        return 0.0

    def idx(self, x, y):
        return 0

    def in_bounds(self, x, y):
        return True

    def intervals(self, x, y):
        return None

    def blocked(self, x, y, z, h=None, step_up=None, radius=None):
        return False

    def _ring(self, x, y, z, h, radius, step_up):
        return True

    def shot_clear(self, a, b, step=None):
        return True

    def solid(self, x, y, z):
        return False

    def vision_clear(self, a, b):
        return True

    def cover_score(self, x, y, z):
        return 0.0

    def walk_clear(self, x0, y0, x1, y1, z, h=None, radius=None, step_up=None):
        return True
