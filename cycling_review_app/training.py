"""基于本地骑行记录生成训练计划的纯 Python 规则。

这个模块不读写数据库，也不依赖 Flask，方便初学者单独理解和测试算法。
"""

from collections import defaultdict
from datetime import date, datetime, timedelta


GOAL_OPTIONS = {
    "endurance": "提升耐力",
    "long_distance": "挑战更长距离",
    "consistency": "建立规律骑行",
}

SESSION_TEXT = {
    "easy": {
        "title": "轻松骑",
        "description": "保持能说完整句子的强度，完成后应该感觉轻松。",
    },
    "tempo": {
        "title": "节奏骑",
        "description": "热身后做 2 次稳定偏快骑行，中间用轻松骑恢复，不追求冲刺。",
    },
    "long": {
        "title": "长距离骑",
        "description": "全程控制节奏，不追求速度，最后仍应能保持动作稳定。",
    },
    "recovery": {
        "title": "恢复骑",
        "description": "轻松转腿，主要目的是恢复，不追求里程和速度。",
    },
}


def analyze_history(records, as_of=None):
    """分析截至某天前最近六周的骑行记录。"""

    as_of = _as_date(as_of) or date.today()
    window_start = as_of - timedelta(days=41)
    recent = []

    for record in records:
        ride_date = _as_date(_value(record, "ride_date"))
        distance = _number(_value(record, "distance_km"))
        if ride_date is None or distance is None:
            continue
        if window_start <= ride_date <= as_of and distance > 0:
            recent.append(
                {
                    "ride_date": ride_date,
                    "distance_km": distance,
                    "fatigue": _number(_value(record, "fatigue")),
                }
            )

    if not recent:
        return {
            "window_start": window_start.isoformat(),
            "window_end": as_of.isoformat(),
            "recent_ride_count": 0,
            "average_weekly_km": 0,
            "longest_distance_km": 0,
            "average_fatigue": None,
            "fatigue_factor": 1.0,
            "data_warning": "最近 6 周没有可用记录，计划将使用 20 km 的保守起始周总量。",
        }

    weekly_totals = defaultdict(float)
    for record in recent:
        monday = record["ride_date"] - timedelta(days=record["ride_date"].weekday())
        weekly_totals[monday] += record["distance_km"]

    first_week = min(weekly_totals)
    current_week = as_of - timedelta(days=as_of.weekday())
    calendar_weeks = ((current_week - first_week).days // 7) + 1
    weeks_used = max(1, min(6, calendar_weeks))

    fatigue_values = [record["fatigue"] for record in recent if record["fatigue"] is not None]
    average_fatigue = round(sum(fatigue_values) / len(fatigue_values), 1) if fatigue_values else None
    if average_fatigue is not None and average_fatigue >= 8:
        fatigue_factor = 0.75
    elif average_fatigue is not None and average_fatigue >= 6:
        fatigue_factor = 0.9
    else:
        fatigue_factor = 1.0

    warning = None
    if average_fatigue is not None and average_fatigue >= 6:
        warning = "近期平均疲劳程度偏高，起始周总量已自动降低。"

    return {
        "window_start": window_start.isoformat(),
        "window_end": as_of.isoformat(),
        "recent_ride_count": len(recent),
        "average_weekly_km": round(sum(weekly_totals.values()) / weeks_used, 1),
        "longest_distance_km": round(max(record["distance_km"] for record in recent), 1),
        "average_fatigue": average_fatigue,
        "fatigue_factor": fatigue_factor,
        "data_warning": warning,
    }


def build_training_plan(analysis, start_date, weeks, rides_per_week, goal):
    """根据分析结果创建计划字典，不保存数据库。"""

    if goal not in GOAL_OPTIONS:
        raise ValueError("训练目标不正确")
    if weeks not in (4, 8):
        raise ValueError("计划周期只能是 4 或 8 周")
    if rides_per_week not in (2, 3, 4):
        raise ValueError("每周骑行次数只能是 2 到 4 次")

    start_date = _as_date(start_date)
    if start_date is None:
        raise ValueError("计划开始日期不正确")

    if analysis["recent_ride_count"] == 0:
        starting_weekly = 20.0
    else:
        starting_weekly = analysis["average_weekly_km"] * 0.9 * analysis["fatigue_factor"]
        starting_weekly = max(10.0, min(120.0, round(starting_weekly, 1)))

    weekly_targets = []
    sessions = []
    normal_weekly = starting_weekly
    for week_number in range(1, weeks + 1):
        is_recovery = week_number % 4 == 0
        if week_number > 1 and not is_recovery:
            normal_weekly = round(normal_weekly * 1.08, 1)
        weekly_distance = round(normal_weekly * 0.7, 1) if is_recovery else normal_weekly
        weekly_targets.append(
            {
                "week_number": week_number,
                "distance_km": weekly_distance,
                "is_recovery": is_recovery,
            }
        )

        specifications = _session_specifications(rides_per_week, goal, is_recovery)
        distances = _split_distance(weekly_distance, specifications)
        offsets = _date_offsets(rides_per_week)
        for session_number, ((session_type, ratio), target_distance, day_offset) in enumerate(
            zip(specifications, distances, offsets), start=1
        ):
            text = SESSION_TEXT[session_type]
            sessions.append(
                {
                    "week_number": week_number,
                    "session_number": session_number,
                    "session_date": (start_date + timedelta(days=(week_number - 1) * 7 + day_offset)).isoformat(),
                    "session_type": session_type,
                    "title": text["title"],
                    "target_distance_km": target_distance,
                    "description": text["description"],
                    "completed": 0,
                }
            )

    rationale = [
        (
            f"参考最近 6 周的 {analysis['recent_ride_count']} 次记录，"
            f"平均每周约 {analysis['average_weekly_km']:.1f} km，"
            f"最长单次 {analysis['longest_distance_km']:.1f} km。"
        ),
        "普通周在上一普通周基础上增加 8%，每 4 周安排一次恢复周。",
        f"每周安排 {rides_per_week} 次训练，包含轻松骑和逐步增加的长距离骑。",
    ]
    if analysis["average_fatigue"] is not None:
        rationale.insert(1, f"近期平均疲劳程度为 {analysis['average_fatigue']:.1f}/10，已用于调整起始训练量。")
    if analysis["data_warning"]:
        rationale.insert(0, analysis["data_warning"])

    return {
        "start_date": start_date.isoformat(),
        "weeks": weeks,
        "rides_per_week": rides_per_week,
        "goal": goal,
        "goal_label": GOAL_OPTIONS[goal],
        "baseline_weekly_km": analysis["average_weekly_km"],
        "baseline_longest_km": analysis["longest_distance_km"],
        "average_fatigue": analysis["average_fatigue"],
        "source_ride_count": analysis["recent_ride_count"],
        "data_warning": analysis["data_warning"],
        "rationale": rationale,
        "weekly_targets": weekly_targets,
        "sessions": sessions,
    }


def _session_specifications(rides_per_week, goal, is_recovery):
    if is_recovery:
        if rides_per_week == 2:
            return [("recovery", 0.5), ("easy", 0.5)]
        if rides_per_week == 3:
            return [("recovery", 0.3), ("easy", 0.3), ("long", 0.4)]
        return [("recovery", 0.2), ("easy", 0.3), ("easy", 0.2), ("long", 0.3)]

    if rides_per_week == 2:
        return [("easy", 0.45), ("long", 0.55)]
    if rides_per_week == 3:
        if goal == "consistency":
            return [("easy", 0.35), ("easy", 0.25), ("long", 0.4)]
        if goal == "long_distance":
            return [("easy", 0.25), ("tempo", 0.25), ("long", 0.5)]
        return [("easy", 0.3), ("tempo", 0.3), ("long", 0.4)]
    if goal == "consistency":
        return [("recovery", 0.2), ("easy", 0.3), ("easy", 0.2), ("long", 0.3)]
    return [("recovery", 0.2), ("easy", 0.25), ("tempo", 0.25), ("long", 0.3)]


def _split_distance(weekly_distance, specifications):
    distances = [round(weekly_distance * ratio, 1) for _session_type, ratio in specifications]
    distances[-1] = round(distances[-1] + weekly_distance - sum(distances), 1)
    return distances


def _date_offsets(rides_per_week):
    return {2: [2, 6], 3: [1, 3, 6], 4: [0, 2, 4, 6]}[rides_per_week]


def _value(record, key, default=None):
    try:
        return record[key]
    except (KeyError, IndexError, TypeError):
        return default


def _number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None

