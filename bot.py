"""Mech Royale entrypoint. `mechfight.run` owns the stdin/stdout loop."""
import mechfight as mf
from brain import Brain


class Bot:
    name = "last-light"

    def __init__(self, hello: mf.Hello):
        self.brain = Brain(hello)

    def act(self, obs: mf.Observation) -> mf.Action:
        try:
            return self.brain.act(obs)
        except Exception as exc:
            import sys
            print(f"act error: {exc}", file=sys.stderr, flush=True)
            me = obs.get("self") or {}
            aim = me.get("aim") or [0.0, 0.0]
            return {
                "move": [0.0, 0.0],
                "boost": False,
                "aim": [float(aim[0]), float(aim[1])],
                "fire": [False, False],
            }


mf.run(Bot)
