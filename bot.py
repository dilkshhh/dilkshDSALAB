"""Mech Royale entrypoint. `mechfight.run` owns the stdin/stdout loop."""
import mechfight as mf
from brain import Brain


class Bot:
    name = "last-light"

    def __init__(self, hello: mf.Hello):
        self.brain = Brain(hello)

    def act(self, obs: mf.Observation) -> mf.Action:
        return self.brain.act(obs)


mf.run(Bot)
