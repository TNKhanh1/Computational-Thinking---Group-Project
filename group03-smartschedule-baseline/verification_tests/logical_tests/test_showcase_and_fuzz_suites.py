"""
Verification tests for the Testing_System suite picker (Regimes × horizon, FuzzGenerator v2 tiers)
and the "Bộ test so sánh" showcase tables with data-driven explanations.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from web.api import app  # first: puts the repo root (Testing_System) on sys.path
from web.test_showcase import LEX_LEVELS, SHOWCASE_CASES, explain_case, lexicographic_key
from web.v3_services import generate_testing_bundle, get_available_solvers

from src.controller import ScheduleController  # noqa: E402
from Testing_System.evaluator import ScheduleEvaluator  # noqa: E402
from Testing_System.evaluator.verdict_and_icee import rank_cross_solver_reports  # noqa: E402
from Testing_System.schemas import EvaluationConfig  # noqa: E402


def _reports_for(source: str, suite_id: str, seed: int):
    bundle = generate_testing_bundle(source, suite_id, seed)
    cfg = EvaluationConfig()
    reports = {}
    for s in get_available_solvers():
        out, _ = ScheduleController.solve_schedule(
            profile=bundle.profile.model_copy(deep=True),
            tasks=[t.model_copy(deep=True) for t in bundle.tasks],
            algorithm=s["key"],
            pinned_blocks=[b.model_copy(deep=True) for b in bundle.pinned_blocks] or None,
        )
        reports[s["key"]] = ScheduleEvaluator.evaluate(
            profile=bundle.profile, tasks=bundle.tasks, schedule=out,
            input_pinned_blocks=bundle.pinned_blocks or None, config=cfg,
        )
    return reports, cfg


def test_showcase_lex_key_matches_official_ranking() -> None:
    """The mirrored 12-level key must reproduce `rank_cross_solver_reports` order exactly (drift guard)."""
    for source, sid, seed in (("regime", "R1", 3), ("regime", "R5", 42), ("fuzz", "RANDOM", 1007)):
        reports, cfg = _reports_for(source, sid, seed)
        official = [e.solver_name for e in rank_cross_solver_reports(reports, cfg)]
        mirrored = sorted(reports, key=lambda k: lexicographic_key(reports[k], cfg))
        assert mirrored == official, (source, sid, seed, mirrored, official)
        assert len(lexicographic_key(reports[official[0]], cfg)) == len(LEX_LEVELS)

        exp = explain_case(official, reports, cfg)
        assert [r["solver_key"] for r in exp["rows"]] == official
        assert len(exp["pairs"]) == len(official) - 1
        assert exp["summary"].startswith(f"Hạng #1 là {official[0]}")
        assert "None" not in " ".join(p["text"] for p in exp["pairs"])


def test_catalog_exposes_every_generated_family_and_loads_them() -> None:
    client = TestClient(app)
    cat = client.get("/api/test-suites/catalog").json()
    assert [r["id"] for r in cat["regimes"]] == ["R1", "R2", "R3", "R4", "R5", "R6"]
    assert {f["id"] for f in cat["fuzz_tiers"]} == {"RANDOM", "LOOSE", "TIGHT", "OVERLOAD"}

    fz = client.post("/api/test-suites/load", json={"source": "fuzz", "id": "OVERLOAD", "seed": 7}).json()
    assert fz["source"] == "fuzz" and fz["metadata"]["fuzz_tier"] == "OVERLOAD" and fz["tasks"]

    # RANDOM reproduces the Benchmark Report's seeded tier draw (seed 1001 → TIGHT)
    rnd = client.post("/api/test-suites/load", json={"source": "fuzz", "id": "RANDOM", "seed": 1001}).json()
    assert rnd["metadata"]["fuzz_tier"] == "TIGHT"

    r14 = client.post("/api/test-suites/load", json={"source": "regime", "id": "R2", "seed": 42, "horizon_days": 14}).json()
    assert r14["metadata"]["horizon_days"] == 14

    bad = client.post("/api/test-suites/load", json={"source": "fuzz", "id": "NOPE", "seed": 1})
    assert bad.status_code == 404


def test_showcase_endpoints_list_and_case() -> None:
    client = TestClient(app)
    listing = client.get("/api/test-showcase").json()
    assert len(listing["cases"]) == len(SHOWCASE_CASES) >= 5
    assert {c["source"] for c in listing["cases"]} == {"regime", "fuzz"}

    case = client.get("/api/test-showcase/3").json()  # R5 overload: cheap & triage-focused
    assert len(case["rows"]) == len(get_available_solvers())
    assert [r["rank"] for r in case["rows"]] == list(range(1, len(case["rows"]) + 1))
    assert case["summary"] and case["verdict_line"] and case["pairs"]
    assert client.get("/api/test-showcase/999").status_code == 404


def test_ui_wires_showcase_view_and_fuzz_picker() -> None:
    client = TestClient(app)
    html = client.get("/").text
    assert 'id="viewShowcase"' in html and 'id="btnTopShowcase"' in html
    js = client.get("/js/render-showcase.js").text
    assert "/api/test-showcase" in client.get("/js/api.js").text
    assert "Giải thích bảng" in js
    modals = client.get("/js/modals.js").text
    assert 'data-load-source="fuzz"' in modals and "inpRegimeHorizon" in modals
