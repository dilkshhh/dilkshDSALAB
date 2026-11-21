"""Aiming, torso slew, hit prediction and evasion."""
from __future__ import annotations

import math

TAU = math.tau


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def size_scale(cubes):
    return 1.0 + 0.05 * float(cubes or 0)


def target_center(actor):
    s = size_scale(actor.get("cubes", 0))
    p = actor["pos"]
    return (p[0], p[1], p[2] + 4.5 * s)


def muzzle(me):
    s = me["stats"].get("muzzle_height", 7.0)
    p = me["pos"]
    return (p[0], p[1], p[2] + s)


def intercept(src, tgt, vel, speed):
    """Iterative constant-velocity intercept. Returns (point, flight_time)."""
    dx, dy, dz = tgt[0] - src[0], tgt[1] - src[1], tgt[2] - src[2]
    t = math.sqrt(dx * dx + dy * dy + dz * dz) / max(1.0, speed)
    for _ in range(3):
        ex, ey, ez = tgt[0] + vel[0] * t, tgt[1] + vel[1] * t, tgt[2] + vel[2] * t
        dx, dy, dz = ex - src[0], ey - src[1], ez - src[2]
        t = math.sqrt(dx * dx + dy * dy + dz * dz) / max(1.0, speed)
    return (tgt[0] + vel[0] * t, tgt[1] + vel[1] * t, tgt[2] + vel[2] * t), t


def aim_to(src, point):
    dx, dy, dz = point[0] - src[0], point[1] - src[1], point[2] - src[2]
    flat = math.hypot(dx, dy)
    return math.atan2(dy, dx), math.atan2(dz, flat)


def future_aim(me, cmd_yaw, cmd_pitch, dt=0.1):
    """Where the torso will actually point when a shot leaves (slew limited)."""
    ay, ap = me["aim"][0], me["aim"][1]
    st = me.get("stats", {})
    try_rate = float(st.get("turn_rate", 4.0))
    pit_rate = float(st.get("pitch_rate", 3.0))
    y = ay + clamp(wrap(cmd_yaw - ay), -try_rate * dt, try_rate * dt)
    p = ap + clamp(cmd_pitch - ap, -pit_rate * dt, pit_rate * dt)
    return y, p


def shot_error(src, point, yaw, pitch):
    """Approximate spatial miss (m) of a ray from src along (yaw,pitch) vs point."""
    dx, dy, dz = point[0] - src[0], point[1] - src[1], point[2] - src[2]
    d = math.sqrt(dx * dx + dy * dy + dz * dz)
    ux = math.cos(pitch) * math.cos(yaw)
    uy = math.cos(pitch) * math.sin(yaw)
    uz = math.sin(pitch)
    proj = dx * ux + dy * uy + dz * uz
    if proj <= 0:
        return d + 10.0
    return math.sqrt(max(0.0, d * d - proj * proj))


def mortar_pitch(R, dz, v, g):
    """Low and high arc solutions, or None. R = horizontal range."""
    if R < 1.0:
        return None
    v2 = v * v
    disc = v2 * v2 - g * (g * R * R + 2.0 * dz * v2)
    if disc < 0:
        return None
    root = math.sqrt(disc)
    return (math.atan2(v2 - root, g * R), math.atan2(v2 + root, g * R))


def dodge_vector(me, projectiles, params):
    """Perpendicular escape from incoming bullets/shells."""
    px, py, pz = me["pos"][0], me["pos"][1], me["pos"][2]
    cx, cy = 0.0, 0.0
    horizon = params["dodge_lead_s"]
    vel = me.get("vel", [0.0, 0.0, 0.0])
    for pr in projectiles:
        q = pr["pos"]
        v = pr["vel"]
        rx, ry = q[0] - px, q[1] - py
        rvx, rvy = v[0] - vel[0], v[1] - vel[1]
        vn = rvx * rvx + rvy * rvy
        if vn < 1.0:
            continue
        t = -(rx * rvx + ry * rvy) / vn
        if t < 0.0 or t > horizon:
            continue
        mx, my = rx + rvx * t, ry + rvy * t
        md = math.hypot(mx, my)
        if md > 7.0:
            continue
        w = (1.0 - md / 7.0) * (1.0 - t / horizon)
        if md < 0.01:
            continue
        # push away from the miss point
        cx -= mx / md * w
        cy -= my / md * w
    d = math.hypot(cx, cy)
    if d > 1e-6:
        return (cx / d * params["dodge_gain"], cy / d * params["dodge_gain"])
    return (0.0, 0.0)


def laser_dodge(me, enemies, params):
    """Strafe when a visible mech is charging a laser roughly at us."""
    px, py = me["pos"][0], me["pos"][1]
    vx, vy = 0.0, 0.0
    for e in enemies:
        if not e.get("charging"):
            continue
        yaw = e.get("aim", [0.0, 0.0])[0]
        ex, ey = e["pos"][0], e["pos"][1]
        bearing = math.atan2(py - ey, px - ex)
        if abs(wrap(yaw - bearing)) > 0.28:
            continue
        d = math.hypot(px - ex, py - ey)
        if d > 280.0:
            continue
        w = 1.0 - d / 280.0
        # perpendicular to their aim
        vx += -math.sin(yaw) * w
        vy += math.cos(yaw) * w
    d = math.hypot(vx, vy)
    if d > 1e-6:
        return (vx / d * params["laser_dodge_gain"], vy / d * params["laser_dodge_gain"])
    return (0.0, 0.0)


