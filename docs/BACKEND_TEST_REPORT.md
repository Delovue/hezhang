# 角色乙后端测试记录

- 验证日期：2026 年 10 月 28 日。
- 分支：feat/backend-foundation。
- 业务实现提交：ccac6aa。
- 本地环境：Windows，Python 3.12.16；依赖版本固定在 backend/uv.lock。
- 范围：乙的后端接口及共享分摊函数，未包含前端或付款结算功能。

## 本地结果

| 检查 | 结果 |
| --- | --- |
| pytest | 46 项通过，0 项失败 |
| app 语句覆盖率 | 605 / 629，约 96% |
| Ruff 检查与格式检查 | 通过 |
| Alembic 升级与模型差异检查 | 通过，无待生成迁移 |
| 临时数据库回退再升级 | 通过 |
| 实际服务 GET /health | 200，schema_revision 为 0001 |
| 实际服务 GET /openapi.json | 200，包含 15 个业务操作及 1 个健康检查 |
| 实际服务 GET /docs | 200 |

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

并发测试使用同一个临时数据库文件的独立连接，使用同步事件协调执行顺序。封账状态由测试代码写入；这些结果验证乙侧的事务与写入保护，不代表封账业务端点或付款结算已经完成。

## 证据与尚待集成的内容

[认证与活动测试](../backend/tests/test_auth_activity.py)、[分摊测试](../backend/tests/test_split.py)、[费用测试](../backend/tests/test_expenses.py)随代码维护。

当前锁定的 Starlette 在使用 HTTPX 测试兼容层时产生 1 项弃用提示，未导致测试失败。后续依赖调整应重新运行完整测试。

GitHub Actions 的 [backend 工作流](../.github/workflows/backend.yml)会在 PR 和 main 更新时执行后端检查，其远端结果以对应提交的运行记录为准。

尚未验收：甲的界面、丙的余额与付款结算和状态转换端点、统计导出、浏览器完整业务流程、第二台电脑现场演示，以及开发计划 T01–T20 的整系统验收。上述 46 项后端测试不能替代这些验收。
