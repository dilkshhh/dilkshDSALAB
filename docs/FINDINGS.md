# FINDINGS — what is true about this game

> Living document. Last updated **2026-11-21 22:50 UTC**.
>
> Tags: `[fact]` protocol or config, citable to a section · `[measured]` we ran it,
> experiment ID given · `[inferred]` follows from facts + measurements · `[hypothesis]`
> untested, do not build on it without an experiment.
>
> If a finding is overturned, rewrite it here and log the reversal in
> `DECISIONS.md`. Never leave two contradictory versions.

---

## F1 — Score is a body count `[fact]`

`score = 16 − place`, and `place = 1 + (number of mechs that died before you)`.
Therefore **score = the number of mechs that died before you**, averaged over 48
matches. Maximum 15. Survivors at the clock are ranked by HP (protocol §4).

This is the single most important line in the repository. Everything else is a
consequence.

## F2 — The 15 opponents are one squad that never fights itself `[fact]`

Track page, verbatim: *"Practice plays 48 matches against 15 house bots (4 easy, 4
medium, 4 hard, 3 expert) acting as one squad: they share vision, never fight each
other, and hunt you weakest first (one early, more as you thin them out, all of
them late)."*

Consequences: no third-party damage between opponents; no "let them weaken each
other" play; the only opponent deaths are ones **we** cause or the **environment**
causes; and the hunter count is a difficulty schedule keyed to our kill count.

## F3 — Score decomposes exactly into kills plus environmental deaths `[measured] E6`

Over 16 matches on one seed range: mean score **2.00** = **1.31 kills** + **0.69
environmental deaths**, to two decimals. The environmental component was entirely
NPC drones killing house bots (11 deaths over 16 matches). Zero zone deaths and
zero fall deaths were observed at that horizon.

The decomposition is exact because of F1: every opponent death is either ours or
the environment's.

## F4 — Environmental attrition is slow early and does not rescue a passive bot `[measured] E6, E13`

At t≈146 s (warden, seed 8000) only about one opponent had died. The theory that a
passive survivor could farm environmental deaths into a 5.96 score is **not
supported** at the horizons we can reach. It would require surviving into the
late zone collapse, which nothing we have built can do.

## F5 — There is no survival/aggression trade-off to optimise, but survival is also capped `[measured] E6`

Nine policy variants, same 16 seeds:

| Policy | Death time | Score | Kills |
| --- | --- | --- | --- |
| default | 59 s | 2.00 | 1.38 |
| "true pacifist" (fire off, hunt off) | 56 s | 1.69 | 1.19 |
| coward (fire off, kite always) | 58 s | 1.75 | 1.31 |
| no kiting, no hunting | 44 s | 1.38 | 1.19 |
| hide in cover always | 66 s | 2.00 | 1.50 |
| kite always, range 200 | 74 s | 1.88 | 1.44 |
| turtle | 73 s | 1.75 | 1.25 |

Nothing exceeds ~74 s, and the "pacifist" row is **suspect**: the fire gate cannot
suppress fire (F11), so that arm still dealt 2,606 damage. Re-run it after E15.

What survives the caveat: **kiting is worth ~15 s** (44 s without it), **cover is
worth ~7 s**, and **no policy variant we have tried reaches 100 s**.

## F6 — Survival-first is a losing trade, tested twice `[measured] E13, E6`

An external reviewer's purpose-built survival policy (`warden`, 778 lines,
predictive engagement gate + heal cycle + drop contest) survived **+11 s** longer
than ours and killed **4× less**:

| | score | death | kills |
| --- | --- | --- | --- |
| ours (train, n=48) | 1.83 | 74 s | 1.19 |
| warden (train, n=48) | 1.06 | 84 s | 0.27 |
| paired delta | **−0.77 ± 0.28** | +10 s | −0.92 |
| ours (holdout, n=48) | 1.96 | 72 s | 1.33 |
| warden (holdout, n=48) | 1.31 | 85 s | 0.31 |
| paired delta | **−0.65 ± 0.35** | +13 s | −1.02 |

A +13 s life extension is worth ~0.2 score. Losing 1 kill is worth ~−1.0. The
exchange rate is brutal: **never trade a kill for survival.**

## F7 — Damage that does not kill is refunded `[measured] E6`

Regen is 45 HP/s after 5 s with no damage dealt *or taken* (protocol §7). One traced
match dealt **4,463 damage and scored 0 kills**; another dealt 3,185 for 1.31
kills. A kill needs 1,400 damage inside the regen window. Anything less is healed
back.

