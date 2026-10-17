"""骑行复盘助手的 Flask 应用入口。"""

from datetime import date, datetime
import os
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, url_for

from db import (
    close_db,
    create_ride,
    create_training_plan,
    delete_ride,
    get_ride,
    get_training_plan,
    get_training_session,
    get_training_sessions,
    init_db,
    list_rides,
    list_training_plans,
    update_ride,
    update_training_session,
)
from training import GOAL_OPTIONS, analyze_history, build_training_plan


FIELD_NAMES = (
    "ride_date",
    "distance_km",
    "duration_minutes",
    "average_speed",
    "average_heart_rate",
    "max_heart_rate",
    "elevation_gain",
    "fatigue",
    "notes",
)


def create_app(test_config=None):
    """创建 Flask 应用。

    测试时可以传入 DATABASE 临时路径，不会污染正式数据。
    """

    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "cycling-review-dev-key"),
        DATABASE=str(Path(app.root_path) / "data" / "cycling.sqlite3"),
    )

    if test_config is not None:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.template_filter("num")
    def format_number(value, decimals=1):
        """在页面上显示好读的数字，空值显示短横线。"""

        if value is None or value == "":
            return "-"
        try:
            formatted = f"{float(value):.{decimals}f}"
        except (TypeError, ValueError):
            return str(value)
        return formatted.rstrip("0").rstrip(".")

    @app.route("/")
    def index():
        return render_template("index.html", records=list_rides())

    @app.route("/plans")
    def plans():
        return render_template("plans.html", plans=list_training_plans())

    @app.route("/plans/new", methods=("GET", "POST"))
    def new_plan():
        form = default_plan_form()
        errors = {}
        analysis = analyze_history(list_rides(), as_of=date.today())

        if request.method == "POST":
            form = plan_form_from_request()
            analysis_date = parse_date(form.get("start_date")) or date.today()
            analysis = analyze_history(list_rides(), as_of=analysis_date)
            settings, errors = validate_plan_form(form)
            if not errors:
                plan = build_training_plan(analysis, **settings)
                plan_id = create_training_plan(plan, plan["sessions"])
                flash("训练计划已生成", "success")
                return redirect(url_for("plan_detail", plan_id=plan_id))

        status_code = 400 if errors else 200
        return render_template(
            "plan_form.html",
            form=form,
            errors=errors,
            analysis=analysis,
            goal_options=GOAL_OPTIONS,
        ), status_code

    @app.route("/plans/<int:plan_id>")
    def plan_detail(plan_id):
        plan = get_training_plan(plan_id)
        if plan is None:
            abort(404)
        return render_plan_detail(plan)

    @app.post("/plans/<int:plan_id>/sessions/<int:session_id>/update")
    def update_plan_session(plan_id, session_id):
        plan = get_training_plan(plan_id)
        session = get_training_session(session_id, plan_id)
        if plan is None or session is None:
            abort(404)

        raw_distance = request.form.get("target_distance_km", "").strip()
        errors = {}
        try:
            target_distance = float(raw_distance)
        except ValueError:
            target_distance = None
            errors["target_distance_km"] = "训练距离必须是数字"

        if target_distance is not None and target_distance <= 0:
            errors["target_distance_km"] = "训练距离必须大于 0"
        if target_distance is not None and target_distance > 1000:
            errors["target_distance_km"] = "训练距离不能超过 1000 km"

        if errors:
            return render_plan_detail(plan, errors=errors), 400

        completed = request.form.get("completed") == "1"
        update_training_session(session_id, plan_id, target_distance, completed)
        flash("训练日已更新", "success")
        return redirect(url_for("plan_detail", plan_id=plan_id))

    @app.route("/records/new", methods=("GET", "POST"))
    def new_record():
        form = default_form()
        errors = {}

        if request.method == "POST":
            form = form_from_request()
            ride, errors = validate_form(form)
            if not errors:
                ride_id = create_ride(ride)
                flash("骑行记录已保存", "success")
                return redirect(url_for("record_detail", record_id=ride_id))

        status_code = 400 if errors else 200
        return render_template(
            "form.html",
            form=form,
            errors=errors,
            is_edit=False,
        ), status_code

    @app.route("/records/<int:record_id>")
    def record_detail(record_id):
        record = get_ride(record_id)
        if record is None:
            abort(404)
        return render_template("detail.html", record=record)

    @app.route("/records/<int:record_id>/edit", methods=("GET", "POST"))
    def edit_record(record_id):
        record = get_ride(record_id)
        if record is None:
            abort(404)

        form = dict(record)
        errors = {}
        if request.method == "POST":
            form = form_from_request()
            ride, errors = validate_form(form)
            if not errors:
                update_ride(record_id, ride)
                flash("骑行记录已更新", "success")
                return redirect(url_for("record_detail", record_id=record_id))

        status_code = 400 if errors else 200
        return render_template(
            "form.html",
            form=form,
            errors=errors,
            is_edit=True,
            record_id=record_id,
        ), status_code

    @app.post("/records/<int:record_id>/delete")
    def remove_record(record_id):
        if get_ride(record_id) is None:
            abort(404)
        delete_ride(record_id)
        flash("骑行记录已删除", "success")
        return redirect(url_for("index"))

    return app


def render_plan_detail(plan, errors=None):
    sessions = get_training_sessions(plan["id"])
    return render_template(
        "plan_detail.html",
        plan=plan,
        sessions=sessions,
        week_groups=group_sessions_by_week(sessions),
        rationale=(plan["rationale"] or "").splitlines(),
        errors=errors or {},
    )


