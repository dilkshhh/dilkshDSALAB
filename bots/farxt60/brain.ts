// farxt60: farx until 60 s of match time, then no fire and a walk to the nearest known mech (bots/farxwhen).
// Board score = E[our kills before 60 s].
import { probe, at } from "../farxwhen/brain.ts"

export const Brain = probe(at(60))