Corollary: chip damage at long range is close to worthless, and *dealing* damage
resets our own regen timer, so poking also costs us healing.

## F8 — Weapon DPS, at realistic hit rates `[inferred from fact + model]`

Nominal (perfect accuracy): gun 45/0.24 = **187 dps**; laser 315/(0.75 charge +
1.65 cooldown) = **131 dps**; lightning 60/0.25 = **240 dps** but only inside 45 m;
mortar 200/2.6 = 77 dps plus 160 splash.

At realistic hit probabilities (warden's hit model: gun ≈ 0.55, laser ≈ 0.9 because
it is hitscan, mortar ≈ 0.3): gun ≈ 102, laser ≈ 131, mortar ≈ 57, **lightning ≈
240 inside 45 m**.

Two things follow and neither is implemented:
- Our `weapon_pref` ranks lightning **last**, but inside 45 m it is the highest-DPS
  weapon in the game.
- The laser beats the gun on expected damage despite lower nominal DPS, and has
  280 m range vs 230.

## F9 — Early weapon acquisition is weakly positive and the only change where kills moved twice `[measured] E14`

`roam_until 45, weapon_seek_range 200, hunt off`: **+0.46 ± 0.30** on train (all
three ranges positive, Δkills +0.46) and **+0.10 ± 0.24** on holdout (Δkills +0.19).
Inconclusive by our own standard, but the mechanism is the only one that can raise
the damage ceiling, so it stays on the shortlist.

## F10 — The local proxy under-rewards aggression `[measured] E7`

Hunt mode measured **neutral locally** and **+0.61 officially** (1.83 → 2.44). The
local emulation's expert bots are probably stronger, or more coordinated, than the
real ones. Practical rule: a local regression of ~−0.2 in exchange for +kills is
acceptable; a local regression of −0.7 (warden) is not.

## F11 — The fire gate is inert `[fact, code] E15`

`combat._act_arbiter` computes `fire_gate = allow_fire and fire_enabled`, then uses
it **only to scale candidate utility**. The gun/lightning/mortar branches pass
literal `fire=True`. The highest-utility candidate therefore fires regardless of
the gate.

Consequences: every "fire discipline" experiment we ran was a no-op; our "never
fire" control still shot; and no hold-fire policy (regen cycle, ambush, silence) can
be tested until this is fixed.

## F12 — Our clock is shorter than the game's `[fact]`

- Zone phase 1 shrink starts at **t = 60 s** (hold 60).
- The first supply drop **lands at t = 95 s** (`times[0] = 70` + `fall_s = 25`).
- We die at **~70 s**.

So every mechanic gated on t > 95 — supply drops, phases 2–6, the late-game mortar
clusters, most upgrade thresholds — is currently **unreachable**. Any improvement
must either pay off inside the first 70 s or extend life past 95 s.

## F13 — Terrain beats vision; distance does not `[inferred]`

Vision is 200 m in a 120° wedge, shared across the squad, with 45 m proximity. Once
seen, we are permanently known. Only hard occluders (buildings, stadium rim) break
contact; trees are soft (canopy blocks with p ≈ 0.35). This is why kiting works when
it seeks occlusion and fails when it only runs away.

## F14 — Mid-body aim is correct `[measured] E18`

Aiming at 0.75 body height measured **−0.47**; 0.5 (mid-body) is the default. High
aim clips intervening geometry, and 44 % of decisions already have enemies
terrain-blocked.

## F15 — `kite_hp` is not a useful lever `[measured] E16`

Gemini correctly identified that `kite_hp = 0.97` means *any* damage triggers a 6 s
flee that aborts duels. But lowering it does nothing:

| `kite_hp` | score | kills | death |
| --- | --- | --- | --- |
| 0.97 (default) | 1.94 | 1.23 | 70 s |
| 0.85 | 1.79 | 1.27 | 70 s |
| 0.70 | 1.92 | **1.38** | 69 s |
| 0.55 | 1.75 | 1.29 | 68 s |

All within noise. The mechanism is real but not the binding constraint — probably
because the flee is also what keeps us alive.

## F16 — Seed *range* is a random effect `[measured] E11`

The same comparison reads +0.67 on one range and −0.10 on another. Per-range deltas
swing by up to 1.2 score within a single config. Treating seeds as independent
understates error badly. See the measurement protocol in `OPERATIONS.md`.

**Next:** [`ARCHITECTURE.md`](ARCHITECTURE.md) — how the code implements (and
mis-implements) the above.
