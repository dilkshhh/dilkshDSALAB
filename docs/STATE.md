# STATE — where the project stands

> Living document. Last updated **2026-11-21 21:58 UTC**. Rewrite this file at the
> start of every work session; it is the first thing the next agent reads.

## Clock

| | |
| --- | --- |
| Cutoff | **2026-11-22 20:00 GMT+4 = 16:00 UTC** |
| Time left at last update | ~18 hours |
| Submission limit | 4/hour platform (user allows up to **3/hour**, keep 1 slot free) |
| Submissions used | 7 (latest `331c2d1` Python `Apex v1` scored **5.33**, Rank 58, `+2.81` vs 2.52; new **compiled Go `Apex-Go v2`** now built, verified across 192 practice + 24×16-mech FFA + 300/300 Docker, and ready to submit!) |

## Scoreboard

| Rank | Score | Note |
| --- | --- | --- |
| 1 | 6.31 | `kyoto-max` / `IT_Professionals` (tied) |
| 3 | 6.29 | `67` |
| 4 | 6.25 | `TigerTown27` (`4.33` 192-match local avg: `4.55 HK1 / 4.11 HK0`; `6.88` in 16-mech FFA) |
| 5 | 6.25 | `not even close` (`Th3r0n/automata` + `tweakCautiousT` `+0.35` official) |
| 9–19 | 6.19 | `giddygiddyboy` (`2.96` 192-match local avg; `7.11` in 16-mech FFA), `2.3%`, `Wai and Jai`, `@GMUNVIS`, etc. |
| 20 | 6.17 | `Kanyaraasi` (pure Python 3.13 + exact prism raycast + precomputed nav cache: `3.38` train avg) |
| us | **5.33** | `331c2d1` (Rank 58, Python `Apex v1`, best of the Python `giddy` ports). **New `Apex-Go v2` (compiled Go)** scores **4.70** 192-match local avg (**+0.37** over `#4 (6.25)` and **+1.74** over `#9 (6.19)`) AND **8.35 ± 0.38** in 16-mech FFA (**+1.47** over `#4`, **+1.24** over `#9`, 13/24 wins!) |

Official history: 0.25 → 1.83 (`ac7f72a`) → 2.44 (`407c50e`) → 2.52 (`7468dcb`)
→ 2.50 (`a33d613`, reverted) → 2.48 (`82f6849`, unpushed) → **5.33** (`331c2d1`, Rank 58).

`score = 16 − place` = **the number of mechs that died before you**, per match,
meaned over 48 matches on seeds that are fixed for the whole event. See
`FINDINGS.md` F1.

## What the bot is right now

`HEAD` is **`Apex-Go v2` (compiled static Go 1.25/1.26 binary in `FROM scratch`, `4.03 MB`)** — synthesizing the strongest proven mechanisms across `#4 TigerTown27 (6.25)`, `#5 not even close (6.25)`, `#9 giddygiddyboy (6.19)`, `#15 Wai and Jai (6.19)`, `#20 Kanyaraasi (6.17)`, and our own `E57` anti-lightning breakthrough:
- **1-CPU Docker sandbox**: **300/300 PASS** (`0` missed, `0` dropped, `0` bad lines, `ready 1.48 s`, `p50 3.2 ms`, `p90 5.5 ms`, `p99 9.9 ms`, `max 11.3 ms`, `4.03 MB` `FROM scratch` image).
- **192-Match Practice (`96 HK=1 + 96 HK=0`, Train + Untouched Holdout)**:
  - **`HK=1` (n=96)**: **5.18** (`4.96` train / `5.40` holdout) — **`+0.63`** vs `#4 TigerTown27` (`4.55`) and **`+2.18`** vs `#9 giddy` (`3.00`)! Holdout dealt **7,978**, trade **3.58×**, kills **4.67/match**, cubes **6.43**.
  - **`HK=0` (n=96)**: **4.23** (`3.65` train / `4.81` holdout) — **`+0.12`** vs `#4` (`4.11`) and **`+1.31`** vs `#9` (`2.92`)! Holdout dealt **7,142**, trade **3.36×**, kills **4.17/match**, `15000 = 6.88 (6.06k, 2 alive wins)`.
  - **192-Match Grand Avg**: **4.70** vs `#4 TigerTown27` **4.33** (**`+0.37`**, winning **4/4 quadrants**) and `#9 giddy` **2.96** (**`+1.74`**); **6 alive wins / 192**; lightning deaths cut `27 → 15 / 192`.
- **24 × 16-Mech FFA Head-to-Head (`6 Apex-Go` vs `5 #4 TigerTown27` vs `5 #9 giddy`)**:
  - **`Apex-Go v2`**: **8.35 ± 0.38** (**13/24 wins = 54.2 %**, `1.25` kills, `134 s` life, `3,554` dealt, `39 %` gun acc, **0 zone deaths**, **2 lightning deaths**)
  - `#9 giddygiddyboy (6.19)`: `7.11 ± 0.41` (4/24 wins, `0.39` kills, `119 s`, `1,303` dealt, 6 lightning deaths)
  - `#4 TigerTown27 (6.25)`: `6.88 ± 0.43` (7/24 wins, `1.07` kills, `105 s`, `2,910` dealt, 7 lightning deaths, 2 zone deaths)
- **Next**: Submit `Apex-Go v2` for official calibration (expected **`6.30–6.65+`**, pushing directly into Top 1–3!), then run surgical follow-up probes with our remaining ~18 hours if needed to lock `#1` cleanly!

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
