// farxc2a: farx to kill 3, then C = "2+ distinct mechs damaged us before kill 3". C true: stop at once (no fire, walk to
// the nearest known mech, bots/farxwhen). C false: farx takes exactly one more kill, then stops.
// Board score = 3 + P(not C) = 3 + P(at most one mech damaged us before kill 3).
import { probe, afterKill3 } from "../farxwhen/brain.ts"

export const Brain = probe(afterKill3((s) => s.attackers.size >= 2))
