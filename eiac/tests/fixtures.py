"""Shared fixture objects used by both the canon test vectors and the
extract() tests. Kept separate from conftest.py so the §1.4.6 vector
generator script can import the exact same objects the tests use.
"""
from __future__ import annotations

from eiac.schema import (
    Budget,
    BudgetSet,
    BudgetWitness,
    CapEdge,
    CapSet,
    Env,
    ExecutionBundle,
    GlueTrace,
    GovEdgeWitness,
    LocalProof,
    Op,
    Proof,
    ResourceRef,
    ZoneRule,
    ZoneSelector,
    ZoneSet,
)
from eiac.canon import hash_of


def env_minimal() -> Env:
    return Env(env_id="env/minimal")


def env_full() -> Env:
    return Env(
        env_id="env/full",
        caps=CapSet(edges=(CapEdge(from_="svc/a", to="svc/b", cap="net"),)),
        budgets=BudgetSet(items=(Budget(name="tokens", limit=1000),)),
        zones=ZoneSet(
            rules=(
                ZoneRule(
                    zone="no-write-prod",
                    selector=ZoneSelector(type="match_resource", value="db/prod/*"),
                ),
            )
        ),
    )


def bundle_minimal() -> ExecutionBundle:
    return ExecutionBundle(bundle_id="bundle/minimal", ops=())


def bundle_with_ops() -> ExecutionBundle:
    return ExecutionBundle(
        bundle_id="bundle/two-ops",
        ops=(
            Op(
                op_id="op-1",
                adapter="adapter/fs",
                principal="svc/a",
                action="write",
                resources=(ResourceRef(resource_ns="fs/path", resource_id="/tmp/x"),),
                tags=("write",),
            ),
            Op(
                op_id="op-2",
                adapter="adapter/net",
                principal="svc/a",
                action="call",
                resources=(ResourceRef(resource_ns="net/host", resource_id="example.test"),),
            ),
        ),
    )


def proof_for(env: Env, bundle: ExecutionBundle) -> Proof:
    adapters = sorted({op.adapter for op in bundle.ops})
    local = tuple(
        LocalProof(adapter=a, payload_tag="STUB/v1", payload=b"ok") for a in adapters
    )
    partition = tuple(
        {"adapter": a, "op_ids": tuple(op.op_id for op in bundle.ops if op.adapter == a)}
        for a in adapters
    )
    glue = GlueTrace(adapters=tuple(adapters), op_partition=partition)
    coupling = (
        GovEdgeWitness(
            from_adapter=adapters[0],
            to_adapter=adapters[-1],
            edge="depends_on",
            op_ids=tuple(op.op_id for op in bundle.ops),
        ),
    ) if len(adapters) >= 2 else ()
    return Proof(
        env_hash=hash_of(env),
        bundle_hash=hash_of(bundle),
        local=local,
        coupling=coupling,
        glue=glue,
    )
