"""Reference runner: delegates directly to the V_ref oracle."""
from src.oracle import interpret
from src.types import VRefOutput


def run(scenario: dict) -> VRefOutput:
    return interpret(scenario)
