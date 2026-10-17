# Training Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已有骑行记录页面中增加基于最近 6 周数据的可解释训练计划生成、保存、查看、修改和完成标记。

**Architecture:** `training.py` 负责无副作用的历史分析和计划生成；`db.py` 负责两个新 SQLite 表；`app.py` 负责表单校验和路由；Jinja 模板负责移动端页面。计划生成后保存快照，因此以后修改骑行记录不会悄悄改变已生成的计划。

**Tech Stack:** Python 3、Flask、SQLite、Jinja2、HTML、CSS、少量原生 JavaScript、pytest。

**Spec:** `docs/superpowers/specs/2026-10-17-training-plan-design.md`

## Global Constraints

- 只使用本地数据，不接入付费 API。
- 计划周数只允许 4 或 8 周；每周骑行次数只允许 2、3、4 次。
- 最近 6 周有数据时以近期平均周里程为基础；没有数据时使用 20 km 保守起点并提示用户。
- 普通周增加 8%；每 4 周设置上一普通周 70% 的恢复周。
- 所有 SQLite 查询使用参数化占位符。
- 页面保持手机优先布局，不新增注册、登录或复杂前端框架。

### Task 1: 先写训练分析与生成算法测试

**Files:**
- Create: `tests/test_training.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Tests will consume `training.analyze_history()` and `training.build_training_plan()`.
- Flask tests will consume `POST /plans/new` and `POST /plans/<plan_id>/sessions/<session_id>/update`.

- [x] Write tests for recent weekly average, fatigue reduction, recovery week, and no-history fallback.
- [x] Run `py -m pytest -q` and confirm the new tests fail because the module/routes do not exist.

### Task 2: Implement pure training algorithm

**Files:**
- Create: `training.py`

**Interfaces:**
- `analyze_history(records, as_of=None) -> dict`
- `build_training_plan(analysis, start_date, weeks, rides_per_week, goal) -> dict`

- [x] Implement the six-week analysis window and numeric summary.
- [x] Implement conservative start, 8% progression, recovery weeks, session distribution, and rationale strings.
- [x] Run pure algorithm tests and confirm they pass.

### Task 3: Persist plans and sessions in SQLite

**Files:**
- Modify: `db.py`
- Modify: `app.py`

**Interfaces:**
- `db.create_training_plan(plan, sessions) -> int`
- `db.list_training_plans() -> list[sqlite3.Row]`
- `db.get_training_plan(plan_id) -> sqlite3.Row | None`
- `db.get_training_sessions(plan_id) -> list[sqlite3.Row]`
- `db.get_training_session(session_id, plan_id) -> sqlite3.Row | None`
- `db.update_training_session(session_id, plan_id, target_distance_km, completed) -> int`

- [x] Add idempotent tables and foreign-key enforcement without changing the existing `rides` table.
- [x] Add form parsing, validation, generation, and update routes.
- [x] Run all tests and fix persistence or validation failures.

### Task 4: Add mobile pages and navigation

**Files:**
- Create: `templates/plans.html`
- Create: `templates/plan_form.html`
- Create: `templates/plan_detail.html`
- Modify: `templates/base.html`
- Modify: `templates/index.html`
- Modify: `static/style.css`

- [x] Add navigation and an entry point from the records page.
- [x] Render analysis summary, rationale, weekly groups, editable distance, and completed state.
- [x] Add responsive styles for narrow screens and verify pages return usable HTML.

### Task 5: Documentation and verification

**Files:**
- Modify: `README.md`

- [x] Explain the plan algorithm in beginner-friendly language and list the new routes.
- [x] Run pytest, Python compile checks, JavaScript syntax checks, and HTTP smoke checks against the running Flask app.
- [x] Confirm no parent-directory files were changed.
