"""Survival-first decision core.

Priority order: stay in the zone > avoid being found > keep HP > take free
economy > fight only when cornered. Torso facing is independent of leg
movement, so we can retreat while keeping our front arc toward the threat.
"""
from __future__ import annotations

import math
import os
import random

from combat import Combat, clamp, wrap, size_scale, target_center
from cover import find_cover
from econ import choose_take, held_kinds, loot_goal, pick_upgrade, seek_goal
from intel import Intel
from nav import Planner, safe_heading
from params import load
from world import NullWorld, World
from zone import ZoneModel, current_circle, outside_amount

TAU = math.tau


class Brain:
    def __init__(self, hello, params=None):
        # load() also honours BOT_PARAMS, which is how local A/B variants are
        # injected into a protocol-speaking child process.
        self.p = load(params)
        self.intel_enabled = bool(self.p.get("intel_enabled", True))
        self.seed = int(hello.get("seed", 0))
        self.rng = random.Random(self.seed)
        self.slot = int(hello.get("slot", 0))
        cfg = hello.get("config", {})
        self.cfg = cfg
        md = hello.get("map", {}).get("dir") or ""
        if not os.path.isdir(os.path.join(md, "v2")):
            md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arena")
        if not os.path.isdir(os.path.join(md, "v2")):
            md = "/arena"
        try:
            self.world = World(md)
        except Exception as exc:  # never let a missing map turn us into a sitting target
            import sys
            print("map unavailable (%s): running without arena geometry" % exc,
                  file=sys.stderr, flush=True)
            self.world = NullWorld()
        self.nav = Planner(self.world)
        self.zone = ZoneModel(cfg, self.seed)
        self.intel = Intel(hello, self.world, self.p)
        self.combat = Combat(self.world, self.p, cfg)
        self.memory_s = float(cfg.get("vision", {}).get("memory_s", 5.0))
        self.vision_range = float(cfg.get("vision", {}).get("range", 200.0))
        self.near_range = float(cfg.get("vision", {}).get("near_range", 45.0))
        self.walk_speed = float(cfg.get("mech", {}).get("walk_speed", 11.7))
        self.step_speed = float(cfg.get("sound", {}).get("step_speed", 5.0))
        self.max_pitch = float(cfg.get("mech", {}).get("max_pitch", 1.3))
        self.min_pitch = float(cfg.get("mech", {}).get("min_pitch", -0.7))

        self.enemies = {}          # id -> {pos, vel, t, hp, weapons, charging, aim}
        self.last_t = -1.0
        self.last_pos = None
        self.path = []
        self.path_goal = None
        self.path_t = -1e9
        self.stuck_t = 0.0
        self.recent_damage = 0.0
        self.damage_bearings = []
        self.sound_points = []
        self.sound_pressure = 0.0
        self.sound_bearing = None
        self.sectors = []
        self.last_hp = 1400.0
        self.spotted = False
        self.last_fire_t = -1e9
        self.fire_count = 0
        self.escape_dir = None
        self.escape_until = -1.0
        self.last_reach = 13.0
        self.flee_dir = None
        self.flee_until = -1.0
        self.pos_hist = []
        self.cover_cache = None
        self.cover_cache_t = -1e9
        self.last_damage_t = -1e9
        self.kite_dir = None
        self.kite_until = -1.0

    # ------------------------------------------------------------------ state
    def _update(self, obs):
        me = obs["self"]
        t = float(obs["t"])
        dt = 0.1 if self.last_t < 0 else max(0.05, min(0.5, t - self.last_t))
        self.last_t = t
        self.recent_damage = max(0.0, self.recent_damage - dt * 0.55)

        for e in obs.get("events", []):
            if e.get("type") == "damaged":
                self.recent_damage += 1.0
                self.last_damage_t = t
                b = e.get("bearing")
                if b is not None:
                    self.damage_bearings.append((b, t, float(e.get("amount", 0))))
        self.damage_bearings = [d for d in self.damage_bearings if t - d[1] < 6.0]

        if self.intel_enabled:
            # D1: `obs.mechs` positions are already the server's real current
            # positions for `vision.memory_s`; do not dead-reckon them.
            # D2: sounds/beams/events become uncertain bearing sectors, not
            # exact pseudo-positions.
            self.intel.update(obs)
            self.sectors = self.intel.sector_contacts()
            self.sound_pressure = self.intel.sound_pressure()
            self.sound_bearing = self.intel.sound_bearing()
        else:
            # Legacy path, retained unchanged for paired ablations.
            for m in obs.get("mechs", []):
                if m.get("kind") != "mech":
                    continue
                self.enemies[int(m["id"])] = {
                    "pos": list(m["pos"]), "vel": list(m.get("vel", [0, 0, 0])),
                    "t": t, "hp": m.get("hp", 1400), "cubes": m.get("cubes", 0),
                    "weapons": m.get("weapons", []), "charging": m.get("charging", False),
                    "aim": list(m.get("aim", [0, 0])),
                }
            for k in list(self.enemies):
                if t - self.enemies[k]["t"] > self.memory_s:
                    del self.enemies[k]

            pts = []
            for s in obs.get("sounds", []):
                kind = s.get("kind", "")
                if kind in ("step", "boost", "jet", "reload", "npc_gun", "crate", "drop"):
                    continue
                b = s.get("bearing")
                if b is None:
                    continue
                cat = s.get("dist")
                dist = 55.0 if cat == "near" else (135.0 if cat == "mid" else 210.0)
                pts.append((me["pos"][0] + math.cos(b) * dist,
                            me["pos"][1] + math.sin(b) * dist, t, kind))
            self.sound_points = [p for p in self.sound_points if t - p[2] < 4.0] + pts
            self.sectors = []
            self.sound_pressure = 0.0
            self.sound_bearing = None

        if self.last_pos is not None:
            moved = math.hypot(me["pos"][0] - self.last_pos[0], me["pos"][1] - self.last_pos[1])
            if moved < 0.35:
                self.stuck_t += dt
            else:
                self.stuck_t = max(0.0, self.stuck_t - dt * 1.5)
        self.last_pos = list(me["pos"])
        self.last_hp = me["hp"]
        self.pos_hist.append((t, me["pos"][0], me["pos"][1]))
        if len(self.pos_hist) > 40:
            self.pos_hist = self.pos_hist[-40:]
        return me, t, dt

    def _threats(self, obs, me, t):
        """Protocol-current enemy positions only, or legacy pseudo-points."""
        if self.intel_enabled:
            return self.intel.threat_points()
        out = []
        x, y = me["pos"][0], me["pos"][1]
        for k, e in self.enemies.items():
            age = t - e["t"]
            px, py = e["pos"][0], e["pos"][1]
            # legacy dead reckoning while out of sight
            px += e["vel"][0] * min(age, 2.0)
            py += e["vel"][1] * min(age, 2.0)
            out.append((px, py))
        for sp in self.sound_points:
            if t - sp[2] < 3.0:
                out.append((sp[0], sp[1]))
        for b, bt, amt in self.damage_bearings:
            if t - bt < 3.0:
                out.append((x + math.cos(b) * 60.0, y + math.sin(b) * 60.0))
        return out

    def _visible_enemies(self, obs, me, t):
        if self.intel_enabled:
            return self.intel.visible_dicts()
        out = []
        for k, e in self.enemies.items():
            if t - e["t"] <= 0.25:
                d = dict(e)
                d["id"] = k
                out.append(d)
        return out

    # ------------------------------------------------------------------ decide
    def act(self, obs):
        p = self.p
        me, t, dt = self._update(obs)
        x, y, z = me["pos"]
        hp_frac = me["hp"] / max(1.0, me["max_hp"])
        threats = self._threats(obs, me, t)
        visible = self._visible_enemies(obs, me, t)
        close = min((math.hypot(q[0] - x, q[1] - y) for q in threats), default=1e6)
        mclose = min((math.hypot(e["pos"][0] - x, e["pos"][1] - y) for e in visible), default=1e6)
        npcs = [m for m in obs.get("mechs", []) if m.get("kind") == "npc"]
        npc_close = min((math.hypot(m["pos"][0] - x, m["pos"][1] - y) for m in npcs),
                        default=1e6)
        npc_near = min(npcs, key=lambda m: math.hypot(m["pos"][0] - x, m["pos"][1] - y)) \
            if npcs else None
        # net displacement over the last 2.5 s: catches orbiting a hide spot,
        # which a per-decision "stuck" check cannot see.
        net = 0.0
        for q in self.pos_hist:
            if t - q[0] >= 2.0:
                net = math.hypot(x - q[1], y - q[2])
                break

        # adaptive pressure: more hunters -> more conservative
        adapt = 1.0
        if p["adapt"]:
            adapt += min(1.2, self.recent_damage * 0.18)
            if self.intel_enabled:
                adapt += min(0.8, self.sound_pressure * p["sound_pressure_gain"])
            if t > p["late_survival_t"]:
                adapt += 0.5

        # ---- goal -------------------------------------------------------
        (ccx, ccy), cr = current_circle(obs["zone"], t)
        goal_threats = threats + [(m["pos"][0], m["pos"][1]) for m in npcs]
        goal, emergency = self.zone.choose_goal(
            obs, me, self.world, goal_threats, p, t,
            sectors=self.sectors if self.intel_enabled else None)
        out_by = outside_amount(x, y, (ccx, ccy), cr)
        if out_by > -0.12 * cr:
            emergency = True
            goal = (ccx, ccy)

        # ---- drone aggro break -------------------------------------------
        # Drones aggro at 45 m, deal 25/s and never lose interest while we
        # orbit a nearby hide spot.  Sprinting out of their 60 m chase leash
        # is quieter (90 m boost sound) than shooting them (320 m gun sound).
        if (npc_near is not None and npc_close < p["npc_break_range"]
                and (self.recent_damage > 0.05 or npc_close < 26.0)):
            fx, fy = x - npc_near["pos"][0], y - npc_near["pos"][1]
            fd = math.hypot(fx, fy) or 1.0
            self.flee_dir = (fx / fd, fy / fd)
            self.flee_until = t + p["npc_break_hold_s"]
        if t < self.flee_until and self.flee_dir is not None:
            fx, fy = self.flee_dir
            gx, gy = x + fx * 120.0, y + fy * 120.0
            dd = math.hypot(gx - ccx, gy - ccy)
            lim = cr * 0.82
            if dd > lim and dd > 0.01:
                gx = ccx + (gx - ccx) / dd * lim
                gy = ccy + (gy - ccy) / dd * lim
            goal, emergency = (gx, gy), False

        # ---- early roam / economy ----------------------------------------
        roaming = (t < p["roam_until"] and not emergency
                   and not (t < self.flee_until))
        goal_kind = "zone"
        if roaming:
            goal, goal_kind = seek_goal(obs, me, p, self.world, goal_threats, t,
                                        (ccx, ccy), cr, self.seed)
        else:
            # small detours only when safe and early
            if not emergency and close > 55.0 and t < p["late_survival_t"]:
                lg = loot_goal(obs, me, p, self.world, goal_threats, t)
                if lg is not None:
                    goal, goal_kind = lg, "loot"

        # ---- LOS-breaking cover -------------------------------------------
        # Squad vision is shared; distance-hiding fails, occlusion works.
        covered = False
        if (p["cover_enabled"] and not emergency and not (t < self.flee_until)
                and (hp_frac < p["cover_hp"] or self.recent_damage > p["cover_after_hit"])
                and mclose > p["cover_min_enemy"] and t - self.last_damage_t < 20.0):
            if t - self.cover_cache_t > p["cover_cache_s"]:
                eyes = sorted(
                    ((e["pos"][0], e["pos"][1], e["pos"][2] + 8.0) for e in visible),
                    key=lambda q: math.hypot(q[0] - x, q[1] - y))
                for b, bt, amt in self.damage_bearings[-2:]:
                    tx, ty = x + math.cos(b) * 70.0, y + math.sin(b) * 70.0
                    eyes.append((tx, ty, self.world.ground(tx, ty) + 8.0))
                if not eyes:
                    eyes = [(q[0], q[1], self.world.ground(q[0], q[1]) + 8.0)
                            for q in threats[:2]]
                self.cover_cache = find_cover(self.world, x, y, z, eyes,
                                              p["cover_max_r"],
                                              zone_center=(ccx, ccy), zone_radius=cr)
                self.cover_cache_t = t
            if self.cover_cache is not None:
                goal = self.cover_cache
                covered = True

        # ---- kiting ------------------------------------------------------
        # The squad converges on our last known position and needs LOS to
        # shoot.  Boost straight away from the incoming-fire bearings, then
        # go quiet again; they arrive at a position we have already left.
        kiting = False
        recent_hits = [d for d in self.damage_bearings if t - d[1] < 3.0]
        if (p["kite_enabled"] and not emergency and not (t < self.flee_until)
                and recent_hits and (hp_frac < p["kite_hp"] or len(recent_hits) >= 2)):
            vx = -sum(math.cos(d[0]) * (1.0 + min(d[2], 200.0) / 200.0) for d in recent_hits)
            vy = -sum(math.sin(d[0]) * (1.0 + min(d[2], 200.0) / 200.0) for d in recent_hits)
            vd = math.hypot(vx, vy) or 1.0
            self.kite_dir = (vx / vd, vy / vd)
            self.kite_until = t + p["kite_hold_s"]
        if t < self.kite_until and self.kite_dir is not None:
            kx, ky = self.kite_dir
            gx, gy = x + kx * 130.0, y + ky * 130.0
            dd = math.hypot(gx - ccx, gy - ccy)
            lim = cr * 0.82
            if dd > lim and dd > 0.01:
                gx = ccx + (gx - ccx) / dd * lim
                gy = ccy + (gy - ccy) / dd * lim
            goal, goal_kind = (gx, gy), "kite"
            covered, roaming, kiting = False, False, True

        # a hide spot we are already standing on is not a goal: stop orbiting
        if covered:
            deadzone = 1.8
        elif goal_kind in ("weapon", "cube", "crate", "npc", "loot"):
            deadzone = 2.5        # get inside the 4 m pickup radius
        else:
            deadzone = 12.0
        at_goal = math.hypot(goal[0] - x, goal[1] - y) < deadzone

        # ---- movement ---------------------------------------------------
        if self.path_goal is None or math.hypot(goal[0] - self.path_goal[0], goal[1] - self.path_goal[1]) > 18.0 \
                or t - self.path_t > 3.5 or self.stuck_t > 0.8:
            self.path = self.nav.path(x, y, goal[0], goal[1], budget=2600)
            self.path_goal = goal
            self.path_t = t
            if self.stuck_t > 0.8:
                self.stuck_t = 0.0
        mvx, mvy = self.nav.steer(x, y, goal[0], goal[1], z, self.path)
        if at_goal and not emergency and not (t < self.flee_until):
            mvx, mvy = 0.0, 0.0

        # dodge incoming fire and telegraphed lasers
        from combat import dodge_vector, laser_dodge
        dvx, dvy = dodge_vector(me, obs.get("projectiles", []), p)
        lvx, lvy = laser_dodge(me, visible, p)
        mx = mvx + dvx * 1.4 + lvx * 1.2
        my = mvy + dvy * 1.4 + lvy * 1.2

        # keep away from NPC drones (they shoot, and killing them is loud)
        for npc in npcs:
            nx, ny = npc["pos"][0] - x, npc["pos"][1] - y
            nd = math.hypot(nx, ny)
            if 0.1 < nd < p["npc_avoid"]:
                w = (1.0 - nd / p["npc_avoid"]) * 0.9
                mx -= nx / nd * w
                my -= ny / nd * w

        # strafe instead of walking straight at a shooter
        if mclose < 55.0 and visible and not emergency:
            e = min(visible, key=lambda q: math.hypot(q["pos"][0] - x, q["pos"][1] - y))
            ex, ey = e["pos"][0] - x, e["pos"][1] - y
            ed = max(0.01, math.hypot(ex, ey))
            sx, sy = -ey / ed, ex / ed
            mx += sx * p["strafe_gain"] * (1.0 - mclose / 70.0)
            my += sy * p["strafe_gain"] * (1.0 - mclose / 70.0)

        md = math.hypot(mx, my)
        if md > 1e-5:
            mx, my = mx / md, my / md
        else:
            mx, my = 0.0, 0.0

        # ---- stuck escape ------------------------------------------------
        # A wedged mech dies to a single NPC drone in ~56 s.  When we stop
        # making progress, commit to one high-clearance heading for a while
        # instead of re-deciding every 100 ms (which just oscillates).
        # Priority: break drone contact > escape a geometric trap > normal steer.
        override = None
        if t < self.flee_until and self.flee_dir is not None:
            override = self.flee_dir
        elif t < self.escape_until and self.escape_dir is not None:
            override = self.escape_dir
        elif (self.stuck_t > 0.7
              or (net < 8.0 and math.hypot(goal[0] - x, goal[1] - y) > 30.0
                  and self.recent_damage > 0.1)):
            best, best_score = None, -1e18
            ox = sum(q[1] for q in self.pos_hist) / max(1, len(self.pos_hist))
            oy = sum(q[2] for q in self.pos_hist) / max(1, len(self.pos_hist))
            for k in range(16):
                a = k * TAU / 16.0
                cx, cy = math.cos(a), math.sin(a)
                reach = self.nav.reach(x, y, z, cx, cy)
                qx, qy = x + cx * 14.0, y + cy * 14.0
                away = min((math.hypot(qx - q[0], qy - q[1]) for q in goal_threats),
                           default=120.0)
                # move away from the pocket we have been orbiting
                outward = math.hypot(qx - ox, qy - oy)
                score = reach + min(away, 120.0) * 0.025 + outward * 0.06
                if score > best_score:
                    best_score, best = score, (cx, cy)
            self.escape_dir = best or (mx, my)
            self.escape_until = t + p["escape_hold_s"]
            self.stuck_t = 0.3
            override = self.escape_dir
        escaping = override is not None
        if escaping:
            mx, my = override

        # Always re-validate the *composed* vector: dodges and NPC repulsion
        # can rotate a clear steering heading into a wall.
        (mx, my), reach = safe_heading(self.world, x, y, z, mx, my)
        self.last_reach = reach
        if reach < 2.0 and self.escape_dir is not None:
            self.escape_until = -1.0

        # quiet movement: <= step_speed makes no footstep sound
        speed_scale = 1.0
        quiet = (p["quiet_when_safe"] and not emergency and close > 70.0
                 and npc_close > 55.0 and t < p["late_survival_t"] and not escaping
                 and not roaming and not kiting)
        if quiet:
            speed_scale = min(1.0, p["quiet_speed"] / max(1.0, self.walk_speed))
        boost = bool(p["emergency_boost"] and (emergency or (hp_frac < 0.25 and mclose < 30.0)))
        # NPC drones move at 5 m/s; a quiet 4.85 m/s walk cannot break aggro.
        # Sprint out of their leash instead of eating 25 damage every second.
        npc_aggro = npc_close < 38.0 and (self.recent_damage > 0.05 or escaping)
        if (escaping or npc_aggro or kiting) and me.get("energy", 0) > 25:
            boost = True
        if boost:
            speed_scale = 1.0
        if covered and p["cover_quiet"] and not escaping:
            # footsteps are silent below step_speed, and boost is audible at 90 m
            speed_scale = min(speed_scale, p["quiet_speed"] / max(1.0, self.walk_speed))
            boost = False

        # ---- firing gate -------------------------------------------------
        cornered = mclose < 32.0 and hp_frac > p["hp_floor"]
        engage_dist = p["engage_range"] * p["aggression"] / adapt
        if t > p["late_survival_t"]:
            engage_dist = min(engage_dist, 38.0)
        allow_fire = (p["fire_enabled"] and not emergency and hp_frac > p["hp_floor"]
                      and (not covered or cornered)
                      and (mclose < engage_dist or cornered)
                      and (self.recent_damage > 0.2 or mclose < 40.0 or p["aggression"] > 0.6))
        # crate / NPC farming is opt-in and only when nothing else is happening
        combat_targets = list(visible)
        farm = False
        if not allow_fire and t < p["early_farm_until"] and mclose > 110.0 and not emergency:
            if p["crate_farm"]:
                for cr in obs.get("crates", []):
                    d = math.hypot(cr["pos"][0] - x, cr["pos"][1] - y)
                    if d < 90.0 and self.world.shot_clear((x, y, z + 7), cr["pos"]):
                        combat_targets.append({"id": cr["id"], "kind": "mech",
                                               "pos": [cr["pos"][0], cr["pos"][1], cr["pos"][2] - 3.3],
                                               "vel": [0, 0, 0], "hp": cr.get("hp", 300),
                                               "cubes": 0, "weapons": [], "aim": [0, 0],
                                               "charging": False})
                        farm = True
                        break
            if p["npc_farm"] and not farm:
                for npc in obs.get("mechs", []):
                    if npc.get("kind") != "npc":
                        continue
                    d = math.hypot(npc["pos"][0] - x, npc["pos"][1] - y)
                    if d < 60.0:
                        combat_targets.append({"id": npc["id"], "kind": "mech",
                                               "pos": [npc["pos"][0], npc["pos"][1], npc["pos"][2] - 2.75],
                                               "vel": list(npc.get("vel", [0, 0, 0])),
                                               "hp": npc.get("hp", 350), "cubes": 0,
                                               "weapons": [], "aim": [0, 0], "charging": False})
                        farm = True
                        break
        if farm:
            allow_fire = True

        aim_cmd, fire, fired = self.combat.act(obs, me, combat_targets, p, allow_fire=allow_fire)
        if fired:
            self.last_fire_t = t
            self.fire_count += 1

        # ---- torso: face the threat (front arc), otherwise scan ----------
        aim_yaw, aim_pitch = me["aim"][0], me["aim"][1]
        if aim_cmd is not None:
            aim_yaw, aim_pitch = aim_cmd[0], clamp(aim_cmd[1], self.min_pitch, self.max_pitch)
        elif p["face_threat"] and threats:
            tx, ty = min(threats, key=lambda q: math.hypot(q[0] - x, q[1] - y))
            aim_yaw = math.atan2(ty - y, tx - x)
            aim_pitch = 0.0
        elif p["scan_enabled"]:
            base = math.atan2(my, mx) if md > 1e-5 else (self.seed % 628) / 100.0
            if self.intel_enabled and p["sound_scan"] and self.sound_bearing is not None:
                base = self.sound_bearing
            aim_yaw = base + 0.55 * math.sin(t / max(1.0, p["scan_period_s"]) * TAU)
            aim_pitch = 0.0
        else:
            aim_yaw = math.atan2(my, mx) if md > 1e-5 else me["aim"][0]

        act = {
            "move": [round(mx * speed_scale, 4), round(my * speed_scale, 4)],
            "boost": boost,
            "aim": [round(aim_yaw, 4), round(clamp(aim_pitch, self.min_pitch, self.max_pitch), 4)],
            "fire": [bool(fire[0]), bool(fire[1])],
        }
        # unstick / climb: jump if we have been wedged for a while
        if self.stuck_t > 1.4 and me.get("grounded"):
            act["jump"] = True
        # reload early when the magazine is dry and no target is in sight
        w0 = me["weapons"][0] if me["weapons"] else None
        if w0 and w0.get("kind") == "gun" and w0.get("ammo", 12) == 0 and w0.get("reload", 0) == 0:
            act["reload"] = True
        # upgrade offer
        pick = pick_upgrade(obs.get("offer"), p, me, self.cfg)
        if pick is not None:
            act["pick"] = pick
        # weapon pickup
        take, drop = choose_take(obs, me, p)
        if take is not None:
            act["take"] = take
            if drop is not None:
                act["drop"] = drop
        if os.environ.get("BOT_DEBUG") and int(obs.get("tick", 0)) % 20 == 0:
            import sys
            print("DBG t=%.1f pos=(%.0f,%.0f) goal=(%.0f,%.0f) mv=(%.2f,%.2f) "
                  "reach=%.0f stuck=%.2f esc=%s npc=%.0f threats=%d hp=%.0f fire=%s"
                  % (t, x, y, goal[0], goal[1], mx, my, reach, self.stuck_t,
                     escaping, npc_close, len(threats), me["hp"], str(fire)),
                  file=sys.stderr, flush=True)
        return act
