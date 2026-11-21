"""Zone interpolation and safe-position selection."""
from __future__ import annotations

import math

TAU = math.tau


def current_circle(z, t):
    """The circle that is in force at match time t."""
    ss, se = z.get("shrink_start", 1e9), z.get("shrink_end", 1e9)
    c, r = z["center"], z["radius"]
    nc, nr = z["next_center"], z["next_radius"]
    if t <= ss or se <= ss:
        return (c[0], c[1]), r
    if t >= se:
        return (nc[0], nc[1]), nr
    f = (t - ss) / (se - ss)
    return (c[0] + (nc[0] - c[0]) * f, c[1] + (nc[1] - c[1]) * f), r + (nr - r) * f


def outside_amount(x, y, center, radius):
    return math.hypot(x - center[0], y - center[1]) - radius


class ZoneModel:
    def __init__(self, config, seed=0):
        self.cfg = config
        zc = config.get("zone", {})
        self.start_center = zc.get("start_center", (0.0, 0.0))
        self.start_radius = zc.get("start_radius", 560.0)
        self.phases = zc.get("phases", [])
        self.seed = seed

    def choose_goal(self, obs, me, world, threats, params, t, sectors=None):
        """Pick a quiet, covered spot inside the next circle, away from threats.

        `sectors` are uncertain bearing/range contacts, not enemy positions;
        they only apply a soft penalty to candidate goals lying inside them.
        """
        z = obs["zone"]
        (cx, cy), r = current_circle(z, t)
        x, y, fz = me["pos"][0], me["pos"][1], me["pos"][2]
        nc, nr = z["next_center"], z["next_radius"]
        margin = params["zone_margin"]
        d = math.hypot(x - cx, y - cy)

        # Outside (or nearly outside) the circle: get back in, fast.
        if d > r * margin:
            return (cx + (x - cx) * 0.0, cy + (y - cy) * 0.0), True

        off = params["goal_offset"] * max(8.0, nr)
        base = (self.seed % 360) * math.pi / 180.0
        n = max(4, int(params["goal_candidates"]))
        best = None
        best_score = -1e18
        tx = sum(p[0] for p in threats) / len(threats) if threats else nc[0]
        ty = sum(p[1] for p in threats) / len(threats) if threats else nc[1]
        for k in range(n):
            a = base + TAU * k / n
            gx = nc[0] + math.cos(a) * off
            gy = nc[1] + math.sin(a) * off
            # must be inside the current circle with margin
            if math.hypot(gx - cx, gy - cy) > r * margin:
                continue
            if world.blocked(gx, gy, world.ground(gx, gy), 9.0):
                continue
            cover = world.cover_score(gx, gy, world.ground(gx, gy))
            tdist = min((math.hypot(gx - p[0], gy - p[1]) for p in threats), default=180.0)
            # prefer the side away from the threat centroid
            away = math.hypot(gx - tx, gy - ty)
            travel = math.hypot(gx - x, gy - y)
            height = world.ground(gx, gy)
            score = (params["cover_bias"] * cover * 40.0
                     + params["threat_bias"] * min(tdist, 220.0) * 0.18
                     + params["threat_bias"] * min(away, 220.0) * 0.10
                     - params["travel_bias"] * travel * 0.35
                     + params["slope_bias"] * height * 0.4)
            if sectors:
                bias = params.get("sound_goal_bias", 0.0)
                if bias > 0.0:
                    penalty = sum(s.penalty(gx, gy, me["pos"], t) for s in sectors)
                    score -= bias * penalty * 20.0
            if score > best_score:
                best_score = score
                best = (gx, gy)
        if best is None:
            return (nc[0], nc[1]), False
        return best, False
