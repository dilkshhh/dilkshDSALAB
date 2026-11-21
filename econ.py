"""Loot, cubes, supply drops and upgrade valuation."""
from __future__ import annotations

import math


def upgrade_value(choice, params):
    uid = choice.get("id", "")
    if uid.startswith("plating"):
        return params["upgrade_plating"]
    if uid.startswith("armor"):
        return params["upgrade_armor"]
    if uid.startswith("nanites"):
        return params["upgrade_nanites"]
    if uid.startswith("capacitor"):
        return params["upgrade_capacitor"]
    if uid.startswith("jets"):
        return params["upgrade_jets"]
    if uid.startswith("servos"):
        return params["upgrade_servos"]
    if uid.startswith("gyros"):
        return params["upgrade_gyros"]
    if uid.startswith("sensors"):
        return params["upgrade_sensors"]
    if uid.startswith("gun_"):
        return params["upgrade_gun"]
    return params["upgrade_weapon"]


def pick_upgrade(offer, params, me):
    if not offer or not offer.get("choices"):
        return None
    hp_frac = me["hp"] / max(1.0, me["max_hp"])
    best_i, best_v = 0, -1e30
    for i, ch in enumerate(offer["choices"]):
        v = upgrade_value(ch, params)
        # when badly hurt, healing matters more than raw max HP
        if ch.get("id", "").startswith("nanites") and hp_frac < 0.5:
            v += 2.0
        if v > best_v:
            best_v, best_i = v, i
    return best_i


def held_kinds(me):
    return [w["kind"] for w in me["weapons"] if w]


def choose_take(obs, me, params):
    """Return (pickup_id, drop_slot) or (None, None)."""
    if not params["take_pickups"]:
        return None, None
    x, y, z = me["pos"]
    reach = 4.0
    held = held_kinds(me)
    empty = 1 if len(me["weapons"]) > 1 and me["weapons"][1] is None else None
    pref = params["weapon_pref"]
    best = None
    best_key = None
    for p in obs.get("pickups", []):
        kind = p["kind"]
        if kind in held:
            continue
        px, py, pz = p["pos"]
        if math.hypot(px - x, py - y) > reach or abs(pz - z) > 4.0:
            continue
        try:
            rank = pref.index(kind)
        except ValueError:
            rank = 99
        key = (rank, math.hypot(px - x, py - y))
        if best_key is None or key < best_key:
            best_key, best = key, p
    if best is None:
        return None, None
    if empty is not None:
        return best["id"], None
    # both slots full: replace slot 1 unless the new weapon is better than slot 1
    slot1 = me["weapons"][1]
    cur_rank = pref.index(slot1["kind"]) if slot1["kind"] in pref else 99
    new_rank = pref.index(best["kind"]) if best["kind"] in pref else 99
    if new_rank >= cur_rank:
        return None, None
    return best["id"], 1


def loot_goal(obs, me, params, world, threats, t):
    """Pick a nearby economic objective worth a small detour. Returns (x,y) or None."""
    x, y, z = me["pos"]
    p = params
    cands = []

    for c in obs.get("cubes", []):
        cx, cy = c["pos"][0], c["pos"][1]
        d = math.hypot(cx - x, cy - y)
        if d < p["cube_detour"] and abs(c["pos"][2] - z) < 6.0:
            cands.append((-d * 0.35 + 14.0, cx, cy, "cube"))

    for pk in obs.get("pickups", []):
        cx, cy = pk["pos"][0], pk["pos"][1]
        d = math.hypot(cx - x, cy - y)
        if d < 30.0 and pk["kind"] not in held_kinds(me) and me["weapons"][1] is None:
            cands.append((-d * 0.4 + 18.0, cx, cy, "pickup"))

    if p["crate_farm"] and t < p["early_farm_until"]:
        for cr in obs.get("crates", []):
            cx, cy = cr["pos"][0], cr["pos"][1]
            d = math.hypot(cx - x, cy - y)
            if d < 90.0:
                cands.append((-d * 0.5 + 10.0, cx, cy, "crate"))

    if p["npc_farm"] and t < p["early_farm_until"]:
        for e in obs.get("mechs", []):
            if e["kind"] != "npc":
                continue
            cx, cy = e["pos"][0], e["pos"][1]
            d = math.hypot(cx - x, cy - y)
            if d < 70.0:
                cands.append((-d * 0.5 + 8.0, cx, cy, "npc"))

    if p["drop_aggression"] > 0.0:
        for dr in obs.get("drops", []):
            if dr.get("lands_in", 99) > 12.0:
                continue
            holder = dr.get("holder")
            if holder is not None and holder != me["id"]:
                continue
            cx, cy = dr["pos"][0], dr["pos"][1]
            d = math.hypot(cx - x, cy - y)
            near_enemy = min((math.hypot(t[0] - cx, t[1] - cy) for t in threats), default=999.0)
            if d < 120.0 and near_enemy > 45.0 / max(0.1, p["drop_aggression"]):
                cands.append((-d * 0.6 + 26.0 * p["drop_aggression"], cx, cy, "drop"))

    if not cands:
        return None
    cands.sort(reverse=True)
    score, cx, cy, kind = cands[0]
    if score < 0:
        return None
    # do not walk into a wall for loot
    if world.blocked(cx, cy, world.ground(cx, cy), 9.0):
        return None
    return (cx, cy)
