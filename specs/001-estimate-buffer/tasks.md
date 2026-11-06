# Feature 001 — Task Breakdown

| # | Task | Files | Done |
|---|---|---|:-:|
| T1 | Pure buffer module (habit → multiplier, rounding rule, reason) | `src/estimate_buffer.py` | ✅ |
| T2 | Model fields `estimate_habit`, `buffer_multiplier`; planned duration uses the rule | `src/models.py` | ✅ |
| T3 | Controller: apply buffer to task copies, annotate blocks, overrun on raw estimate | `src/controller.py` | ✅ |
| T4 | API: read the habit from all three payload shapes, return `new_estimate_min` | `web/api.py` | ✅ |
| T5 | Workbench: selector, planned preview, table column, overrun fix | `web/index.html`, `web/app.js` | ✅ |
| T6 | Tests for AC1–AC7; give the gap test its missing input | `verification_tests/logical_tests/test_estimate_buffer.py`, `development_gap_tests/` | ✅ |
| T7 | Run `clean_runner.py --pass` and the full suite; check determinism | — | ✅ |
| T8 | Update team change logs (EN + VI) | `agents/commit_changes.md`, `docs/commit_changes.md` | ✅ |
