# 合账

面向小组活动的协作记账与费用结算系统，用于软件工程课程大作业。

项目以朋友旅行为主要场景，完成“创建活动 → 邀请成员 → 共同记账 → 费用分摊 → 付款确认 → 结清归档”的流程，并通过业务规则、测试和真实 Git 提交记录展示开发过程。

**当前阶段：后端已实现。角色乙的基础后端位于 feat/backend-foundation，角色丙的结算后端位于 feat/settlement（已合并乙的分支）。前端待继续开发。**

已实现注册登录、活动与成员、费用增删改查、三种分摊计算、权限和操作历史，并提供数据库迁移。活动可按状态和名称筛选，费用可按关键词与分摊参与人组合查询，历史支持按对象、操作者和动作追溯及游标翻页。费用创建可携带 request_id，重复或并发重试只记一笔。85 项后端测试通过，app 语句覆盖率约 97%。

结算部分已实现分摊预览、余额与转账建议、付款登记与确认、封账归档、预算统计和 CSV 导出，付款登记同样支持 request_id 重试保护，并发登记、确认与撤销由写锁保证只生效一次。结算接口的错误同样返回稳定错误码。合并后共 325 项后端测试通过，app 语句覆盖率约 99%。

- [后端交接说明](docs/BACKEND_HANDOFF.md)
- [后端测试记录](docs/BACKEND_TEST_REPORT.md)
- [结算后端交接说明](docs/SETTLEMENT_HANDOFF.md)
- [结算后端测试记录](docs/SETTLEMENT_TEST_REPORT.md)
- [结算模块设计与算法说明](docs/SETTLEMENT_DESIGN.md)

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

## 完整首版规划

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
- [后端交接说明](docs/BACKEND_HANDOFF.md)：字段、权限、版本、事务约定及与甲、丙的接口。
- [后端测试记录](docs/BACKEND_TEST_REPORT.md)：实际验证结果及尚待集成的范围。
- `.gitignore`：忽略环境变量、依赖、数据库和构建产物。

每完成一项新增功能逻辑并验证通过，立即 commit 并推送功能分支。项目进展通过实际代码、测试结果及 GitHub 提交记录更新。
