# 合账

面向小组活动的协作记账与费用结算系统，用于软件工程课程大作业。

项目以朋友旅行为主要场景，完成“创建活动 → 邀请成员 → 共同记账 → 费用分摊 → 付款确认 → 结清归档”的流程，并通过业务规则、测试和真实 Git 提交记录展示开发过程。

**当前阶段：首版 FR01–FR12 已实现，包含完整前后端、演示工具和课程材料。2026-11-01 角色丁复核：后端 345 项、前端单元 59 项、浏览器 17 项及重启验证通过；新增统一验收工具与 Windows／Ubuntu CI。实际课堂电脑和四名成员的现场验收仍待完成，当前作为课程候选版交付。版本与验证边界见系统验收报告。**

页面已接入注册登录、活动与成员、费用增删改查、三种分摊预览、余额与建议、部分付款及收款确认、封账归档、预算统计、操作历史与 CSV 导出。费用和付款重试保留请求编号；版本冲突保留输入并要求核对；同名成员显示编号。

后端使用整数分和事务内权限／状态校验，重复登记、确认与撤销受请求编号和写锁保护。app 语句覆盖率为 98.90%，完整证据与验收边界见系统报告。

- [课程实验报告](docs/COURSE_REPORT.md)
- [运行、演示讲稿与课堂验收](docs/DEMO_GUIDE.md)
- [系统验收与测试记录](docs/ACCEPTANCE_REPORT.md)
- [角色丁集成交接与未完成工作](docs/ROLE_D_HANDOFF.md)

- [后端交接说明](docs/BACKEND_HANDOFF.md)
- [后端测试记录](docs/BACKEND_TEST_REPORT.md)
- [结算后端交接说明](docs/SETTLEMENT_HANDOFF.md)
- [结算后端测试记录](docs/SETTLEMENT_TEST_REPORT.md)
- [结算模块设计与算法说明](docs/SETTLEMENT_DESIGN.md)
- [前端交接与推进计划](docs/FRONTEND_HANDOFF.md)
- [前端测试记录](docs/FRONTEND_TEST_REPORT.md)

## 开发计划

[阅读完整开发计划](docs/DEVELOPMENT_PLAN.md)

- 团队规模：4 人。
- 开发周期：7 天，按 D1 至 D7 排期。
- 技术路线：Vue 3、TypeScript、FastAPI、SQLAlchemy、SQLite。
- 交付形式：可本地运行的 Web 应用、源代码、实验报告、测试记录和 3–5 分钟现场演示。

## 后端运行

需要 Git、Python 和 uv。若未安装 uv，可执行 `python -m pip install uv==0.13.6`。进入仓库目录，在 PowerShell 或其他终端执行：

~~~text
cd backend
uv python install 3.12
uv sync --locked --managed-python
uv run --locked python -c "from pathlib import Path; import secrets; p=Path('.env'); p.exists() or p.write_text('HEZHANG_JWT_SECRET='+secrets.token_urlsafe(48)+'\n', encoding='utf-8')"
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
~~~

初始化命令只在 .env 不存在时生成密钥。已有 .env 会保留；若从示例复制了空密钥，需要为 HEZHANG_JWT_SECRET 填入至少 32 字符的随机值。

已有项目更新后，重新启动后端之前也要执行 `uv run --locked alembic upgrade head`。当前迁移 head 为 0003：0002 新增费用请求登记表，0003 新增付款表；迁移已验证保留原账单、分摊和历史。健康检查 `/health` 在数据库版本不匹配时返回 503，升级完成后返回 `schema_revision: "0003"`。

