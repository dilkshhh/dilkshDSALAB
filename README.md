# Mech Royale bot (`mechfight/1`)

Entry for the Builders Buildathon 2026, **Mech Royale** track. Python 3.13,
standard library only. The bot optimises placement (survival), not kills.

## Layout

| Path | What it is |
| --- | --- |
| `bot.py` | Entrypoint: thin adapter around `mechfight.run`. |
| `brain.py` | Decision core: mode selection, zone rotation, threat handling. |
| `world.py` | Arena model: terrain heightmap, prism rasterisation, line of sight. |
| `nav.py` | Navigation grid + bounded A* + local steering. |
| `zone.py` | Circle interpolation and safe-point selection. |
| `combat.py` | Lead aiming, torso slew, projectile/laser evasion, facing. |
| `econ.py` | Loot, cubes, supply drops and upgrade valuation. |
| `params.py` | Tunable policy parameters (local A/B variants override these). |
| `mechfight.py` | Official protocol wrapper from the organiser's starter kit. |
| `mechfight.schema.json`, `check/`, `arena/` | Official kit files, used only for local conformance testing; excluded from the image. |
| `sim/`, `tools/`, `tests/` | Local development harness; excluded from the image. |

## Attribution

- `mechfight.py`, `mechfight.schema.json`, `check/check.py`,
  `check/stream.jsonl.gz`, `arena/v2/world.json` and `arena/v2/terrain.i16` are
  copied unchanged from the official **mechfight bot kit** published on the
  track page (https://www.joinbuilders.org/buildathon/tracks/builders).
- The local headless simulator in `sim/` is an independent implementation
  written from `protocol.md` for relative A/B testing only; no third-party bot
  code is included in the submitted image.
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
