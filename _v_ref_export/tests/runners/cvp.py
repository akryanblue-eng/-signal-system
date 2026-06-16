"""CVP->V_ref bridge: maps CVP transition semantics to V_ref types via oracle."""
from src.oracle import interpret
from src.types import VRefOutput


def run(scenario: dict) -> VRefOutput:
    return interpret(scenario)
