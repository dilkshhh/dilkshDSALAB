// farxt<T> plays farx's game until T s of match time, farxc* until kill 3 and then until kill 4 unless their condition
// holds at kill 3; past the trigger they hold fire.
import { test, expect } from "bun:test"
import { readFileSync } from "node:fs"
import { gunzipSync } from "node:zlib"
import { World } from "../../src/world.ts"
import { Nav } from "../../src/nav.ts"
import { Brain as FarX } from "../farx/brain.ts"
import { Brain as T60 } from "../farxt60/brain.ts"
import { Brain as C2a } from "../farxc2a/brain.ts"
import { Brain as C90 } from "../farxc90/brain.ts"
import { Brain as Cret } from "../farxcret/brain.ts"
import { probe, at } from "./brain.ts"

const lines = gunzipSync(readFileSync(new URL("../../check/stream.jsonl.gz", import.meta.url))).toString().split("\n").filter(Boolean).map((l) => JSON.parse(l))
const w = new World(new URL("../../arena", import.meta.url).pathname)
const nav = new Nav(w)
const hello = lines[0]
const obs = lines.filter((o) => o.type === "obs")
// the recorded stream (we are mech 3) has no kills; we hit mech 10 at obs 57, 60 and 71, and it first damages us at obs 79
const KILLS = [30, 45, 60, 75, 90, 105]
/** the stream with our kills at `kills` and `extra` events added at their observation index; `dt` shifts match time */
const stream = (kills: number[], extra: Record<number, any[]> = {}, dt = 0) => obs.map((o, i) => ({
  ...o,
  t: o.t + dt,
  events: [...o.events, ...(extra[i] ?? []), ...(kills.includes(i) ? [{ type: "kill", target: 90 + i }] : [])],
}))
const play = (b: any, s: any[]) => s.map((o) => {
  b.until = Infinity
  return b.act(o)
})
const fires = (a: any[]) => a.some((x) => x.fire?.[0] || x.fire?.[1])
const hurt = (by: number) => ({ type: "damaged", amount: 45, weapon: "gun", bearing: 0, by })

/** the probe makes farx's decisions before obs `cut` and holds fire from it on, where farx fires */
function stopsAt(P: any, s: any[], cut: number) {
  const a = play(new P(hello, w, nav, null), s)
  const f = play(new FarX(hello, w, nav, null), s)
  expect(a.slice(0, cut)).toEqual(f.slice(0, cut))
  expect(fires(f.slice(cut))).toBe(true)
  expect(fires(a.slice(cut))).toBe(false)
}

test("a time probe past the stream's end makes every farx decision and draws the same random numbers", () => {
  const s = stream(KILLS)
  const farx = new FarX(hello, w, nav, null)
  const p = new (probe(at(60)))(hello, w, nav, null)
  expect(play(p, s)).toEqual(play(farx, s))
  expect(p.rng()).toBe(farx.rng())
})

test("farxt60 holds fire from the first observation at 60 s on", () => {
  // obs 100 is at 10 s, so 50 s later puts it at 60 s
  expect(obs[100].t).toBe(10)
  stopsAt(T60, stream(KILLS, {}, 50), 100)
})

test("farxc2a with two mechs damaging us before kill 3 stops at kill 3", () => {
  stopsAt(C2a, stream(KILLS, { 50: [hurt(7), hurt(9)] }), 60)
})

test("farxc2a with one attacker, and our own splash, takes kill 4 before it stops", () => {
  stopsAt(C2a, stream(KILLS, { 50: [hurt(7), hurt(3)] }), 75)
})

test("farxc90 with kill 3 before 90 s stops at kill 3", () => {
  stopsAt(C90, stream(KILLS), 60)
})

test("farxc90 with kill 3 at 90 s or later takes kill 4 before it stops", () => {
  stopsAt(C90, stream(KILLS, {}, 90), 75)
})

test("farxcret with mech 10 shooting back (obs 79) after our hits (obs 57) before kill 3 stops at kill 3", () => {
  stopsAt(Cret, stream([30, 45, 85, 120]), 85)
})

test("farxcret before anyone we hit shot back takes kill 4 before it stops", () => {
  stopsAt(Cret, stream(KILLS), 75)
})

test("farxcret decides at kill 3: mech 10 shooting back after it (obs 79) does not stop it before kill 4", () => {
  stopsAt(Cret, stream([30, 45, 60, 120]), 120)
})

test("farxcret counts a mech that damaged us before our first hit as a hunter, not a reply", () => {
  stopsAt(Cret, stream([30, 45, 85, 120], { 50: [hurt(10)] }), 120)
})
