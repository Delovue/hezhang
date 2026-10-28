# 角色乙后端测试记录

- 验证日期：2026 年 10 月 28 日。
- 分支：feat/backend-foundation。
- 业务实现提交：ab378b8。
- 本地环境：Windows，Python 3.12.16；依赖版本固定在 backend/uv.lock。
- 范围：乙的后端接口及共享分摊函数，未包含前端或付款结算功能。

## 本地结果

| 检查 | 结果 |
| --- | --- |
| pytest | 64 项通过，0 项失败 |
| app 语句覆盖率 | 645 / 668，约 97% |
| Ruff 检查与格式检查 | 通过 |
| Alembic 升级与模型差异检查 | 通过，无待生成迁移 |
| 临时数据库回退再升级 | 通过 |
| 首轮实际服务 GET /health | 200，schema_revision 为 0001；记录来自首轮代码 |
| 首轮实际服务 GET /openapi.json | 200，包含 15 个业务操作及 1 个健康检查；记录来自首轮代码 |
| 首轮实际服务 GET /docs | 200；记录来自首轮代码 |
| 第二轮实际服务预览 | 未完成：重启旧进程和启动隔离预览的命令均被自动审批策略拦截 |

运行命令在 backend 目录执行：

~~~text
uv run --locked ruff check app tests migrations
uv run --locked ruff format --check app tests migrations
uv run --locked alembic upgrade head
uv run --locked alembic check
uv run --locked pytest -q --cov=app --cov-report=term-missing
~~~

测试运行使用独立临时数据库。迁移回退测试只针对空的临时数据库，不针对开发数据库。

## 已验证场景

- 注册、登录、密码哈希、重复用户名；缺失、错误和过期令牌。
- 用户只可访问自己的活动；邀请码仅创建者可见；重复加入不重复保存。
- 活动只有创建者能改；非 ACTIVE 状态不能加入或修改。
- 整数分校验；均摊、指定金额、按份数、余数确定性和大整数守恒。
- 费用的创建、筛选、分页、详情、修改和软删除。
- 不同活动的付款人或分摊成员不能混入同一费用。
- 付款人身份不自动获得编辑权；费用记录者和活动创建者可编辑。
- 版本过期返回冲突；两次同时修改同一版本只有一次成功。
- 封账持有写锁期间到达的费用修改，在拿到写锁后重新读状态并被拒绝。
- 保存历史时注入异常，费用创建、分摊替换、版本变化和软删除均能回滚。
- ID、版本和分页数值超过安全整数范围时返回 422，不再触发 SQLite 整数溢出。
- 费用关键词同时检索标题和备注；空白关键词被拒绝，百分号、下划线和斜线按字面匹配。
- 按参与人查询可与付款人、分类、日期和关键词叠加；零分份额也算参与，结果不重复且排除软删除费用。
- 活动按状态和名称查询仅显示本人参加的活动；普通成员和已封账活动的响应不包含邀请码。
- 历史可按对象、操作者和动作组合筛选；费用删除、活动归档后仍能查修改前后快照。
- 活动与历史游标分页期间新增记录，不会使已存在记录重复出现；旧 offset 分页仍可使用。

并发测试使用同一个临时数据库文件的独立连接，使用同步事件协调执行顺序。封账状态由测试代码写入；这些结果验证乙侧的事务与写入保护，不代表封账业务端点或付款结算已经完成。

## 证据与尚待集成的内容

[认证与活动测试](../backend/tests/test_auth_activity.py)、[分摊测试](../backend/tests/test_split.py)、[费用测试](../backend/tests/test_expenses.py)随代码维护。

第二轮在原 46 项基础上新增 18 项自动化测试：

| 内容 | 测试文件 | 数量 |
| --- | --- | ---: |
| 异常 ID 与分页参数回归 | [test_parameter_validation.py](../backend/tests/test_parameter_validation.py) | 4 |
| 历史筛选、删除追溯、权限和游标 | [test_audit_queries.py](../backend/tests/test_audit_queries.py) | 5 |
| 费用关键词、参与人、组合筛选与隔离 | [test_expense_queries.py](../backend/tests/test_expense_queries.py) | 5 |
| 活动状态、名称、邀请码隔离与游标 | [test_activity_queries.py](../backend/tests/test_activity_queries.py) | 4 |

边界回归先复现了超大路径 ID 引发 `OverflowError: Python int too large to convert to SQLite INTEGER`，随后增加参数上限并验证返回 422。本轮未改变数据表结构；状态查询测试直接设置测试数据库中的活动状态，不代表已经实现生命周期端点。

第二轮的 64 项自动化测试通过 FastAPI TestClient 调用当前代码。旧的本地 8000 端口服务未刷新，不能用其文档页证明新查询参数已上线；需要按 README 从当前分支重新启动服务后再开展真实前端联调。命令拒绝信息只有“blocked by policy”，没有进一步说明原因。

当前锁定的 Starlette 在使用 HTTPX 测试兼容层时产生 1 项弃用提示，未导致测试失败。后续依赖调整应重新运行完整测试。

GitHub Actions 的 [backend 工作流](../.github/workflows/backend.yml)会在 PR 和 main 更新时执行后端检查。[业务提交 ab378b8 的远端检查](https://github.com/Delovue/hezhang/actions/runs/40634815201)已通过，包括依赖安装、格式检查、迁移与后端测试；后续提交以其各自运行记录为准。

尚未验收：甲的界面、丙的余额与付款结算和状态转换端点、统计导出、浏览器完整业务流程、第二台电脑现场演示，以及开发计划 T01–T20 的整系统验收。上述 64 项后端测试不能替代这些验收。
