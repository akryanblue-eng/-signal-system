// Verifies that substring-style matches do NOT fire.
// "latest" must not match "test".  "speculative" must not match "spec".
// "OracleTravelerStateRunner" — TravelerState appears as a substring of a
// different identifier, not a call; must NOT emit STATE_INIT.
func processLatest(_ speculative: Bool) -> Bool { speculative }
let label = "OracleTravelerStateRunner"