打开 [接口文档](http://127.0.0.1:8000/docs)，先注册并登录，再把返回的 access_token 填入 Authorize。默认没有预置账号。接口金额单位为分，数据库保存在 backend/data/hezhang.db。

验证代码：

~~~text
uv run --locked pytest -q --cov=app --cov-report=term-missing
uv run --locked ruff check app tests migrations
uv run --locked ruff format --check app tests migrations
uv run --locked alembic check
~~~

## 前端运行

先按上文启动后端，再新开一个终端，在仓库根目录执行：

~~~text
cd frontend
npm ci
npm run dev
~~~

浏览器打开 http://127.0.0.1:5173。Node.js 支持 22.12 以上的 22.x 或 24 以上版本；本次系统验收使用 24.18.0。依赖由 `frontend/package-lock.json` 锁定。

开发服务器将 `/api` 请求转发到 http://127.0.0.1:8000。需要其他地址时，将 `frontend/.env.example` 复制为 `frontend/.env.local`，修改 `HEZHANG_API_TARGET` 后重启前端。使用同一仓库版本的 `backend/` 和 `frontend/`，避免旧工作目录的服务与当前页面契约不一致。

没有预置账号；在页面注册自己的账号。令牌仅保存在内存中，刷新后需要重新登录，已保存的活动不受影响。登录过期时可用原账号重新登录，继续填写当前表单。

前端验证：

~~~text
cd frontend
npm run build
npm test
npm run test:install-browser
npm run test:e2e
~~~

浏览器测试需要先在 `backend/` 执行 `uv sync --locked`，建立 Python 虚拟环境。测试自动在 18000、15173 端口启动隔离的后端和前端，不要提前在这些端口启动服务。测试数据库位于忽略的 `.e2e/` 目录，不使用或清空开发数据库。构建目录 `frontend/dist/` 可生成静态资源；本轮不包含生产托管配置。

## 统一自动化验收

安装上述锁定依赖及 Chromium 后，在仓库根目录执行（目录必须尚不存在）：

```powershell
backend/.venv/Scripts/python.exe scripts/acceptance.py --directory .e2e/acceptance-01
```

Linux/macOS 使用 `backend/.venv/bin/python`。命令依次执行代码检查、隔离库迁移、后端测试与覆盖率、前端构建与单元测试、真实浏览器流程、HTTP 与服务重启验证。任何步骤失败立即返回非零退出码，后续步骤记为未运行；逐步日志、JSON／JUnit 报告及提交哈希保存在指定目录的 `summary.json` 及相邻文件中。已有结果不会被覆盖，开发数据库不会被用于迁移验证。

自动化通过不代表课堂电脑及四名成员人工验收通过；结果中的人工验收始终为待完成。完整输出目录包含虚构测试数据与随机测试密钥，不要整目录发布；只提交核对后的报告，CI 也仅归档指定的测试证据文件。

## 独立演示环境

安装上述后端和前端依赖后，在仓库根目录执行：

```powershell
backend/.venv/Scripts/python.exe scripts/course.py prepare --directory .demo/lesson-01
backend/.venv/Scripts/python.exe scripts/course.py serve --directory .demo/lesson-01
```

打开 http://127.0.0.1:15174，使用演示账号 `demo_a`、`demo_b`、`demo_c`，密码均为 `Demo-pass-2026`。这是脚本生成的虚构数据。三个页面可分别登录；主活动已有成员但没有费用，便于现场录入 120 元餐费和 60 元车费。

Linux/macOS 将解释器改为 `backend/.venv/bin/python`。脚本拒绝覆盖已有目录；重练时使用新目录。Ctrl+C 停止本次启动的服务。详细流程见[演示指南](docs/DEMO_GUIDE.md)。

## 首版功能

| 模块 | 主要功能 |
| --- | --- |
| 账号与活动 | 注册登录、创建活动、邀请码加入、成员权限 |
| 协作记账 | 费用录入、分类、付款人、分摊成员、编辑与删除 |
| 灵活分摊 | 均摊、指定金额、按份数分摊 |
| 余额与建议 | 垫付与承担汇总、应收应付、转账建议 |
| 付款确认 | 部分付款、收款确认、拒绝、撤销待确认记录 |
| 封账与追溯 | 活动状态流转、费用冻结、操作历史、归档 |
| 预算与统计 | 总预算、超预算提示、分类汇总、个人承担、CSV 导出 |

系统只登记成员在外部完成的付款，不接入支付渠道。任务协作、票据上传、多币种和全局最少转账次数优化留作后续版本。

## 计算示例

A 垫付餐费 120 元，由 A、B、C 均摊；B 垫付车费 60 元，仅 A、B 分摊。

| 成员 | 垫付 | 承担 | 余额 |
| --- | ---: | ---: | --- |
| A | 120 元 | 70 元 | 应收 50 元 |
| B | 60 元 | 70 元 | 应付 10 元 |
| C | 0 元 | 40 元 | 应付 40 元 |

C 登记支付 20 元时，余额保持不变；A 确认收到后，A 应收 30 元、B 应付 10 元、C 应付 20 元。成员间的结算付款不增加活动消费总额。

## 仓库内容

- [开发计划](docs/DEVELOPMENT_PLAN.md)：需求、架构、接口、分工、排期、测试和答辩安排。
- [基础后端](backend/)：FastAPI 路由、业务服务、共享分摊、模型、迁移和测试。
- [前端](frontend/)：Vue 页面、路由、内存会话、API 调用、金额工具和自动化测试。
- [前端交接](docs/FRONTEND_HANDOFF.md)：当前完整页面范围、接口和实现入口。
- [后端交接说明](docs/BACKEND_HANDOFF.md)：字段、权限、版本、事务约定及与甲、丙的接口。
- [后端测试记录](docs/BACKEND_TEST_REPORT.md)：实际验证结果及尚待集成的范围。
- `.gitignore`：忽略环境变量、依赖、数据库和构建产物。

每完成一项新增功能逻辑并验证通过，立即 commit 并推送功能分支。项目进展通过实际代码、测试结果及 GitHub 提交记录更新。