class Combat:
    """Stateful weapon handling (laser charge bookkeeping lives here)."""

    def __init__(self, world, params):
        self.w = world
        self.p = params
        self.release_laser = False

    def pick_target(self, me, enemies, max_range):
        px, py = me["pos"][0], me["pos"][1]
        src = muzzle(me)
        best = None
        best_score = 1e30
        for e in enemies:
            d = math.hypot(e["pos"][0] - px, e["pos"][1] - py)
            if d > max_range:
                continue
            tc = target_center(e)
            if not self.w.shot_clear(src, tc):
                continue
            score = d - 45.0 * (1.0 - min(1.0, e.get("hp", 1400) / 1400.0))
            if score < best_score:
                best_score = score
                best = e
        return best

    def act(self, obs, me, enemies, params, allow_fire=True):
        """Return (aim, fire[2], fired) for this decision."""
        p = params
        weapons = me["weapons"]
        src = muzzle(me)
        fire = [False, False]
        aim_cmd = None
        fired = False

        target = self.pick_target(me, enemies, p["fire_max_range"])
        if target is not None:
            tc = target_center(target)
            tv = target.get("vel", [0.0, 0.0, 0.0])
            tr = 2.5 * size_scale(target.get("cubes", 0))

        # --- slot 0: gun ---------------------------------------------------
        w0 = weapons[0] if weapons else None
        if w0 and w0["kind"] == "gun" and target is not None:
            st = w0["stats"]
            pt, ft = intercept(src, tc, tv, st["speed"])
            yaw, pitch = aim_to(src, pt)
            pitch = clamp(pitch, -0.7, 1.3)
            aim_cmd = [yaw, pitch]
            fy, fp = future_aim(me, yaw, pitch)
            err = shot_error(src, pt, fy, fp)
            spread = math.radians(st.get("spread_deg", 0.6)) * math.dist(src, pt)
            if (allow_fire and p["fire_enabled"] and err + spread * 0.5 < tr * p["gun_min_hit"]
                    and w0.get("ammo", 1) > 0 and w0.get("reload", 0) == 0
                    and w0.get("cooldown", 0) <= 0.05
                    and math.dist(src, pt) < st["range"]):
                fire[0] = True
                fired = True

        # --- slot 1: laser / lightning / mortar ----------------------------
        w1 = weapons[1] if len(weapons) > 1 else None
        if w1 and target is not None:
            kind = w1["kind"]
            if kind == "laser":
                st = w1["stats"]
                charge = w1.get("charge", 0.0)
                full = st["charge"]
                pt, _ = intercept(src, tc, tv, 1e6)  # hitscan: aim one decision ahead
                pt = (tc[0] + tv[0] * 0.1, tc[1] + tv[1] * 0.1, tc[2] + tv[2] * 0.1)
                yaw, pitch = aim_to(src, pt)
                pitch = clamp(pitch, -0.7, 1.3)
                if aim_cmd is None:
                    aim_cmd = [yaw, pitch]
                fy, fp = future_aim(me, yaw, pitch)
                err = shot_error(src, pt, fy, fp)
                aligned = err < tr * 1.15 and math.dist(src, pt) < st["range"]
                if charge >= max(p["laser_min_charge"], st.get("min_charge", 0.15)) and aligned:
                    fire[1] = False  # release -> fire
                    self.release_laser = True
                    fired = True
                elif charge < full and w1.get("cooldown", 0) <= 0.05 and allow_fire:
                    fire[1] = True
                    if aim_cmd is None or w0 is None or w0.get("kind") != "gun":
                        aim_cmd = [yaw, pitch]
                if self.release_laser:
                    fire[1] = False
                    self.release_laser = False
            elif kind == "lightning":
                st = w1["stats"]
                d = math.dist(src, tc)
                yaw = math.atan2(tc[1] - src[1], tc[0] - src[0])
                if d < st["range"] and me["energy"] > p["lightning_energy_floor"]:
                    if aim_cmd is None:
                        aim_cmd = [yaw, 0.0]
                    if allow_fire:
                        fire[1] = True
                        fired = True
            elif kind == "mortar":
                st = w1["stats"]
                if allow_fire:
                    dx = tc[0] - src[0]
                    dy = tc[1] - src[1]
                    R = math.hypot(dx, dy)
                    dz = tc[2] - src[2]
                    sol = mortar_pitch(R, dz, st["speed"], st["gravity"])
                    if sol and R > 30.0 and R < 210.0:
                        for pitch in sol:
                            if not (-0.7 <= pitch <= 1.3):
                                continue
                            yaw = math.atan2(dy, dx)
                            # sample the arc for obstruction
                            v = st["speed"]
                            g = st["gravity"]
                            tt = R / (v * math.cos(pitch)) if math.cos(pitch) > 0.01 else 99
                            clear = True
                            for k in range(1, 9):
                                f = k / 9.0
                                ttf = tt * f
                                ax = src[0] + v * math.cos(pitch) * math.cos(yaw) * ttf
                                ay = src[1] + v * math.cos(pitch) * math.sin(yaw) * ttf
                                az = src[2] + v * math.sin(pitch) * ttf - 0.5 * g * ttf * ttf
                                if self.w.blocked(ax, ay, max(az - 1.0, 0.0), 1.0):
                                    clear = False
                                    break
                            if not clear:
                                continue
                            if abs(pitch - me["aim"][1]) > 0.5:
                                if aim_cmd is None:
                                    aim_cmd = [yaw, pitch]
                                continue
                            if aim_cmd is None:
                                aim_cmd = [yaw, pitch]
                            fire[1] = True
                            fired = True
                            break
        return aim_cmd, fire, fired
