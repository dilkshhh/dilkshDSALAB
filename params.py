"""Tunable policy knobs. A local A/B run overrides a subset by passing a dict to Brain().

The production image always uses DEFAULT (no environment variables are read at runtime).
"""
from __future__ import annotations

import json
import os

DEFAULT = {
    # --- zone rotation -------------------------------------------------
    "zone_margin": 0.78,          # stay inside this fraction of the current radius
    "goal_offset": 0.42,          # camp this fraction of next_radius away from next_center
    "goal_candidates": 12,        # candidate hide spots evaluated per decision
    "cover_bias": 0.55,           # weight on nearby solid cover when scoring a hide spot
    "threat_bias": 1.35,          # weight on distance from known threats
    "travel_bias": 0.30,          # weight on travel distance to a hide spot
    "slope_bias": 0.10,           # mild preference for higher ground
    "emergency_boost": True,      # boost while outside the circle / when the shrink is closing in
    "quiet_speed": 4.85,          # <= step_speed (5 m/s) makes no footstep sound
    "quiet_when_safe": True,      # move silently when no threat is close
    # --- engagement ----------------------------------------------------
    "aggression": 0.35,           # 0 = pure pacifist, 1 = fight anything in range
    "engage_range": 95.0,         # only consider fighting inside this range
    "fire_enabled": True,
    "fire_max_range": 175.0,
    "early_farm_until": 150.0,    # farm crates / NPCs / drops before this match time
    "late_survival_t": 250.0,     # after this, never shoot unless cornered
    "hp_floor": 0.28,             # below this HP fraction, disengage completely
    "retreat_hp": 0.55,
    "pressure_hide": 2,           # number of recent damage events that triggers hard hiding
    "face_threat": True,          # turn torso toward the attacker (front arc avoids x1.5)
    "scan_enabled": True,         # sweep the torso when idle to widen the vision wedge
    "scan_period_s": 7.0,
    # --- weapons -------------------------------------------------------
    "weapon_pref": ["laser", "mortar", "lightning", "gun"],
    "gun_min_hit": 1.25,          # fire only if predicted miss < this * target radius
    "laser_min_charge": 0.45,
    "mortar_self_safe": 11.0,     # never lob a shell whose impact is closer than this
    "lightning_energy_floor": 12.0,
    # --- economy -------------------------------------------------------
    "take_pickups": True,
    "crate_farm": False,          # shooting crates is loud (320 m gun sound)
    "npc_farm": False,            # NPC drones shoot back and make noise
    "npc_avoid": 42.0,            # keep this distance from drones
    "drop_aggression": 0.0,       # 0 = ignore supply drops, 1 = always contest
    "cube_detour": 26.0,          # max detour (m) to grab a loose cube
    "upgrade_plating": 10.0,
    "upgrade_armor": 8.5,
    "upgrade_nanites": 7.0,
    "upgrade_capacitor": 4.0,
    "upgrade_jets": 4.0,
    "upgrade_servos": 5.0,
    "upgrade_gyros": 4.5,
    "upgrade_sensors": 3.0,
    "upgrade_gun": 2.0,
    "upgrade_weapon": 2.5,
    # --- evasion -------------------------------------------------------
    "dodge_gain": 1.0,
    "dodge_lead_s": 0.65,
    "laser_dodge_gain": 1.0,
    "strafe_gain": 0.85,
    "stuck_speed": 1.2,           # moved < this many m over 2 s => replan
    # --- adaptive / final generalisation --------------------------------
    "adapt": True,                # modulate policy by observed opponent pressure
    "ffa_mode": False,            # simulator-only: opponents are independent, not a squad
}


def load(params=None):
    """Merge an optional override dict (and an optional BOT_PARAMS env JSON) over DEFAULT."""
    out = dict(DEFAULT)
    raw = os.environ.get("BOT_PARAMS")
    if raw:
        try:
            out.update(json.loads(raw))
        except (ValueError, TypeError):
            pass
    if params:
        out.update(params)
    return out


P = load()
