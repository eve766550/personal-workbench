# 骑行复盘助手

第一阶段的个人骑行数据分析网页，使用 Python、Flask、SQLite、HTML、CSS 和 JavaScript 实现。

## 功能

- 录入日期、距离、时长、速度、心率、爬升、疲劳程度和备注。
- 在列表中查看所有骑行记录，按日期倒序排列。
- 查看单次骑行的完整详情。
- 修改或删除已有记录。
- 根据最近 6 周骑行记录生成 4 周或 8 周训练计划。
- 查看每周训练安排，修改训练距离并标记训练完成。
- 数据保存在 `data/cycling.sqlite3`，程序重启后仍然保留。

## Windows 启动

在当前目录打开 PowerShell：

```powershell
cd cycling_review_app
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

看到 Flask 启动提示后，在浏览器打开 <http://127.0.0.1:5000>。

如果 PowerShell 禁止激活虚拟环境，也可以直接使用虚拟环境里的 Python：

```powershell
\.venv\Scripts\python.exe -m pip install -r requirements.txt
\.venv\Scripts\python.exe app.py
```

## 部署为公开网址（Render）

这个项目也可以部署到 Render，得到一个任何人都能打开的 `onrender.com` 网址。GitHub 只负责保存代码，Render 负责运行 Flask 服务。

1. 打开 <https://render.com>，使用 GitHub 登录。
2. 点击 **New > Web Service**，选择 `eve766550/personal-workbench` 仓库。
3. 在 **Root Directory** 填写 `cycling_review_app`。
4. 设置 **Build Command** 为 `pip install -r requirements.txt`。
5. 设置 **Start Command** 为 `gunicorn app:app`。
6. 选择免费实例并点击部署。项目已经包含 `Procfile`，它也记录了生产环境启动命令。

部署完成后，Render 会生成一个公开网址。免费实例可能会自动休眠，第一次打开时需要等待几秒。

公开部署前请注意两点：

- 当前版本没有用户注册和登录，所以公开网址上的任何人都可以查看、添加、修改和删除骑行记录。建议公开演示时使用示例数据，不要录入隐私数据。
- SQLite 文件适合本地学习和演示。免费云服务的本地磁盘可能在重新部署或重启后被清空；如果要长期保存真实数据，需要后续接入 PostgreSQL 或带持久磁盘的部署方案。

## 运行测试

```powershell
py -m pytest -q
```

测试会使用临时 SQLite 文件，不会修改正式的 `data/cycling.sqlite3`。

## 训练计划怎么生成

在“训练计划”页面选择训练目标、计划周期、每周骑行次数和开始日期。程序会读取开始日期之前最近 6 周的骑行记录：

- 计算平均每周公里数、最长单次距离、记录次数和平均疲劳程度。
- 有历史数据时，起始周大约使用近期平均周里程的 90%；疲劳程度较高时会继续降低。
- 普通周在上一普通周基础上增加 8%。第 4 周和第 8 周是恢复周，训练量约为上一普通周的 70%。
- 没有历史记录时使用 20 km 的保守起点，并在页面明确提示。

这是一套容易理解和修改的通用耐力规则，不接入外部 API，也不替代医生或专业教练的个性化建议。

## 训练计划相关路由

- `/plans`：查看已生成的计划。
- `/plans/new`：填写设置并生成新计划。
- `/plans/<计划编号>`：查看每周训练安排、调整距离和标记完成。

## 代码学习路线

1. 先读 `app.py` 的路由：它展示了 Flask 如何接收请求、渲染模板和跳转页面。
2. 再读 `db.py`：重点看 `?` 占位符，它能避免把用户输入直接拼进 SQL。
3. 然后读 `training.py`：重点看 `analyze_history()` 如何把多条记录变成摘要，以及 `build_training_plan()` 如何把周总量分配到训练日。
4. 最后读 `templates/plan_form.html` 和 `templates/plan_detail.html`，理解表单字段和训练计划页面如何对应。

可以尝试把列表里的“记录次数”改成“本月记录次数”，或给详情页增加天气字段；练习时先修改模板，再修改校验、数据库表和测试。
也可以尝试把普通周的 `8%` 改成 `5%`，观察生成的训练计划如何变化，然后运行测试确认恢复周仍然存在。

