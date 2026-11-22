// farxcret: farx to kill 3, then C = "a mech we hit before it ever damaged us (a house bot, not a hunter) damaged us
// afterwards, before kill 3". C true: stop at once (no fire, walk to the nearest known mech, bots/farxwhen). C false:
// farx takes exactly one more kill, then stops.
// Board score = 3 + P(not C) = 3 + P(no mech we shot first shot back before kill 3).
import { probe, afterKill3 } from "../farxwhen/brain.ts"

export const Brain = probe(afterKill3((s) => s.shotBack))
