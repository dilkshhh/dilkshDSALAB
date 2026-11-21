# STATE — where the project stands

> Living document. Last updated **2026-11-21 22:50 UTC**. Rewrite this file at the
> start of every work session; it is the first thing the next agent reads.

## Clock

| | |
| --- | --- |
| Cutoff | **2026-11-22 20:00 GMT+4 = 16:00 UTC** |
| Time left at last update | ~17 hours |
| Submission limit | 4/hour platform, self-limited to **2/hour**, keep one slot free |
| Submissions used | 4 (0.25, 1.83, 2.44, `7468dcb` — last score not recorded) |

## Scoreboard

| Rank | Score | Note |
| --- | --- | --- |
| 1 | 5.96 | `azing` |
| 16 | 5.38 | qualify for finals |
| 32 | 5.13 | last qualifying slot |
| 48 | 4.88 | |
| us | **2.44** | `407c50e`; `7468dcb` scored higher but the number was never recorded |

`score = 16 − place` = **the number of mechs that died before you**, per match,
meaned over 48 matches on seeds that are fixed for the whole event. See
`FINDINGS.md` F1.

## What the bot is right now

`HEAD` is `7468dcb` + documentation commits. The working tree is the same policy as
the submitted build: survival-first with a hunt layer on top. Local profile over
48 matches: **score 1.83–1.96, death ~72 s, kills ~1.25**.

It passes the sandbox conformance check (299/300, one late answer, p99 24.7 ms,
max 106 ms) and builds clean. Nothing in the tree is broken.

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

## Next actions, ranked

1. **Fix the fire gate so it can actually suppress fire** (E15). `allow_fire` only
   scales candidate *utility*; the weapon branches pass literal `fire=True`, so the
   gate never suppresses anything. Consequence: our "never fire" control still
   dealt 2,606 damage, which invalidates the pacifist row of the survival table and
   means we cannot test any hold-fire policy. Patch behind
   `params["fire_gate_strict"]`, A/B it, then make it default if it holds.
2. **Then test the regen cycle properly.** 45 HP/s after 5 s of no damage dealt
   *or taken* is the largest untapped resource in the game (a full bar is 31 s of
   regen). It is untestable until (1) is fixed.
3. **Damage conversion.** We deal 3,200–4,500 per match for 1.3 kills; one traced
   match dealt 4,463 for zero. Damage that does not kill is refunded at 45 HP/s.
   Consider a per-target damage ledger so fire commits to the target we have
   already sunk damage into, rather than the lowest-HP one.
4. **Weapon quality.** Early weapon acquisition is the only change where kills
   moved on both train and holdout (+0.46 / +0.10, E14). The gun out-DPSes the
   laser in theory (187 vs 131) but the laser wins at realistic hit rates and has
   50 m more range; lightning is 240 dps inside 45 m and we rank it *last*.
5. **Verticality.** We never jump or jet except to unstick. 259 prisms, 25 % of
   loot on roofs, `jump_speed` 11 + `jet_accel` 34. Untested, and both external
   reviewers flagged it.

## What not to do

- Do not tune the existing parameters. A 14-dimension sweep found no reliable
  winner (E11). The space is exhausted.
- Do not re-propose anything in `EXPERIMENTS.md` §Rejected without a new mechanism.
- Do not trust a single seed range. Per-range deltas swing by up to 1.2 score
  within one config.
- Do not build a survival-first policy. Tested twice, both times worse (E13, E6).

## Open questions

1. Why does the leader score 5.96? (H1/H2/H3 above.)
2. Does the real squad escalate the way the track page says, or does it converge
   immediately? The local emulation may not match.
3. Are practice seeds exploitable? They are fixed for the event, so overfitting is
   possible in principle — but we cannot see them, only aggregate scores.
4. Does dying to the zone count as a death for placement? (Yes by the protocol's
   wording, and the simulator agrees — E13 seed 8000.)

**Next:** [`FINDINGS.md`](FINDINGS.md) — what is actually true.
