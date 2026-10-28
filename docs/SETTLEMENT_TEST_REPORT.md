# 角色丙结算后端测试记录

- 验证日期：2026 年 10 月 28 日。
- 分支：feat/settlement，已合并乙的 feat/backend-foundation（至 5799e02）。
- 验证提交：421d8b5。业务代码最后变更于 c3e58a4，此后只有测试夹具整理、文档和冒烟脚本。
- 本地环境：WSL2 Linux 6.6，Python 3.12.15，FastAPI 0.162.0，SQLAlchemy 2.0.55，Pydantic 2.14.1；依赖固定在 backend/uv.lock。
- 范围：丙的分摊、余额、结算建议、付款、生命周期、统计与导出。乙的接口见[乙的测试记录](BACKEND_TEST_REPORT.md)。未包含前端。

## 本地结果

| 检查 | 结果 |
| --- | --- |
| pytest 全部后端测试 | 325 项通过，0 项失败（丙 226 项，乙 99 项） |
| app 语句覆盖率 | 1329 / 1344，约 99% |
| 丙模块覆盖率 | 领域层、服务层与路由除 2 行外全部覆盖，见下文 |
| 并发测试重复执行 | tests/test_settlement_concurrency.py 连续 10 次，10 次全部通过 |
| Ruff 检查与格式检查 | 通过 |
| Alembic 升级与模型差异检查 | 通过，head 为 0003，无待生成迁移 |
| 0003 回退至 0002 再升级 | 通过（空临时库） |
| 真实服务冒烟流程 | 18 项检查全部通过 |
| 重启服务后核对 | 3 项检查全部通过 |

在 backend 目录执行：

~~~text
uv run --locked ruff check app tests migrations
uv run --locked ruff format --check app tests migrations
uv run --locked alembic upgrade head
uv run --locked alembic check
uv run --locked pytest -q --cov=app --cov-report=term-missing
~~~

自动化测试使用 pytest 临时目录中的独立数据库，不使用开发库或演示库。

## 丙的测试分布

| 测试文件 | 层次 | 数量 |
| --- | --- | ---: |
| [domain/test_split.py](../backend/tests/domain/test_split.py) | 单元 | 41 |
| [domain/test_balance.py](../backend/tests/domain/test_balance.py) | 单元 | 10 |
| [domain/test_settlement.py](../backend/tests/domain/test_settlement.py) | 单元，含 200 组随机账本 | 6 |
| [domain/test_payment.py](../backend/tests/domain/test_payment.py) | 单元 | 34 |
| [domain/test_activity.py](../backend/tests/domain/test_activity.py) | 单元 | 17 |
| [domain/test_statistics.py](../backend/tests/domain/test_statistics.py) | 单元 | 6 |
| [domain/test_export.py](../backend/tests/domain/test_export.py) | 单元 | 13 |
| [test_split_preview.py](../backend/tests/test_split_preview.py) | 接口 | 10 |
| [test_balance_api.py](../backend/tests/test_balance_api.py) | 接口 | 9 |
| [test_lifecycle_api.py](../backend/tests/test_lifecycle_api.py) | 接口 | 11 |
| [test_payments_api.py](../backend/tests/test_payments_api.py) | 接口 | 22 |
| [test_payment_actions_api.py](../backend/tests/test_payment_actions_api.py) | 接口 | 16 |
| [test_payment_rollback.py](../backend/tests/test_payment_rollback.py) | 接口，故障注入 | 2 |
| [test_settlement_concurrency.py](../backend/tests/test_settlement_concurrency.py) | 接口，并发 | 6 |
| [test_reports_api.py](../backend/tests/test_reports_api.py) | 接口 | 11 |
| [test_settlement_error_codes.py](../backend/tests/test_settlement_error_codes.py) | 接口，错误码契约 | 12 |
| 合计 | | 226 |

未覆盖的 2 行均为防御分支：split.py 中不支持的分摊方式（输入已由枚举限定），payment.py 中当前用户不是成员（调用前 require_activity 已拦截）。

