// farxc90: farx to kill 3, then C = "kill 3 landed before 90 s". C true: stop at once (no fire, walk to the nearest known
// mech, bots/farxwhen). C false: farx takes exactly one more kill, then stops.
// Board score = 3 + P(not C) = 3 + P(kill 3 at 90 s or later).
import { probe, afterKill3 } from "../farxwhen/brain.ts"

export const Brain = probe(afterKill3((s) => s.k3t < 90))
