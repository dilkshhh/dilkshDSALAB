"""Arena model: terrain heightmap, solid prisms, tree canopy and line of sight.

Everything expensive is built once in hello (20 s budget). Per-decision queries are
O(samples along a ray) with list lookups only.
"""
from __future__ import annotations

import json
import math
import os
import sys
from array import array

TAU = math.tau


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
    def __init__(self, map_dir, cell=2.0, nav_cell=8.0, load_trees=True):
        self.map_dir = map_dir
        with open(os.path.join(map_dir, "v2", "world.json"), "r", encoding="utf-8") as f:
            w = json.load(f)
        self.w = w
        b = w["bounds"]
        self.minx, self.maxx = float(b["minX"]), float(b["maxX"])
        self.miny, self.maxy = float(b["minY"]), float(b["maxY"])
        t = w["terrain"]
        self.tminx, self.tminy = float(t["minX"]), float(t["minY"])
        self.tstep, self.tscale = float(t["step"]), float(t["scale"])
        self.tnx, self.tny = int(t["nx"]), int(t["ny"])
        with open(os.path.join(map_dir, "v2", "terrain.i16"), "rb") as f:
            raw = f.read()
        self.terr = array("h")
        self.terr.frombytes(raw[: self.tnx * self.tny * 2])
        if sys.byteorder != "little":
            self.terr.byteswap()
        self.scale = self.tscale

        # ---- 2 m column grid ------------------------------------------------
        self.cell = float(cell)
        self.nx = int((self.maxx - self.minx) / self.cell) + 2
        self.ny = int((self.maxy - self.miny) / self.cell) + 2
        n = self.nx * self.ny
        self.g = [0.0] * n                 # ground height at each cell centre
        self.cols = [None] * n             # merged (base, top) solid intervals
        self._build_ground()
        self._build_prisms(w["prisms"])
        self._build_trees(w["trees"] if load_trees else None)

        # ---- coarse navigation grid -----------------------------------------
        self.nav_cell = float(nav_cell)
        self.nnx = int((self.maxx - self.minx) / self.nav_cell) + 2
        self.nny = int((self.maxy - self.miny) / self.nav_cell) + 2
        self.nav_blocked = bytearray(self.nnx * self.nny)
        self.nav_z = [0.0] * (self.nnx * self.nny)
        self._build_nav()
        self.ready = True

    # ------------------------------------------------------------------ build
    def _terrain_raw(self, i, j):
        if i < 0:
            i = 0
        elif i >= self.tnx:
            i = self.tnx - 1
        if j < 0:
            j = 0
        elif j >= self.tny:
            j = self.tny - 1
        return self.terr[j * self.tnx + i] * self.scale

    def _build_ground(self):
        c = self.cell
        nx, ny = self.nx, self.ny
        for j in range(ny):
            y = self.miny + j * c
            fy = (y - self.tminy) / self.tstep
            j0 = int(fy)
            ty = fy - j0
            row = j * nx
            for i in range(nx):
                x = self.minx + i * c
                fx = (x - self.tminx) / self.tstep
                i0 = int(fx)
                tx = fx - i0
                a = self._terrain_raw(i0, j0)
                bb = self._terrain_raw(i0 + 1, j0)
                cc = self._terrain_raw(i0, j0 + 1)
                dd = self._terrain_raw(i0 + 1, j0 + 1)
                self.g[row + i] = (a * (1 - tx) * (1 - ty) + bb * tx * (1 - ty)
                                   + cc * (1 - tx) * ty + dd * tx * ty)

    def _build_prisms(self, prisms):
        c = self.cell
        nx, ny = self.nx, self.ny
        for p in prisms:
            ring = p["ring"]
            holes = p.get("holes") or []
            base, top = float(p["base"]), float(p["top"])
            if not ring or top <= base:
                continue
            xs = ring[0::2]
            ys = ring[1::2]
            i0 = max(0, int((min(xs) - self.minx) / c) - 1)
            i1 = min(nx - 1, int((max(xs) - self.minx) / c) + 1)
            j0 = max(0, int((min(ys) - self.miny) / c) - 1)
            j1 = min(ny - 1, int((max(ys) - self.miny) / c) + 1)
            if i1 < i0 or j1 < j0:
                continue
            for j in range(j0, j1 + 1):
                y = self.miny + j * c
                spans = _spans(ring, y)
                if not spans:
                    continue
                hspans = []
                for h in holes:
                    hspans.extend(_spans(h, y))
                row = j * nx
                for s, e in spans:
                    ia = max(i0, int((s - self.minx) / c))
                    ib = min(i1, int((e - self.minx) / c))
                    for i in range(ia, ib + 1):
                        x = self.minx + i * c
                        if not (s <= x <= e):
                            continue
                        skip = False
                        for hs, he in hspans:
                            if hs <= x <= he:
                                skip = True
                                break
                        if skip:
                            continue
                        idx = row + i
                        cur = self.cols[idx]
                        if cur is None:
                            self.cols[idx] = [(base, top)]
                        else:
                            cur.append((base, top))
        # merge overlapping/adjacent intervals
        for idx, cur in enumerate(self.cols):
            if cur and len(cur) > 1:
                cur.sort()
                merged = [cur[0]]
                for a, b in cur[1:]:
                    la, lb = merged[-1]
                    if a <= lb + 0.01:
                        if b > lb:
                            merged[-1] = (la, b)
                    else:
                        merged.append((a, b))
                self.cols[idx] = merged

    def _build_trees(self, trees):
        self.trees = []
        self.tree_hash = {}
        if not trees:
            return
        fields = trees["fields"]
        data = trees["data"]
        nf = len(fields)
        fi = {name: k for k, name in enumerate(fields)}
        bucket = 24.0
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
            key = (int(x // bucket), int(y // bucket))
            self.tree_hash.setdefault(key, []).append(rec)
        self.tree_bucket = bucket

    def _build_nav(self):
        c = self.nav_cell
        for j in range(self.nny):
            y = self.miny + j * c
            row = j * self.nnx
            for i in range(self.nnx):
                x = self.minx + i * c
                z = self.ground(x, y)
                self.nav_z[row + i] = z
                blk = self.blocked(x, y, z, 9.0)
                if not blk:
                    # slopes steeper than 50 degrees cannot be walked up
                    d = self.ground(x + c, y) - z
                    d2 = self.ground(x, y + c) - z
                    if max(abs(d), abs(d2)) / c > 1.19:
                        blk = True
                if x < self.minx + 4 or x > self.maxx - 4 or y < self.miny + 4 or y > self.maxy - 4:
                    blk = True
                self.nav_blocked[row + i] = 1 if blk else 0

    # ------------------------------------------------------------------ queries
    def idx(self, x, y):
        i = int((x - self.minx) / self.cell)
        j = int((y - self.miny) / self.cell)
        if i < 0:
            i = 0
        elif i >= self.nx:
            i = self.nx - 1
        if j < 0:
            j = 0
        elif j >= self.ny:
            j = self.ny - 1
        return j * self.nx + i

    def ground(self, x, y):
        fx = (x - self.minx) / self.cell
        fy = (y - self.miny) / self.cell
        i, j = int(fx), int(fy)
        tx, ty = fx - i, fy - j
        nx, ny = self.nx, self.ny
        i = min(max(i, 0), nx - 2)
        j = min(max(j, 0), ny - 2)
        g = self.g
        a = g[j * nx + i]
        b = g[j * nx + i + 1]
        c = g[(j + 1) * nx + i]
        d = g[(j + 1) * nx + i + 1]
        return a * (1 - tx) * (1 - ty) + b * tx * (1 - ty) + c * (1 - tx) * ty + d * tx * ty

    def surface(self, x, y, z, step_up=1.2):
        """Highest walkable surface at (x,y) at or below z+step_up."""
        g = self.ground(x, y)
        best = g
        cols = self.cols[self.idx(x, y)]
        if cols:
            for a, b in cols:
                if b <= z + step_up and b > best:
                    best = b
        return best

    def intervals(self, x, y):
        return self.cols[self.idx(x, y)]

    def blocked(self, x, y, z, h=9.0, step_up=1.2):
        """Is a vertical cylinder with feet at z blocked at (x,y)?"""
        if self.ground(x, y) > z + step_up:
            return True
        cols = self.cols[self.idx(x, y)]
        if cols:
            top_limit = z + h
            low = z + step_up
            for a, b in cols:
                if b > low and a < top_limit:
                    return True
        return False

    def shot_clear(self, a, b, step=None):
        """Line of sight for projectiles/lasers: terrain + prisms, trees ignored."""
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        dz = b[2] - a[2]
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return True
        st = step or self.cell
        n = max(2, min(160, int(dist / st) + 1))
        cols = self.cols
        nx = self.nx
        g = self.g
        minx, miny, c = self.minx, self.miny, self.cell
        for k in range(1, n):
            f = k / n
            x = a[0] + dx * f
            y = a[1] + dy * f
            z = a[2] + dz * f
            i = int((x - minx) / c)
            j = int((y - miny) / c)
            if i < 0 or i >= self.nx or j < 0 or j >= self.ny:
                return False
            idx = j * nx + i
            # ground: bilinear-free lookup at cell centre (close enough for shots)
            if g[idx] > z + 0.05:
                return False
            iv = cols[idx]
            if iv:
                for lo, hi in iv:
                    if lo < z < hi:
                        return False
        return True

    def vision_clear(self, a, b):
        """Approximate visual LOS including tree canopy and trunks."""
        if not self.shot_clear(a, b):
            return False
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        dz = b[2] - a[2]
        dist = math.hypot(dx, dy)
        n = max(2, min(80, int(dist / 4.0) + 1))
        density = 0.0
        seen = set()
        bk = self.tree_bucket
        for k in range(1, n):
            f = k / n
            x = a[0] + dx * f
            y = a[1] + dy * f
            z = a[2] + dz * f
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
                            density += 0.35 * (1.0 - d / cr)
                    if z < cb and math.hypot(x - tx, y - ty) < tr:
                        return False
            if density > 0.75:
                return False
        return True

    def cover_score(self, x, y, z):
        """0..1: how much solid geometry is nearby (good for hiding)."""
        score = 0.0
        for ang in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
            px = x + math.cos(ang) * 6.0
            py = y + math.sin(ang) * 6.0
            if self.blocked(px, py, z, 9.0):
                score += 0.25
        return score

    def walk_clear(self, x0, y0, x1, y1, z, h=9.0, radius=2.2):
        dx, dy = x1 - x0, y1 - y0
        d = math.hypot(dx, dy)
        if d < 0.01:
            return not self.blocked(x1, y1, z, h)
        n = max(1, min(24, int(d / 2.0) + 1))
        ux, uy = dx / d, dy / d
        px, py = -uy * radius, ux * radius
        for k in range(1, n + 1):
            f = k / n
            x = x0 + dx * f
            y = y0 + dy * f
            if (self.blocked(x, y, z, h) or self.blocked(x + px, y + py, z, h)
                    or self.blocked(x - px, y - py, z, h)):
                return False
        return True


class NullWorld:
    """Permissive stand-in when the arena files cannot be read.

    A crashed mech is scored as a sitting target, so the bot must always keep
    playing even if /arena is missing. Without a map it loses LOS/navigation
    but keeps zone logic, facing, firing and economy working.
    """

    def __init__(self):
        self.ready = False
        self.minx, self.miny = -600.0, -600.0
        self.nav_cell = 4.0
        self.nx = self.ny = self.nnx = self.nny = 0
        self.nav_blocked = bytearray(0)
        self.nav_z = []
        self.trees = []
        self.tree_hash = {}

    def ground(self, x, y):
        return 0.0

    def surface(self, x, y, z, step_up=1.2):
        return 0.0

    def idx(self, x, y):
        return 0

    def intervals(self, x, y):
        return None

    def blocked(self, x, y, z, h=9.0, step_up=1.2):
        return False

    def shot_clear(self, a, b, step=None):
        return True

    def vision_clear(self, a, b):
        return True

    def cover_score(self, x, y, z):
        return 0.0

    def walk_clear(self, x0, y0, x1, y1, z, h=9.0, radius=2.2):
        return True
