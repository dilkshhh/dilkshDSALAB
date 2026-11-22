// farxt<T> and farxc* probes: farx unchanged (same seed, same random draws, same decisions) until a trigger, then the
// farxk stop (bots/farxkill): hold fire and walk to the nearest mech it knows. The same sha replays the same 48 board
// games, so a time probe scores about E[kills before T] and a conditional probe about 3 + P(not C).
import type { Observation } from "../../src/mechfight.ts"
import { Brain as FarX } from "../farx/brain.ts"

const d2 = (a: number[], b: number[]) => Math.hypot(a[0] - b[0], a[1] - b[1])
// protocol.md, Id ranges: mechs 0-15
const isMech = (id: unknown): id is number => typeof id === "number" && id >= 0 && id <= 15

/** our kills, and what happened to us up to our 3rd kill */
export class Tally {
  kills = 0
  /** match time of kill 3 */
  k3t = Infinity
  /** other mechs that damaged us */
  attackers = new Set<number>()
  /** mechs we hit before they ever damaged us */
  shotFirst = new Set<number>()
  /** one of shotFirst damaged us */
  shotBack = false

  see(obs: Observation) {
    for (const e of obs.events as any[]) {
      if (e.type === "kill") {
        this.kills++
        if (this.kills === 3) this.k3t = obs.t
      }
      if (this.kills >= 3) continue
      if (e.type === "hit" && isMech(e.target) && !this.attackers.has(e.target)) this.shotFirst.add(e.target)
      if (e.type === "damaged" && isMech(e.by) && e.by !== obs.self.id) {
        this.attackers.add(e.by)
        if (this.shotFirst.has(e.by)) this.shotBack = true
      }
    }
  }
}

/** farx until `stop` first holds, then no fire and a walk to the nearest known mech for the rest of the match */
export function probe(stop: (s: Tally, t: number) => boolean) {
  return class Brain extends FarX {
    tally = new Tally()
    /** match time of the trigger */
    stopT: number | null = null

    act(obs: Observation) {
      this.tally.see(obs)
      // farx's decision keeps its tracking (enemies, path, zone) current; past the trigger only fire and move change
      const a = super.act(obs)
      if (this.stopT === null && !stop(this.tally, obs.t)) return a
      this.stopT ??= obs.t
      a.fire = [false, false]
      const pos = this.me.pos
      let near: number[] | null = null
      for (const e of this.enemies.values()) if (!near || d2(e.pos, pos) < d2(near, pos)) near = e.pos
      // no mech known: farx's own move (zone, search) stands
      if (near) a.move = this.unstick(this.steer([near[0], near[1]], obs), a)
      return a
    }
  }
}

/** stop at T s of match time */
export const at = (T: number) => (_s: Tally, t: number) => t >= T

/** stop at kill 3 when `c` holds then, else at kill 4 */
export const afterKill3 = (c: (s: Tally) => boolean) => (s: Tally) => s.kills >= 4 || (s.kills >= 3 && c(s))
