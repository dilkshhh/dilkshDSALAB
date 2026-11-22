# Team 4141: Mech Royale bot

Team 4141's entry for the Builders Buildathon 2026 Mech Royale track, by Dilksh and Sparsh.

**This entry reuses other people's code.** Most of the bot was written by the authors credited below.

- **This commit:** the final entry's bot. Every file except this README is identical to
  `b833cd0adab280a62b18a4e6b1402c59c647db1d`.
- **The `main` branch:** an older snapshot of the same upstream project. It is not the final entry.

## Credits

### 1. ahmad-ovh/Buildathon (team Ahmad Suliman): the bot

- Source: https://github.com/ahmad-ovh/Buildathon
- License: MIT, Copyright (c) 2026 ahmad-ovh
- Used in the final entry: the whole Apex-Go v3 bot, from commit `56e0f76`, with the license notices added in
  `54919f3`. That covers `cmd/mechbot/`, `internal/`, the `Dockerfile`, the older Python bot, and the project
  documentation and tooling.
- Their contribution includes the changes they made to the engine credited in section 2, such as lightning
  avoidance, laser-cooldown tracking, rear-arc avoidance, reloading behind cover, kill-aware laser release,
  and the practice and free-for-all tuning.
- Used on `main`: their commit `f29e4d3`, nearly unchanged (see section 4).

### 2. andrew-zhouu/builders-mech-royale-2026 (team TigerTown27): the engine underneath

- Source: https://github.com/andrew-zhouu/builders-mech-royale-2026
- License: MIT, Copyright (c) 2026 the authors of that repository
- Ahmad Suliman's bot is built on this engine, so it is part of this entry.
- Identical in the final entry to their v0.118 (`663bbc4`), apart from import paths:
  - `internal/world/`: `world.go`, `nav.go`, `exposure.go`, `roofs.go`, `surface.go`, `trees.go`
    (map, line of sight, path search, roofs)
  - `internal/proto/proto.go` (protocol)
  - `internal/bot/`: `move.go`, `peek.go`, `util.go`, `hidemap.go`, `hidemap.gz`
    (movement, corner peeking, helpers, hiding map)
- Derived from their code, with differences from v0.118:
  - `internal/bot/`: `bot.go`, `policy.go`, `combat.go`, `strategy.go`, `cover.go`, `hide.go`, `lead.go`,
    `plan.go`, `roof.go`, `variants.go` (decisions, combat, aiming, cover, strategy)
  - `cmd/mechbot/main.go` (input and output loop)

### 3. h-ardy/buildathon-mech-royale (team who dey): three settings

- Source: https://github.com/h-ardy/buildathon-mech-royale (no longer publicly reachable as of 22 Nov 2026)
- Used in the final entry, in `DefaultParams` in `internal/bot/bot.go`:
  - `RearAvoidW: 50` (was 35)
  - `CubeSmart: true`
  - `KillFocus: 1.5`
- With these settings the final entry's bot code is functionally the same as who dey's, which is also built on
  Ahmad Suliman's bot.

### 4. What team 4141 changed

- Final entry: combined sections 1 and 3, removed the upstream chat transcripts, and built and tested the result.
- `main`: renamed the bot to PROFESSOR, added code comments and left out some upstream documents and transcripts.

### 5. Official bot kit (Builders)

- Source: https://www.joinbuilders.org/buildathon/tracks/builders
- Files: `mechfight.py`, `mechfight.schema.json`, `check/`, `arena/v2/` and `tools/example_bot.py`

### 6. Earlier versions in this repository's history (not in the final entry)

- **giddygiddyboy** (https://github.com/justnau/giddygiddyboy-mech-royale), MIT, Copyright (c) 2026 giddygiddyboy:
  the earlier Go bot (`pilot.go`, `strategy.go`, `terrain.go`), including commit `c512d8d` and the `exp-v5` to
  `exp-v11` branches.
- **aqilc**, MIT, Copyright (c) 2026 aqilc: the "farx" bot on branch `exp-aq1`.

## Build

```sh
docker build --platform linux/amd64 -t mech-bot .
```

## License

MIT. The copyright notices of the reused code and the permission notice that applies to each:

```
Copyright (c) 2026 ahmad-ovh
Copyright (c) 2026 the authors of andrew-zhouu/builders-mech-royale-2026
Copyright (c) 2026 giddygiddyboy
Copyright (c) 2026 aqilc

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