def default_form():
    """新建页面的初始值。"""

    return {name: "" for name in FIELD_NAMES} | {"ride_date": date.today().isoformat()}


def default_plan_form():
    return {
        "goal": "endurance",
        "weeks": "4",
        "rides_per_week": "3",
        "start_date": date.today().isoformat(),
    }


def form_from_request():
    """只取允许保存的字段，并去除首尾空格。"""

    return {name: request.form.get(name, "").strip() for name in FIELD_NAMES}


def plan_form_from_request():
    return {
        "goal": request.form.get("goal", "").strip(),
        "weeks": request.form.get("weeks", "").strip(),
        "rides_per_week": request.form.get("rides_per_week", "").strip(),
        "start_date": request.form.get("start_date", "").strip(),
    }


def validate_form(form):
    """校验表单并把字符串转换成适合保存到 SQLite 的类型。"""

    errors = {}
    ride = {}

    ride_date = form.get("ride_date", "")
    if not ride_date:
        errors["ride_date"] = "请选择日期"
    else:
        try:
            datetime.strptime(ride_date, "%Y-%m-%d")
        except ValueError:
            errors["ride_date"] = "日期格式不正确"
    ride["ride_date"] = ride_date

    required_float("distance_km", "距离", form, ride, errors, minimum=0)
    required_int("duration_minutes", "骑行时长", form, ride, errors, minimum=0)
    optional_float("average_speed", "平均速度", form, ride, errors, minimum=0)
    optional_int("average_heart_rate", "平均心率", form, ride, errors, minimum=0)
    optional_int("max_heart_rate", "最大心率", form, ride, errors, minimum=0)
    optional_int("elevation_gain", "累计爬升", form, ride, errors, minimum=0)
    optional_int("fatigue", "疲劳程度", form, ride, errors, minimum=1, maximum=10)

    notes = form.get("notes", "")
    if len(notes) > 2000:
        errors["notes"] = "备注不能超过 2000 个字符"
    ride["notes"] = notes or None

    return ride, errors


def validate_plan_form(form):
    errors = {}
    goal = form.get("goal", "")
    if goal not in GOAL_OPTIONS:
        errors["goal"] = "请选择训练目标"

    weeks = parse_int_choice(form.get("weeks"), (4, 8), "计划周期只能选择 4 周或 8 周", errors, "weeks")
    rides_per_week = parse_int_choice(
        form.get("rides_per_week"),
        (2, 3, 4),
        "每周骑行次数只能选择 2、3 或 4 次",
        errors,
        "rides_per_week",
    )

    start_date = form.get("start_date", "")
    if not start_date:
        errors["start_date"] = "请选择计划开始日期"
    elif parse_date(start_date) is None:
        errors["start_date"] = "开始日期格式不正确"

    settings = {
        "goal": goal,
        "weeks": weeks,
        "rides_per_week": rides_per_week,
        "start_date": start_date,
    }
    return settings, errors


def parse_int_choice(value, choices, message, errors, field):
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors[field] = message
        return None
    if number not in choices:
        errors[field] = message
        return None
    return number


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def group_sessions_by_week(sessions):
    groups = []
    for session in sessions:
        if not groups or groups[-1]["week_number"] != session["week_number"]:
            groups.append(
                {
                    "week_number": session["week_number"],
                    "sessions": [],
                    "total_distance_km": 0,
                    "is_recovery": session["week_number"] % 4 == 0,
                }
            )
        groups[-1]["sessions"].append(session)
        groups[-1]["total_distance_km"] += session["target_distance_km"]
    for group in groups:
        group["total_distance_km"] = round(group["total_distance_km"], 1)
    return groups


def required_float(field, label, form, ride, errors, minimum=None):
    value = form.get(field, "")
    if not value:
        errors[field] = f"{label}不能为空"
        ride[field] = None
        return
    try:
        number = float(value)
    except ValueError:
        errors[field] = f"{label}必须是数字"
        ride[field] = None
        return
    if minimum is not None and number <= minimum:
        errors[field] = f"{label}必须大于 {minimum:g}"
    ride[field] = number


def required_int(field, label, form, ride, errors, minimum=None):
    value = form.get(field, "")
    if not value:
        errors[field] = f"{label}不能为空"
        ride[field] = None
        return
    try:
        number = int(value)
    except ValueError:
        errors[field] = f"{label}必须是整数"
        ride[field] = None
        return
    if minimum is not None and number <= minimum:
        errors[field] = f"{label}必须大于 {minimum:g}"
    ride[field] = number


def optional_float(field, label, form, ride, errors, minimum=None):
    value = form.get(field, "")
    if not value:
        ride[field] = None
        return
    try:
        number = float(value)
    except ValueError:
        errors[field] = f"{label}必须是数字"
        ride[field] = None
        return
    if minimum is not None and number < minimum:
        errors[field] = f"{label}不能小于 {minimum:g}"
    ride[field] = number


def optional_int(field, label, form, ride, errors, minimum=None, maximum=None):
    value = form.get(field, "")
    if not value:
        ride[field] = None
        return
    try:
        number = int(value)
    except ValueError:
        errors[field] = f"{label}必须是整数"
        ride[field] = None
        return
    if minimum is not None and number < minimum:
        errors[field] = f"{label}不能小于 {minimum:g}"
    if maximum is not None and number > maximum:
        errors[field] = f"{label}必须是 {minimum} 到 {maximum} 分"
    ride[field] = number


# Gunicorn uses this module-level application object in production.
app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=True,
    )

