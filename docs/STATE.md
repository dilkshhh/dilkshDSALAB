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

## The local instrument is exhausted

Every change in round 2 landed inside ±0.2, while official scores move in steps of
0.6. Repeated nulls: strict fire gate (−0.60, so the *fix* is right but the gate is
wrong), pickup detour radius (0.00), early weapon roam (+0.02 / +0.15), full-charge
laser (−0.02 / +0.16), gun-only (−0.17). Meanwhile a purpose-built replacement
policy scored −0.7, and a single knob (`kite_hp`) moved nothing across four values.

**Conclusion: local A/B can no longer rank candidates.** It can still reject a
−0.7 regression and confirm a mechanism is wired (weapon uptime 8 % → 35 %), but it
cannot tell +0.1 from 0.0. From here, the official board is the better instrument —
and a worse submission does **not** damage the best score, so probes are nearly free
except for the human's time.

## Next actions, ranked

1. **Recover the official score for `7468dcb`.** It is the single most valuable
   datum in the project: it is the only measurement of whether local-neutral
   aggression transfers (hunt v1 went 1.83 → 2.44 that way). Without it we cannot
   tell whether the current build is at 2.5 or 3.5, and every calibration argument
   in `FINDINGS.md` F10 is extrapolation.
2. **Submit the early-roam build as a probe.** `roam_until 45`,
   `weapon_seek_range 200`. Kills up on train and holdout, weapon uptime 4×,
   aggression-flavoured — the class that has historically transferred better
   officially than locally. Set as defaults, run the sandbox conformance check,
   commit, request submission.
3. **Then, and only then, attack the real gap.** With H1 (laser) dead and H2
   (survival) unsupported, the remaining explanation is H3 — the real squad is
   weaker than the emulation — plus the duty-cycle problem: a shootable target
   exists in only 21 % of decisions, and 44 % are terrain-blocked. Raising the duty
   cycle is a positioning problem, not a weapon or survival problem.
4. **Untested and cheap:** lightning preference (240 dps inside 45 m, currently
   ranked last); rooftops (we never jump); the regen cycle (now testable via E35);
   kill-loot collection (built, default off, never measured).

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