## 开发计划用例结果

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| T01 100 元三人均摊 | 通过：3334、3333、3333 | 单元 test_t01；接口 test_t01_preview；真实服务分摊预览 |
| T02 0.01 元任意排列 | 通过：始终由 ID 最小的成员获得 1 分 | 单元 test_t02（均摊）、余数相同时按 ID 排序（按份数），覆盖全部 6 种排列 |
| T03 600 元按 2∶2∶1∶1 | 通过：200、200、100、100 | 单元 test_t03；接口 test_t03_preview |
| T04 非法分摊 | 通过：合计不符、负份额、零份数、重复成员均被拒绝 | 单元 test_t04 系列；接口预览返回 422；乙的费用保存测试验证不留残片 |
| T05 未参与成员承担零 | 通过 | 单元与接口 test_t05 |
| T06 三人出游示例 | 通过：50、-10、-40 元 | 单元、接口 test_t06；真实服务 |
| T07 登记 20 元待确认 | 通过：余额不变，C 可登记付出 20 元，A 可登记收到 30 元 | 接口 test_t07；真实服务 |
| T08 A 确认 20 元 | 通过：30、-10、-20 元 | 接口 test_t08；真实服务 |
| T09 重试与重复确认 | 通过：同编号顺序与并发重试只登记一笔；重复或并发确认只入账一次、只写一条历史 | 接口 test_t09 系列；并发测试；真实服务 |
| T10 40 元债务并发登记两笔 30 元 | 通过：恰好一笔 201、一笔 409 | 并发测试；持有写锁时插入待确认付款，验证后到请求等待写锁并基于最新占用拒绝 |
| T11 确认与撤销并发 | 通过：恰好一个终态成功，余额与历史一致 | 并发测试；终态不可再变更的接口测试 |
| T12 越权与跨活动 | 通过：非收款人确认、非付款人撤销、创建者代确认返回 403；非成员访问丙的全部接口返回 404 | 接口 test_t12 系列；错误码测试；真实服务 |
| T13 封账与改账 | 通过：封账后增删改费用、加入成员返回 409；并发时封账之后不出现费用修改 | 接口 test_t13；并发测试；乙的持锁测试；真实服务 |
| T14 旧 version 修改费用 | 乙负责 | 见乙的测试记录 |
| T15 事务中途失败 | 付款部分通过：登记失败不留记录且编号可复用；最后一笔确认失败时付款、活动状态与历史全部回滚 | test_payment_rollback.py；费用部分见乙的测试记录 |
| T16 归档条件 | 通过：已结清可归档，未结清返回 409 | 单元、接口 test_t16；真实服务 |
| T17 无费用或净额为零 | 通过：发起结算直接进入 SETTLED | 单元、接口 test_t17 |
| T18 预算、统计、CSV 与付款并存 | 通过：确认付款后消费仍为 180 元；CSV 带 BOM、金额与页面一致、归档后可导出、公式字符被转义 | 接口 test_t18 系列；单元 test_export；真实服务 |
| T19 重启、刷新、重新登录 | 部分通过：后端重启后活动、统计与付款数据仍在；页面刷新与重新登录待前端 | 真实服务重启核对 |
| T20 完整流程与第二台电脑 | 未执行：需要前端和第二台电脑 | 后端主流程已由真实服务冒烟脚本跑通 |

## 真实服务冒烟流程

使用 [settlement_smoke.py](../scripts/settlement_smoke.py)。服务以临时 SQLite 文件和随机 JWT 密钥启动，执行 `alembic upgrade head` 后用 uvicorn 监听 127.0.0.1:8765，脚本通过 HTTP 调用接口。

| 步骤 | 实际结果 |
| --- | --- |
| GET /health | 200，schema_revision 为 0003；OpenAPI 共 27 个业务操作 |
| 分摊预览 120 元三人均摊 | 4000、4000、4000 分 |
| 录入两笔费用 | 201、201 |
| 余额 alice、bob、charlie | 5000、-1000、-4000 分 |
| 转账建议 | charlie→alice 4000 分，bob→alice 1000 分 |
| 封账前登记付款 | 409 PAYMENTS_CLOSED |
| 发起结算 | SETTLING；随后修改费用返回 409 ACTIVITY_LOCKED |
| charlie 登记 20 元并以同编号重试 | 201、200，返回同一记录 |
| 待确认时 | charlie 余额 -4000、可登记付出 2000；alice 可登记收到 3000 |
| 再登记 30 元 | 409 PAYMENT_QUOTA_EXCEEDED |
| bob 代替 alice 确认 | 403 PAYMENT_ACTION_FORBIDDEN |
| alice 确认两次 | 余额 3000、-1000、-2000 分，只入账一次 |
| 其余付款确认后 | 活动自动变为 SETTLED，余额全为 0 |
| 归档 | ARCHIVED |
| 统计 | 消费 18000 分，剩余预算 32000 分 |
| 归档后导出 CSV | 200，带 BOM，表头加两行费用 |
| 重启服务后 | 活动仍为 ARCHIVED，消费 18000 分，三笔付款均为 CONFIRMED |

操作历史按时间顺序为 ACTIVITY_CREATED、MEMBER_JOINED ×2、EXPENSE_CREATED ×2、SETTLEMENT_STARTED、三组 PAYMENT_CREATED 与 PAYMENT_CONFIRMED、ACTIVITY_SETTLED、ACTIVITY_ARCHIVED。重复确认没有产生额外历史。服务日志中没有错误。

## 说明与尚待完成的内容

并发测试通过 TestClient 在多个线程中发起请求，引擎使用 NullPool，每个请求是独立的 SQLite 连接。除依赖时序的并发断言外，另用“测试持有写锁、观察请求是否发出 BEGIN IMMEDIATE 并等待”的方式验证额度检查确实发生在写锁之内，这一项结果不依赖线程调度。

当前锁定的 Starlette 在使用 HTTPX 测试兼容层时产生 1 项弃用提示，未导致测试失败。

GitHub Actions 的 backend 工作流在 [PR #2](https://github.com/Delovue/hezhang/pull/2) 上对提交 05f1d37 运行通过（[运行记录](https://github.com/Delovue/hezhang/actions/runs/40687998195)，用时 2 分 41 秒）：Ruff 检查与格式检查通过，迁移升级后无待生成迁移，325 项测试全部通过，app 语句覆盖率 99%，与本地结果一致。后续提交以其各自的运行记录为准。

尚未验收：甲的界面、浏览器完整流程（T19 的页面部分、T20）、第二台电脑复现。上述后端测试与冒烟流程不能替代这些验收。
