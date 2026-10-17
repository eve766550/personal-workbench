from datetime import date
from math import isclose

from training import analyze_history, build_training_plan


def ride(ride_date, distance_km, fatigue=None):
    return {
        "ride_date": ride_date.isoformat(),
        "distance_km": distance_km,
        "fatigue": fatigue,
    }


def test_analyze_history_uses_recent_six_weeks_and_reports_fatigue():
    analysis = analyze_history(
        [
            ride(date(2026, 10, 16), 40, 6),
            ride(date(2026, 10, 10), 30, 8),
            ride(date(2026, 9, 1), 99, 1),
        ],
        as_of=date(2026, 10, 17),
    )

    assert analysis["recent_ride_count"] == 2
    assert analysis["longest_distance_km"] == 40
    assert analysis["average_weekly_km"] == 35
    assert analysis["average_fatigue"] == 7
    assert analysis["fatigue_factor"] == 0.9


def test_build_training_plan_increases_volume_and_adds_recovery_week():
    analysis = analyze_history(
        [ride(date(2026, 10, 16), 40, 4)],
        as_of=date(2026, 10, 17),
    )

    plan = build_training_plan(
        analysis,
        start_date=date(2026, 10, 19),
        weeks=8,
        rides_per_week=3,
        goal="endurance",
    )

    weekly_targets = plan["weekly_targets"]
    assert len(weekly_targets) == 8
    assert weekly_targets[1]["distance_km"] > weekly_targets[0]["distance_km"]
    assert weekly_targets[3]["is_recovery"] is True
    assert weekly_targets[3]["distance_km"] < weekly_targets[2]["distance_km"]
    assert weekly_targets[4]["distance_km"] > weekly_targets[3]["distance_km"]
    assert len(plan["sessions"]) == 24

    for week in weekly_targets:
        session_total = sum(
            session["target_distance_km"]
            for session in plan["sessions"]
            if session["week_number"] == week["week_number"]
        )
        assert isclose(session_total, week["distance_km"], abs_tol=0.1)


def test_build_training_plan_without_history_uses_conservative_start():
    analysis = analyze_history([], as_of=date(2026, 10, 17))

    plan = build_training_plan(
        analysis,
        start_date=date(2026, 10, 19),
        weeks=4,
        rides_per_week=2,
        goal="consistency",
    )

    assert plan["weekly_targets"][0]["distance_km"] == 20
    assert plan["data_warning"]
    assert len(plan["sessions"]) == 8

