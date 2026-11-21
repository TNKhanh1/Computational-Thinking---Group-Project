"""
Verification tests for P3.3: Focus Timer (Pomodoro -> M7), EWMA Alpha Calibration Card,
and Web Notification Reminder UI/JS Contracts.
"""

from __future__ import annotations

from pathlib import Path

BASELINE_ROOT = Path(__file__).resolve().parents[2]


def test_p3_3_focus_timer_calibration_and_notification_contracts() -> None:
    html = (BASELINE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    js = (BASELINE_ROOT / "web" / "app.js").read_text(encoding="utf-8")

    required_dom_ids = [
        "stFocusTimerPanel",
        "stFocusPresetSelect",
        "stFocusTimerDisplay",
        "stFocusTimerStatus",
        "btnFocusStart",
        "btnFocusPause",
        "btnFocusReset",
        "btnFocusCompleteM7",
        "stCalibrationAdvisoryCard",
        "stCalibrationMetrics",
        "stCalibrationNote",
        "btnRefreshCalibration",
        "btnApplyCalibrationAlpha",
        "btnStNotifyToggle",
    ]
    for dom_id in required_dom_ids:
        assert f'id="{dom_id}"' in html, f"Missing P3.3 DOM id in web/index.html: {dom_id}"

    required_js_handlers = [
        "function changeFocusTimerPreset(",
        "function startFocusTimer(",
        "function pauseFocusTimer(",
        "function resetFocusTimer(",
        "async function completeFocusTimerToM7(",
        "async function refreshCalibrationAdvisory(",
        "async function applyRecommendedCalibrationAlpha(",
        "async function toggleScheduleNotifications(",
        "/api/tasks/calibration",
    ]
    for sym in required_js_handlers:
        assert sym in js, f"Missing P3.3 JS handler/route in web/app.js: {sym}"
