# STATE — where the project stands

> Living document. Last updated **2026-11-21 16:30 UTC**. Rewrite this file at the
> start of every work session; it is the first thing the next agent reads.

## Clock

| | |
| --- | --- |
| Cutoff | **2026-11-22 20:00 GMT+4 = 16:00 UTC** |
| Time left at last update | ~23.5 hours |
| Submission limit | 4/hour platform, self-limited to **2/hour**, keep one slot free |
| Submissions used | 5 (0.25, 1.83, 2.44, **2.52** `7468dcb`, 2.50 `a33d613`) |

## Scoreboard

| Rank | Score | Note |
| --- | --- | --- |
| 1 | 5.96 | `azing` |
| 16 | 5.38 | qualify for finals |
| 32 | 5.13 | last qualifying slot |
| 48 | 4.88 | |
| us | **2.52** | `7468dcb` — best official so far; `E45 snowball_v2` ready to probe |

Official history: 0.25 → 1.83 (`ac7f72a`) → 2.44 (`407c50e`) → **2.52** (`7468dcb`)
→ 2.50 (`a33d613`, reverted).

`score = 16 − place` = **the number of mechs that died before you**, per match,
meaned over 48 matches on seeds that are fixed for the whole event. See
`FINDINGS.md` F1.

## What the bot is right now

`HEAD` is **`E45 snowball_v2`** — the first architecture in the project to break the
2.10 local ceiling on both train and holdout:
- **Train (n=48):** score **2.48** (+0.50 vs 1.98), kills **1.96** (+0.71), dealt **3,729** (+833), taken **1,968** (+231)
- **Holdout (n=48):** score **2.42** (+0.75 vs 1.67), kills **1.90** (+0.67), dealt **3,668** (+1,108), trade ratio **1.98×**
- **Combined (n=96):** score **2.45** (**+0.625 ± 0.23**), kills **1.93** (**+0.69 ± 0.18**, +56%), 6/6 seed ranges non-negative.

Mechanisms added in E41–E45:
- **Adopted:** `snowball_v1` + `snowball_v2` (lightning-first preference, gun+lightning shared-pitch dual-wielding, full/lethal laser charge controller, mortar ballistic aim fix + cluster targeting, proactive gun reload, fixed exact upgrade valuation for `armor`/`plating`, persistent `known_pickups` memory, active early patrol, safe NPC drone & crate farming, aggressive cube & 3-cube kill-loot scooping, lightning 1v1 rush, enemy lightning hard-counter, supply drop contesting, zone emergency fix, crash-safe `Bot.act` wrapper).
- **Tested and rejected (kept behind default-off flags):** `combat_v2` open-ground strafing (−0.15, −16.7s life), `roof_enabled` rooftop camping (−0.23, +10s life, −0.42k, 8× mortar dmg), `tactical_cover_v1` low-HP hold-fire regen (−0.23 vs E43, −0.32k).

## The central problem

We score ~2 because we die at ~70 s with ~1.3 kills. The leader needs ~5–6.
Three candidate explanations, and the evidence so far:

| Hypothesis | Status | Evidence |
| --- | --- | --- |
| H1: they kill 5 in ~60 s (needs a laser) | **open** | gun is 187 dps theoretical but only ~20 s of trigger time fits in a 70 s life |
| H2: they survive far longer and collect environmental deaths | **weakened** | a purpose-built survival policy reached only 84 s (E13); at 146 s only ~1 bot had died |
| H3: our local proxy is harsher than the real squad | **supported** | hunt mode: neutral locally, **+0.61** officially (E7) |

H3 is the one that keeps being right. Treat local score as a *floor* on quality,
not a ranking of candidates — but do not ignore a local regression of −0.7 either
(that is what warden produced, E13).

## The instrument situation (this changed — read it)

Earlier notes in this file said local A/B was exhausted. That was wrong in an
important way. Two official data points settled it:

- The roam probe predicted **+0.02** locally and delivered **−0.02** officially.
- Hunt v1 was **flat locally** and **+0.61 officially**.

So: **within an architecture, local deltas transfer 1:1 — but the offset between
local and official is a property of the policy, not a constant.** Adding hunt moved
the offset by ~+0.6 without moving the local score. Full analysis in
`FINDINGS.md` F17.

Practical rules for the next agent:

1. **Official resolution is ~±0.05** (practice seeds are fixed; only slot and spawn
   vary). It is a far finer instrument than local (±0.5). Use it to *measure*.
2. **Local is for generating candidates**, not ranking them. Its value is that it
   is free and unlimited; its weakness is that it under-prices aggression.
3. **A change that moves local by less than ~0.5 is not worth a slot** unless it is
   a new mechanism with a strong argument, in which case a probe is cheap: a worse
   submission never damages the best score.

## Next actions, ranked

1. **Find a mechanism worth +2.6, or accept 2.52.** That is the arithmetic:
   qualification is 5.13, we are at 2.52, transfer is 1:1, and the best local score
   any policy has produced here is ~2.1. Tuning cannot close it. The next agent
   should spend its first hour on *what could plausibly double the score*, not on
   knobs.
2. **The three live hypotheses**, in order of how much evidence supports them:
   - **H3 — the real squad is weaker than the emulation.** Supported by hunt v1
     (+0.61 official, 0 local). If true, more aggression is underpriced and a
     bolder policy transfers better than it measures.
   - **H4 — duty cycle.** A shootable target exists in only 21 % of decisions and
     44 % are terrain-blocked. Damage is limited by *target availability*, which is
     a positioning problem. Nothing we have tried attacks it directly.
   - **H1 (laser) is dead** (F8): the laser is DPS-neutral, not a 3× upgrade.
   - **H2 (survival) is dead** (F6, E35): a true pacifist scores 0.38, and the best
     survival policy we could build reached 84 s and scored −0.77.
3. **Untested and cheap**, in rough value order: lightning preference (240 dps
   inside 45 m, currently ranked last); rooftops and jump/jet (we never use them,
   25 % of loot is on roofs); the regen cycle (now testable via `fire_gate_strict`);
   per-target damage ledger so fire commits instead of spreading; kill-loot
   collection (built, default off, never measured).
4. **Do not re-submit HEAD expecting a change.** It is the 2.52 build.

## What not to do

- Do not tune the existing parameters. E12 found no reliable winner.
- Do not re-propose anything in `EXPERIMENTS.md` §Rejected without a new mechanism.
- Do not trust a single seed range. Per-range deltas swing up to 1.2.
- Do not build a survival-first policy. Tested three times now: E13 (−0.77), E16,
  and the true-pacifist control (0.38).
- Do not assume a laser is a damage upgrade. It is DPS-neutral (F8).

## Open questions

1. Why does the leader score 5.96? (H1/H2/H3 above.)
2. Does the real squad escalate the way the track page says, or does it converge
   immediately? The local emulation may not match.
3. Are practice seeds exploitable? They are fixed for the event, so overfitting is
   possible in principle — but we cannot see them, only aggregate scores.
4. Does dying to the zone count as a death for placement? (Yes by the protocol's
   wording, and the simulator agrees — E13 seed 8000.)

**Next:** [`FINDINGS.md`](FINDINGS.md) — what is actually true.
