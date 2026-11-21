# EXPERIMENTS — the full ledger

> Living document. Last updated **2026-11-21 22:50 UTC**.
>
> Every entry: what changed, what was expected, what was measured, what was
> decided. Deltas are **paired local score differences** in the simulator, not
> official points. Negative results are kept deliberately — they are the only
> thing preventing the next agent from repeating them.

## How to read this

- `n=` is paired matches. A valid claim needs **n ≥ 48 across ≥ 3 seed ranges**,
  per-range deltas reported, and a holdout.
- Effects under ~0.5 are **unresolvable** at feasible sample sizes. They are
  recorded as "inconclusive", never as wins.
- Baselines drift between sessions because the working tree changes. Each entry
  records its own baseline.

Baselines used below, 48 matches unless stated:

| Set | Score | Death | Kills |
| --- | --- | --- | --- |
| train (8000/11000/13000) | 1.83–1.96 | 71–74 s | 1.19–1.27 |
| holdout (14000/15000/16000) | 1.65–1.96 | 66–72 s | 1.17–1.33 |

---

## Adopted

### E1 — Exact upgrade valuation, first (mobility-heavy) weights · `f78d3f5`
Read marginal effects from `hello.config.upgrades` instead of hand-assigned ranks.
First weights over-valued mobility and aim: **−0.33 ± 0.17** (24 pairs, harsh
opponents), **−0.08 ± 0.25** (mild). Rejected the weights, kept the mechanism.

### E2 — Exact upgrade valuation, survival-weighted retune · `f78d3f5`
**+0.04 ± 0.09** (24 pairs) / **0.00 ± 0.12**. Neutral. Retained for protocol
correctness: the bot now adapts to balance patches instead of assuming them.

### E3 — Protocol-first belief layer (D1/D2) · `7addbb2`
Stopped dead-reckoning server-tracked positions; turned sound bearings into
uncertain sectors with live σ. **+0.04 ± 0.07** (24 pairs). Neutral, but it removes
a fabricated-precision bug and feeds the arbiter. Retained.

### E4 — Single torso-aim arbiter (D3) · `7addbb2`
One final aim for both weapon slots; a second slot fires only if its shot still
lands given that aim. **+0.54 ± 0.28** (harsh) / **+0.71 ± 0.59** (mild). Retained.

### E5 — D1+D2+D3 combined · `7addbb2`
**+0.63 ± 0.25** / **+1.50 ± 0.40**. Much better than the parts. Retained.

### E6 — 1 m engine-accurate collision + composed-heading validation · `5ab07e7`
Per-column solid tops and bridge overhangs, 9-point body ring, revalidation of the
*composed* steering vector. Fixed a hard wedging bug where the mech was farmed to
death by a single NPC drone at t≈70 s. Adopted as correctness.

### E7 — Aggression and hunt mode · `407c50e`, `7468dcb`
Aggression 0.95 → **0.00**; 0.7 → **−0.31**. Rejected.
Hunt mode v1 (close on the nearest known enemy) measured **neutral locally** and
**+0.61 officially** (1.83 → 2.44). Hunt v2 (target the weakest, standoff 45 m) was
submitted as `7468dcb` and scored higher again; exact number never recorded.
**This is the calibration anchor for F10.**

### E8 — Squad kiting · `84e97cb`
Boost away from incoming-fire bearings, hold ~6 s, prefer headings that put terrain
between us and the shooters. **+0.55 ± 0.27**, death 80 → 105 s. Retained.
Hold 8 s vs 5 s: 0.00. Hold 14 s vs 8 s: **−0.21 ± 0.13**, rejected (over-commits).

### E9 — Quiet movement · `84e97cb`
Full speed vs quiet (≤ `step_speed` = 4.85 m/s): quiet is **+0.67**. Footsteps are
audible at 40 m, boost at 90 m. Retained.

### E10 — Movement discipline · `ac7f72a`
Route clearance along the path, goal hysteresis, reciprocal fire, kite range gate,
no static camping. Score **−0.22 ± 0.44**, survival −3.5 ± 13.2 s, damage dealt
**+335 ± 239**, kills **+0.25 ± 0.21** (32 pairs). Neutral on survival, positive on
offence; kept because each item fixes a demonstrated defect (walking into the
squad, standing still, dying with a full magazine).

### E11 — Live-config geometry (D5, D9) · `91bac7b`
Radius, height, step-up, slope, canopy density from `hello.config` / `world.json`.
**+0.42 ± 0.51** / **+0.13 ± 0.18**. Inconclusive as a gain; retained as protocol
correctness (no hard-coded rule numbers).

---

## Inconclusive / null

### E12 — 14-dimension parameter sweep · `82f6849`
Cached per-seed baseline, 14 random configs, 3 training ranges, holdout on three
untouched ranges. Dimensions: `aggression, cover_bias, engage_range,
focus_switch_margin, hp_floor, hunt_hp, hunt_range, hunt_standoff, hunt_target,
hunt_until, kite_range, quiet_when_safe, strafe_gain, threat_bias`.

**No reliable winner.** Per-range deltas swing up to 1.2 score *within one config*
(e.g. `+0.31 / −1.00 / +0.12`). Only one config was positive on all three training
ranges and it had negative kills — self-contradictory.

Best by mechanism (kills): aggression 0.8 / cover_bias 0.25 / standoff 65 /
hunt_hp 0.30 / quiet off → train **+0.33** (kills +0.38), holdout **+0.15** (kills
+0.06), 5 of 6 ranges non-negative. Not clearly better than the submitted build.

