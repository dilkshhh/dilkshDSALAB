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
from econ import choose_take, held_kinds, loot_goal, pick_upgrade
from nav import Planner
from params import DEFAULT
from world import NullWorld, World
from zone import ZoneModel, current_circle, outside_amount

TAU = math.tau


class Brain:
    def __init__(self, hello, params=None):
        self.p = dict(DEFAULT)
        if params:
            self.p.update(params)
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
        self.combat = Combat(self.world, self.p)
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
        self.last_hp = 1400.0
        self.spotted = False
        self.last_fire_t = -1e9
        self.fire_count = 0

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
                b = e.get("bearing")
                if b is not None:
                    self.damage_bearings.append((b, t, float(e.get("amount", 0))))
        self.damage_bearings = [d for d in self.damage_bearings if t - d[1] < 6.0]

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

        if self.last_pos is not None:
            moved = math.hypot(me["pos"][0] - self.last_pos[0], me["pos"][1] - self.last_pos[1])
            if moved < 0.35:
                self.stuck_t += dt
            else:
                self.stuck_t = max(0.0, self.stuck_t - dt * 1.5)
        self.last_pos = list(me["pos"])
        self.last_hp = me["hp"]
        return me, t, dt

    def _threats(self, obs, me, t):
        """Enemy positions (visible + recent memory) and sound-derived points."""
        out = []
        x, y = me["pos"][0], me["pos"][1]
        for k, e in self.enemies.items():
            age = t - e["t"]
            px, py = e["pos"][0], e["pos"][1]
            # dead reckoning while out of sight
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

        # adaptive pressure: more hunters -> more conservative
        adapt = 1.0
        if p["adapt"]:
            adapt += min(1.2, self.recent_damage * 0.18)
            if t > p["late_survival_t"]:
                adapt += 0.5

        # ---- goal -------------------------------------------------------
        goal, emergency = self.zone.choose_goal(obs, me, self.world, threats, p, t)
        (ccx, ccy), cr = current_circle(obs["zone"], t)
        out_by = outside_amount(x, y, (ccx, ccy), cr)
        if out_by > -0.12 * cr:
            emergency = True
            goal = (ccx, ccy)

        # economy detours only when safe and early
        if not emergency and close > 55.0 and t < p["late_survival_t"]:
            lg = loot_goal(obs, me, p, self.world, threats, t)
            if lg is not None:
                goal = lg

        # ---- movement ---------------------------------------------------
        if self.path_goal is None or math.hypot(goal[0] - self.path_goal[0], goal[1] - self.path_goal[1]) > 18.0 \
                or t - self.path_t > 3.5 or self.stuck_t > 0.8:
            self.path = self.nav.path(x, y, goal[0], goal[1], budget=2600)
            self.path_goal = goal
            self.path_t = t
            if self.stuck_t > 0.8:
                self.stuck_t = 0.0
        mvx, mvy = self.nav.steer(x, y, goal[0], goal[1], z, self.path)

        # dodge incoming fire and telegraphed lasers
        from combat import dodge_vector, laser_dodge
        dvx, dvy = dodge_vector(me, obs.get("projectiles", []), p)
        lvx, lvy = laser_dodge(me, visible, p)
        mx = mvx + dvx * 1.4 + lvx * 1.2
        my = mvy + dvy * 1.4 + lvy * 1.2

        # keep away from NPC drones (they shoot, and killing them is loud)
        for npc in obs.get("mechs", []):
            if npc.get("kind") != "npc":
                continue
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

        # quiet movement: <= step_speed makes no footstep sound
        speed_scale = 1.0
        quiet = p["quiet_when_safe"] and not emergency and close > 70.0 and t < p["late_survival_t"]
        if quiet:
            speed_scale = min(1.0, p["quiet_speed"] / max(1.0, self.walk_speed))
        boost = bool(p["emergency_boost"] and (emergency or (hp_frac < 0.25 and mclose < 30.0)))
        if boost:
            speed_scale = 1.0
        move = [mx * speed_scale, my * speed_scale]

        # ---- firing gate -------------------------------------------------
        cornered = mclose < 32.0 and hp_frac > p["hp_floor"]
        engage_dist = p["engage_range"] * p["aggression"] / adapt
        if t > p["late_survival_t"]:
            engage_dist = min(engage_dist, 38.0)
        allow_fire = (p["fire_enabled"] and not emergency and hp_frac > p["hp_floor"]
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
        pick = pick_upgrade(obs.get("offer"), p, me)
        if pick is not None:
            act["pick"] = pick
        # weapon pickup
        take, drop = choose_take(obs, me, p)
        if take is not None:
            act["take"] = take
            if drop is not None:
                act["drop"] = drop
        return act
