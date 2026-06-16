"""
WitnessRef — opaque kernel-minted token.

INVARIANT: Only pcp_kernel may mint WitnessRef values.
External construction raises TypeError regardless of token content.
The sentinel is private by naming convention; the architecture (not Python's
module system) enforces the boundary.
"""

_KERNEL_SENTINEL = object()


class WitnessRef:
    """
    Opaque proof token. Falsification is structurally impossible: the token
    is a keyed hash produced by the kernel, and the constructor is guarded.
    """
    __slots__ = ("_token",)

    def __init__(self, _token: bytes, _kernel_guard=None) -> None:
        if _kernel_guard is not _KERNEL_SENTINEL:
            raise TypeError(
                "WitnessRef is opaque: only pcp_kernel may mint witness tokens. "
                "External construction is a protocol violation."
            )
        if not isinstance(_token, bytes) or len(_token) != 32:
            raise ValueError("WitnessRef token must be exactly 32 bytes")
        self._token = _token

    def __repr__(self) -> str:
        return f"WitnessRef({self._token[:8].hex()}…)"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, WitnessRef) and self._token == other._token

    def __hash__(self) -> int:
        return hash(self._token)