### E13 — Situational trade-ratio controller · `3ffe906`
Press when dealt/taken > 1.35 and HP > 45 %; disengage when < 0.65 or HP < 32 %.
**−0.062 ± 0.233**, per-range `[−0.25 / −0.44 / +0.50]`. Default off.

### E14 — Kill-loot collection · `7468dcb`
Detour to a corpse for its 3 cubes within a 7 s window when nothing is within 55 m.
Built, **default off, never measured**. Still pending.

### E15 — Early weapon acquisition
`roam_until 45, weapon_seek_range 200, hunt off`:

| Set | Δscore | Δkills | Per-range |
| --- | --- | --- | --- |
| train (n=48) | **+0.46 ± 0.30** | +0.46 | +0.44 / +0.12 / +0.81 |
| holdout (n=48) | **+0.10 ± 0.24** | +0.19 | +0.94 / −0.12 / −0.50 |

All three training ranges positive and kills up on both sets, but the holdout is
mixed → **inconclusive, not a win**. Kept on the shortlist because the mechanism
(F8) is the only route to a higher damage ceiling.

### E16 — Survival ceiling: nine policy variants
Same 16 seeds, same opponents. Full table in `FINDINGS.md` F5. Range 44–74 s;
nothing reaches 100 s. **The pacifist arm is invalid** (see E18) because the fire
gate cannot suppress fire.

### E17 — `kite_hp` sweep (duel-abort threshold)
Prompted by an external review: `kite_hp = 0.97` means any damage triggers a 6 s
flee that aborts duels mid-kill.

| `kite_hp` | score | kills | death | paired vs 0.97 |
| --- | --- | --- | --- | --- |
| 0.97 | 1.94 | 1.23 | 70 s | — |
| 0.85 | 1.79 | 1.27 | 70 s | −0.15 ± 0.29 |
| 0.70 | 1.92 | **1.38** | 69 s | −0.02 ± 0.34 |
| 0.55 | 1.75 | 1.29 | 68 s | −0.19 ± 0.34 |

Null. Kills rise slightly at 0.70 but score does not move. The diagnosis was right,
the lever is not load-bearing.

### E18 — External review: `warden` (Claude), full policy replacement
778-line policy: predictive engagement gate (time-to-kill race), heal cycle,
weapon-first opening, zone-clock regimes, laser charge controller, mortar cluster
solver, drop contest. Wired standalone into the harness (`work-warden/bot.py`) and
run on six seed ranges.

| Set | ours | warden | paired |
| --- | --- | --- | --- |
| train (n=48) | 1.83 / 74 s / 1.19 k | 1.06 / 84 s / 0.27 k | **−0.77 ± 0.28** |
| holdout (n=48) | 1.96 / 72 s / 1.33 k | 1.31 / 85 s / 0.31 k | **−0.65 ± 0.35** |

Survives longer, kills 4× less, scores much worse. **Rejected as a replacement.**
Individual mechanisms worth salvaging: the ratio-based engagement gate (more
principled than a fixed range), the laser charge controller, and the mortar cluster
solver. Note it was run without the map (`world=None`), so its LOS is optimistic —
but the kill collapse is a policy effect, not a map effect.

---

## Rejected

| # | Change | Result |
| --- | --- | --- |
| E19 | Focus fire | +0.38 ± 0.13 (32 pairs, range 4000) then **−0.04 ± 0.08** (48 pairs, range 8000) — **false positive**, retracted. Kept as neutral/mechanically sound |
| E20 | Laser pre-charge without a working gate | −0.16 ± 0.13 |
| E21 | Indirect mortar (accept LOS-blocked targets) | −0.28 ± 0.11 |
| E22 | Economy bundle (roam + crates + drops) | **−0.78 ± 0.36** |
| E23 | High aim point (0.75 body height) | −0.47 ± 0.23 |
| E24 | Open ground (`cover_bias` 0) | −0.22 ± 0.19 |
| E25 | LOS-breaking cover on | 0.00 ± 0.07, costs ~10 ms/decision |
| E26 | Statue (never move) | −0.46 |
| E27 | Coward (never fire) | 0.00 |
| E28 | Hunter v3 (aggressive variant) | −0.15 |
| E29 | Zone-edge goal | +0.19 / +0.67 / −0.10 → +0.25 ± 0.23, inconclusive |
| E30 | Aggression 1.0 / engage_range 240 | +0.12 ± 0.12, inconclusive |
| E31 | Mortar-preferring loadout | −0.02 ± 0.09, inconclusive |

---

## Diagnostics (not A/B)

### E32 — Decision-time budget
387 sampled decisions: a shootable target existed **21 %** of the time, we were
alone **35 %**, enemies were visible but terrain-blocked **44 %**. Damage is limited
by target availability, not by permission to shoot.

### E33 — Death profile
Cause of our deaths: gun ~1,000–1,250 damage, laser/lightning/mortar ~400 each, NPC
~70. Death time improved from 77 s (v1) to 97–120 s during the survival iteration,
now ~70 s with hunt mode enabled.

### E34 — Sandbox conformance
299/300 answered, 1 late, p99 24.7 ms, max 106 ms. Passes. p99 native is 4.3 ms.

**Next:** [`OPERATIONS.md`](OPERATIONS.md) — how to reproduce any of this.
