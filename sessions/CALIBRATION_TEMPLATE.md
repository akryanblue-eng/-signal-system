# Calibration Session — [DATE]

> **For the interviewer.**
> Fill this out during a 15-minute naïve tester session.
> No framework docs open. No prior briefing to the tester.
> Everything below maps directly to a session JSON file.

---

## Tester

- Handle: _______________
- Prior exposure to framework: **none** (required)
- Session duration: ___ min

---

## The Three Questions

Ask verbatim. Write verbatim. No paraphrasing.

**1. "Tell me what happened in one breath."**

> _______________________________________________________________

**2. "Where did you feel like you regained control after things went wrong?"**

> _______________________________________________________________

**3. "What place do you remember most clearly?"**

> _______________________________________________________________

---

## Go / No-Go Signals

Mark immediately after hearing the three answers. No framework lookup.

| # | Signal | Pass |
|---|--------|------|
| 1 | Player describes **route** (not mission) | ☐ |
| 2 | Failure produced a **story** (not a reset) | ☐ |
| 3 | "I escaped because…" contains **location + mistake + recovery** | ☐ |
| 4 | You classified the run **without rereading framework** | ☐ |
| 5 | You identified the **breakpoint class in <30 seconds** | ☐ |

Signals passed: ___ / 5

---

## Fragility Notes

Patterns that felt edge or outside-envelope (optional):

> _______________________________________________________________

---

## Raw Verdict (interviewer gut check)

- [ ] SHIP — gate is real, outcomes classifiable
- [ ] TUNE — gate is describing, not catching
- [ ] KILL — identity broke or signals absent

---

## Next Step

Once session is over, create the session JSON file:

```
sessions/session_YYYY_MM_DD_NNN.json
```

Then run:

```bash
python scripts/calibrate.py sessions/session_YYYY_MM_DD_NNN.json
```

The script derives the formal verdict from `classifier_checks` + perturbation envelope.
Your gut check above should match. If it doesn't — that gap is a signal worth logging.
