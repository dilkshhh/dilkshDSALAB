"""Aiming, torso slew, hit prediction and evasion.

`aim_arbiter=True` builds one final commanded torso aim per decision and only
fires a weapon whose own solution remains compatible with that final aim.
`aim_arbiter=False` preserves the previous two-slot behaviour for paired A/B
experiments.  Both paths use the live `hello.config` geometry where available.
"""
from __future__ import annotations

import math

TAU = math.tau


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def size_scale(cubes, size_per_cube=0.05):
    return 1.0 + size_per_cube * float(cubes or 0)


def target_center(actor, size_per_cube=0.05, height=9.0):
    s = size_scale(actor.get("cubes", 0), size_per_cube)
    p = actor["pos"]
    return (p[0], p[1], p[2] + 0.5 * height * s)


def muzzle(me):
    s = _num(me.get("stats", {}).get("muzzle_height"), 7.0)
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
    st = me.get("stats", {}) or {}
    try_rate = _num(st.get("turn_rate"), 4.0)
    pit_rate = _num(st.get("pitch_rate"), 3.0)
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
        if not e.get("charging") or e.get("charging_conf", 1.0) <= 0.0:
            continue
        if e.get("aim_conf", 1.0) <= 0.0:
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
    """Stateful weapon handling (legacy laser release bookkeeping lives here)."""

    def __init__(self, world, params, cfg=None):
        self.w = world
        self.p = params
        self.cfg = cfg or {}
        mech = self.cfg.get("mech", {}) or {}
        cubes = self.cfg.get("cubes", {}) or {}
        match = self.cfg.get("match", {}) or {}
        self.size_per_cube = _num(cubes.get("size_per_cube"), 0.05)
        self.height = _num(mech.get("height"), 9.0)
        self.radius = _num(mech.get("radius"), 2.5)
        self.min_pitch = _num(mech.get("min_pitch"), -0.7)
        self.max_pitch = _num(mech.get("max_pitch"), 1.3)
        self.base_hp = _num(mech.get("hp"), 1400.0)
        self.self_damage_mult = _num(mech.get("self_damage_mult"), 0.5)
        self.dt = (_num(match.get("decide_every"), 2.0)
                   / max(1.0, _num(match.get("tick_hz"), 20.0)))
        self.release_laser = False
        # target hysteresis: see pick_target
        self.focus_id = None
        self.focus_enabled = bool(self.p.get("focus_fire", True))
        self.focus_switch_margin = _num(self.p.get("focus_switch_margin"), 55.0)

    # ------------------------------------------------------------------ shared
    def _pitch_limits(self, me):
        st = me.get("stats", {}) or {}
        return (_num(st.get("min_pitch"), self.min_pitch),
                _num(st.get("max_pitch"), self.max_pitch))

    def _center(self, actor):
        return target_center(actor, self.size_per_cube, self.height)

    def _radius(self, actor):
        return self.radius * size_scale(actor.get("cubes", 0), self.size_per_cube)

    def _future(self, me, yaw, pitch):
        return future_aim(me, yaw, pitch, self.dt)

    def pick_target(self, me, enemies, max_range):
        """Choose who to shoot, with hysteresis so damage is not spread.

        Re-picking by distance every decision scatters fire across the squad:
        measured 2442 damage per 1400 HP kill, i.e. 40% of our output was
        wasted on bots that never died.  Keep hitting the same target until it
        dies, leaves line of sight, or something much better appears.
        """
        px, py = me["pos"][0], me["pos"][1]
        src = muzzle(me)
        best = None
        best_score = 1e30
        focus = self.focus_id
        focus_score = None
        focus_target = None
        for e in enemies:
            if e.get("pos") is None:
                continue
            d = math.hypot(e["pos"][0] - px, e["pos"][1] - py)
            if d > max_range:
                continue
            tc = self._center(e)
            if not self.w.shot_clear(src, tc):
                continue
            hp = e.get("hp")
            hp_conf = e.get("hp_conf", 1.0 if hp is not None else 0.0)
            score = d
            if hp is not None and hp_conf > 0.0:
                mx = _num(e.get("max_hp"), self.base_hp)
                score -= 45.0 * hp_conf * (1.0 - clamp(_num(hp) / max(1.0, mx), 0.0, 1.0))
            if focus is not None and e.get("id") == focus:
                focus_score, focus_target = score, e
            if score < best_score:
                best_score = score
                best = e
        if (focus_target is not None and self.focus_enabled
                and best_score > focus_score - self.focus_switch_margin):
            best = focus_target
        self.focus_id = best.get("id") if best is not None else None
        return best

    # ------------------------------------------------------------------ dispatch
    def act(self, obs, me, enemies, params, allow_fire=True):
        if params.get("aim_arbiter", False):
            return self._act_arbiter(obs, me, enemies, params, allow_fire)
        return self._act_legacy(obs, me, enemies, params, allow_fire)

    # ------------------------------------------------------------------ legacy
    def _act_legacy(self, obs, me, enemies, params, allow_fire=True):
        """Exact pre-arbiter behaviour, retained for controlled A/B."""
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

    # ------------------------------------------------------------------ arbiter
    def _act_arbiter(self, obs, me, enemies, params, allow_fire=True):
        """One final torso aim; each slot fires only if compatible with it."""
        p = params
        weapons = me["weapons"]
        src = muzzle(me)
        target = self.pick_target(me, enemies, p["fire_max_range"])
        if target is None:
            return None, [False, False], False

        tc = self._center(target)
        tv = target.get("vel", [0.0, 0.0, 0.0])
        tr = self._radius(target)
        min_pitch, max_pitch = self._pitch_limits(me)
        dt = self.dt
        fire_gate = bool(allow_fire and p["fire_enabled"])
        candidates = []

        def add(slot, kind, aim, point, tol, utility, fire, fired, hold=False, cone=None):
            candidates.append({
                "slot": slot, "kind": kind, "aim": (aim[0], clamp(aim[1], min_pitch, max_pitch)),
                "point": point, "tol": max(1e-3, tol), "utility": max(0.0, utility),
                "fire": bool(fire), "fired": bool(fired), "hold": bool(hold),
                "cone": cone,
            })

        # --- slot 0: gun ---------------------------------------------------
        w0 = weapons[0] if weapons else None
        if w0 and w0["kind"] == "gun":
            st = w0["stats"]
            pt, _ = intercept(src, tc, tv, st["speed"])
            yaw, pitch = aim_to(src, pt)
            fy, fp = self._future(me, yaw, pitch)
            err = shot_error(src, pt, fy, fp)
            spread = math.radians(_num(st.get("spread_deg"), 0.6)) * math.dist(src, pt)
            tol = tr * p["gun_min_hit"] + spread * 0.5
            hit_prob = clamp(1.0 - max(0.0, err - spread * 0.5) / tol, 0.0, 1.0)
            ready = (w0.get("ammo", 1) > 0 and w0.get("reload", 0) == 0
                     and w0.get("cooldown", 0) <= 0.05
                     and math.dist(src, pt) < _num(st.get("range"), 230.0))
            gate = fire_gate and ready
            add(0, "gun", (yaw, pitch), pt, tol,
                _num(st.get("damage"), 45.0) * hit_prob if gate else 0.0,
                True, gate and hit_prob > 0.05)

        # --- slot 1: laser / lightning / mortar ----------------------------
        w1 = weapons[1] if len(weapons) > 1 else None
        if w1:
            kind = w1["kind"]
            st = w1["stats"]
            if kind == "laser":
                charge = _num(w1.get("charge"), 0.0)
                full = max(1e-3, _num(st.get("charge"), 0.75))
                min_charge = max(p["laser_min_charge"], _num(st.get("min_charge"), 0.15))
                pt = (tc[0] + tv[0] * dt, tc[1] + tv[1] * dt, tc[2] + tv[2] * dt)
                yaw, pitch = aim_to(src, pt)
                fy, fp = self._future(me, yaw, pitch)
                err = shot_error(src, pt, fy, fp)
                aligned = err < tr * 1.15 and math.dist(src, pt) < _num(st.get("range"), 280.0)
                frac = (_num(st.get("min_frac"), 0.35)
                        + (1.0 - _num(st.get("min_frac"), 0.35)) * min(1.0, charge / full))
                dmg = _num(st.get("damage"), 315.0)
                if charge >= min_charge:
                    gate = fire_gate and aligned and w1.get("cooldown", 0) <= 0.05
                    utility = dmg * frac * (1.0 if aligned else 0.25)
                    # Release means fire[1]=False; holding means fire[1]=True.
                    add(1, "laser", (yaw, pitch), pt, tr * 1.15,
                        utility if gate else utility * 0.5,
                        not gate, gate, hold=not gate)
                elif charge < full and w1.get("cooldown", 0) <= 0.05 and fire_gate:
                    add(1, "laser", (yaw, pitch), pt, tr * 1.15,
                        dmg * 0.25 * (charge / full), True, False, hold=True)
            elif kind == "lightning":
                cone = math.radians(_num(st.get("cone_deg"), 30.0)) * 0.5
                d = math.dist(src, tc)
                yaw = math.atan2(tc[1] - src[1], tc[0] - src[0])
                pitch = clamp(0.0, min_pitch, max_pitch)
                fy, _ = self._future(me, yaw, pitch)
                yaw_err = abs(wrap(fy - yaw))
                hit_prob = clamp(1.0 - yaw_err / max(1e-3, cone), 0.0, 1.0)
                ready = (d < _num(st.get("range"), 45.0)
                         and me["energy"] > p["lightning_energy_floor"]
                         and w1.get("cooldown", 0) <= 0.05)
                gate = fire_gate and ready
                utility = _num(st.get("damage"), 60.0) * hit_prob - _num(st.get("energy"), 3.0) * 2.0
                add(1, "lightning", (yaw, pitch), tc, d * math.tan(cone) + tr,
                    utility if gate else 0.0, True, gate and hit_prob > 0.1, cone=cone)
            elif kind == "mortar":
                v = _num(st.get("speed"), 72.0)
                g = _num(st.get("gravity"), 22.0)
                splash_r = _num(st.get("splash_radius"), 7.0)
                # Two-pass moving-target lead using the low-arc flight time.
                pt = tc
                R = math.hypot(pt[0] - src[0], pt[1] - src[1])
                dz = pt[2] - src[2]
                for _ in range(2):
                    sol0 = mortar_pitch(R, dz, v, g)
                    if not sol0:
                        break
                    c = math.cos(sol0[0])
                    tt = R / (v * c) if c > 0.01 else 9.0
                    pt = (tc[0] + tv[0] * tt, tc[1] + tv[1] * tt, tc[2] + tv[2] * tt)
                    R = math.hypot(pt[0] - src[0], pt[1] - src[1])
                    dz = pt[2] - src[2]
                sol = mortar_pitch(R, dz, v, g)
                if sol and 30.0 < R < 210.0:
                    yaw = math.atan2(pt[1] - src[1], pt[0] - src[0])
                    for pitch in sol:
                        if not (min_pitch <= pitch <= max_pitch):
                            continue
                        c = math.cos(pitch)
                        if c <= 0.01:
                            continue
                        tt = R / (v * c)
                        clear = True
                        for k in range(1, 10):
                            f = k / 10.0
                            tf = tt * f
                            ax = src[0] + v * c * math.cos(yaw) * tf
                            ay = src[1] + v * c * math.sin(yaw) * tf
                            az = src[2] + v * math.sin(pitch) * tf - 0.5 * g * tf * tf
                            if self.w.solid(ax, ay, az):
                                clear = False
                                break
                        if not clear:
                            continue
                        ix = src[0] + v * c * math.cos(yaw) * tt
                        iy = src[1] + v * c * math.sin(yaw) * tt
                        self_d = math.hypot(ix - me["pos"][0], iy - me["pos"][1])
                        if self_d < splash_r + p["mortar_self_safe"]:
                            continue
                        fy, fp = self._future(me, yaw, pitch)
                        err = shot_error(src, (ix, iy, pt[2]), fy, fp)
                        tol = tr + splash_r
                        hit_prob = clamp(1.0 - err / tol, 0.0, 1.0)
                        gate = fire_gate and w1.get("cooldown", 0) <= 0.05
                        utility = (_num(st.get("damage"), 200.0)
                                   + _num(st.get("splash"), 160.0) * 0.5) * hit_prob
                        add(1, "mortar", (yaw, pitch), (ix, iy, pt[2]), tol,
                            utility if gate else 0.0, True, gate and hit_prob > 0.1)

        if not candidates:
            return None, [False, False], False

        # Prefer expected damage, then the smallest torso movement.
        for c in candidates:
            c["aim_cost"] = (abs(wrap(c["aim"][0] - me["aim"][0]))
                             + abs(c["aim"][1] - me["aim"][1]))
        chosen = max(candidates, key=lambda c: (c["utility"], -c["aim_cost"]))
        final_yaw, final_pitch = chosen["aim"]
        final_pitch = clamp(final_pitch, min_pitch, max_pitch)
        fy, fp = self._future(me, final_yaw, final_pitch)
        fire = [False, False]
        fired = False

        # Keep an in-progress laser charging rather than accidentally releasing
        # it along another weapon's aim.
        if any(c["kind"] == "laser" and c["hold"] for c in candidates):
            fire[1] = True

        fire[chosen["slot"]] = bool(chosen["fire"])
        if chosen["fired"] and (chosen["fire"] or (chosen["kind"] == "laser" and not chosen["hold"])):
            fired = True

        # A second slot may fire only when its own solution matches the one
        # torso aim we actually commanded.
        for c in candidates:
            if c is chosen or not c["fired"] or not c["fire"]:
                continue
            if c.get("cone") is not None:
                compatible = abs(wrap(fy - c["aim"][0])) <= c["cone"]
            else:
                compatible = shot_error(src, c["point"], fy, fp) <= c["tol"]
            if compatible:
                fire[c["slot"]] = True
                fired = True

        return [final_yaw, final_pitch], fire, fired
