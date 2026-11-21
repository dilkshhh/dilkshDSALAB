# Mech Royale bot (`mechfight/1`)

Entry for the Builders Buildathon 2026, **Mech Royale** track. Python 3.13,
standard library only. Placement is the metric, so the policy is survival-first:
stay inside the circle, avoid being found, break line of sight, and only take
free economy or favourable fights.

## Layout

| Path | What it is |
| --- | --- |
| `bot.py` | Entrypoint: thin adapter around `mechfight.run`. |
| `brain.py` | Decision core: mode selection, zone rotation, threat handling. |
| `intel.py` | Belief records with source/confidence tags; server-tracked positions, uncertain sound/beam/event sectors, explicit unknowns. |
| `world.py` | 1 m arena model: solid column tops, overhangs, 9-point body collision, LOS. |
| `nav.py` | Navigation grid + bounded A* + local steering + collision-safe heading filter. |
| `zone.py` | Circle interpolation and safe-point selection. |
| `combat.py` | Lead aiming, torso slew, projectile/laser evasion, facing. |
| `econ.py` | Loot, cubes, supply drops, upgrade valuation, optional early roam. |
| `cover.py` | Local line-of-sight breaking spot search (optional policy layer). |
| `params.py` | Tunable policy parameters; `BOT_PARAMS` env JSON overrides them for local A/B. |
| `mechfight.py` | Official protocol wrapper from the organiser's starter kit. |
| `mechfight.schema.json`, `check/`, `arena/` | Official kit files, used only for local conformance testing; excluded from the image. |
| `tools/example_bot.py` | Official starter bot, kept for reference; excluded from the image. |
| `AUDIT.md` | Protocol fact/uncertainty ledger, architecture audit, observation/action maps and baseline. |

`sim/` and `tests/` are **empty local placeholders** and are not in the public tree.
The A/B simulator used for development is external and uncommitted (see Attribution).

## Attribution

- `mechfight.py`, `mechfight.schema.json`, `check/check.py`,
  `check/stream.jsonl.gz`, `arena/v2/world.json` and `arena/v2/terrain.i16` are
  copied unchanged from the official **mechfight bot kit** published on the
  track page (https://www.joinbuilders.org/buildathon/tracks/builders).
- Local relative A/B testing uses a separate, uncommitted headless simulator
  derived from the public MIT-licensed repository
  `anthonyteti/buildathon-mech-royale`, driven through its protocol-speaking
  external-bot hook. **No third-party bot code is included in the submitted
  image**; every file in the Docker context is our own Python or an official kit file.
- Released under the MIT License (see `LICENSE`).

## Build and verify

```sh
docker build --platform linux/amd64 -t mech-bot .
python3 check/check.py -- python3 -u bot.py
python3 check/check.py --map-dir /arena -- docker run --rm -i --network none \
  --cpus 1 --memory 512m --read-only --tmpfs /tmp:rw,size=64m \
  --user 65534:65534 -v "$PWD/arena:/arena:ro" mech-bot
```

`check.py` only proves protocol compliance and timing; it is not a game.

## Local experiment log (relative scores, not official points)

Paired practice runs, same seeds, external protocol-speaking bots. Only the
paired difference is meaningful; absolute values are not comparable with the
official practice score. **No official practice submission has been made yet.**

| Experiment | Paired delta | Decision |
| --- | --- | --- |
| Protocol-first belief layer (D1/D2: server-tracked positions, uncertain sound sectors) | +0.04 ± 0.07 (24 paired, harsh) | neutral; retained for protocol correctness and as arbiter input |
| Single torso-aim arbiter (D3) | +0.54 ± 0.28 (24 paired, harsh) / +0.71 ± 0.59 (24 paired, mild) | retained; positive but variance is high |
| Combined D1/D2/D3 | +0.63 ± 0.25 (24 paired, harsh) / +1.50 ± 0.40 (24 paired, mild) | retained |
| 1 m engine-accurate collision + composed-heading validation | fixed a hard wedging bug (bot was farmed to death by one drone at t≈70 s) | adopted |
| Aggression (`aggression` 0.95 / 0.7) | 0.00 / −0.31 | rejected |
| LOS-breaking cover | 0.00 ± 0.07 | optional, off by default |
| Early roam / weapon + cube farming | −0.50 ± 0.17 | rejected (roam_until = 0) |
| Squad kiting (boost away from incoming-fire bearings, 5 s hold) | +0.55 ± 0.27 | adopted |
| Kite hold 8 s vs 5 s | 0.00 ± 0.09 | 6 s default |
| Kite hold 14 s vs 8 s | −0.21 ± 0.13 | rejected |
| Full-speed (loud) movement vs quiet | −0.67 ± 0.26 | quiet movement kept |
