# 角色乙后端交接说明

本轮交付认证、活动与成员、费用管理、操作历史和数据库迁移，可供甲对接页面、供丙继续实现余额与结算。开发分支为 feat/backend-foundation。

## 当前实现与分工边界

| 范围 | 当前结果 |
| --- | --- |
| FR01 | 注册、登录、当前用户；密码使用 Argon2 哈希，JWT Bearer 验证 |
| FR02 与 FR03 | 创建活动、按状态和名称查询、修改预算、邀请码加入、成员列表、重复加入保护 |
| FR04 | 费用创建及重复提交保护、关键词与参与人组合筛选、详情、部分修改、版本冲突与软删除 |
| FR05 的共享依赖 | 三种分摊纯函数已用于费用保存，供丙复用到预览接口 |
| FR10 | 活动、成员、费用变更历史；记录修改前后数据；按对象、操作者、动作筛选与游标分页 |
| FR09 的乙侧约束 | 所有非 ACTIVE 状态拒绝费用、成员和活动写入；并发时在写锁内重新检查 |
| 后续由丙实现 | 分摊预览端点、余额、结算建议、付款确认、状态转换端点、统计和导出 |
| 后续由甲与丁完成 | 前端页面、完整端到端流程、报告整合与现场演示 |

当前没有创建付款表或提供封账端点。测试中的状态变更由测试代码模拟，不能视为结算功能已经实现。

## 运行与联调入口

按 [README](../README.md) 初始化环境、执行迁移并启动后端。

- 健康检查：GET /health。
- 接口文档：/docs；机器可读契约：/openapi.json。
- API 前缀：/api/v1。
- 默认允许的前端来源：http://localhost:5173 和 http://127.0.0.1:5173。
- 开发数据库：backend/data/hezhang.db；数据库和 .env 均不提交 Git。
- 列表默认每页 50 条，通过 limit 和 offset 分页，limit 最大 100。
- ID 和 version 为 1–9007199254740991 的整数；offset 为 0–9007199254740991。超出范围返回 422，避免浏览器精度丢失或数据库整数溢出。

## 甲的接入顺序

### 账号与登录状态

POST /api/v1/auth/register 接收 JSON：

~~~json
{"username":"alice","display_name":"小王","password":"your-password-at-least-8-chars"}
~~~

用户名使用 3–32 位英文字母、数字或下划线，统一转为小写；显示名支持中文。密码为 8–128 个字符，保留原始空格，不按显示名规则裁剪。

POST /api/v1/auth/login 接收 username 和 password，返回 access_token、token_type 和 expires_in。后续请求发送 Authorization: Bearer 加该令牌。GET /api/v1/auth/me 返回当前用户。

前端只在内存中保存令牌，退出时清空；当前没有服务端注销或令牌撤销端点。刷新后重新登录，过期响应 401 后也回到登录页。Swagger 的 Authorize 输入框填写登录返回的令牌本体即可。

### 活动与成员

| 方法与路径 | 行为 |
| --- | --- |
| POST /api/v1/activities | 创建活动，请求 name 和可选 budget_cents |
| GET /api/v1/activities | 仅列出本人参加的活动；可用 status、q 组合筛选 |
| GET /api/v1/activities/{id} | 查询详情 |
| PATCH /api/v1/activities/{id} | 创建者在 ACTIVE 状态修改名称或预算 |
| POST /api/v1/activities/join | 用 invite_code 加入 |
| GET /api/v1/activities/{id}/members | 查询成员 id、user_id、display_name、role |

预算为 null 表示未设置，0 是有效预算。仅活动创建者在 ACTIVE 状态能看到邀请码，其他成员收到 null。不可从操作历史获取邀请码。

活动列表的 status 可选 ACTIVE、SETTLING、SETTLED、ARCHIVED；省略时返回全部状态。q 在活动名称中做字面子串匹配，裁剪首尾空格后为 1–120 字符，忽略 ASCII 字母大小写。结果按活动 id 倒序排列，可使用 limit、offset，或将上一页最后一个活动 id 作为 before_id 加载更早创建的活动；before_id 不能与非零 offset 同用。新建活动不会使游标分页重复返回旧活动，但切换筛选条件或有新加入、状态变化时，应从第一页刷新列表。

**成员 id 与用户 user_id 是不同标识。** 付款人和分摊参与人使用成员 id，不能直接拿登录返回的用户 id 充当成员 id。

### 费用录入

先调用成员列表，使用真实成员 id 组装以下请求；示例中的 1、2、3 仅为占位。

POST /api/v1/activities/{id}/expenses：

~~~json
{
  "title": "晚餐",
  "category": "餐饮",
  "amount_cents": 10000,
  "expense_date": "2026-10-27",
  "notes": "三人均摊",
  "payer_member_id": 1,
  "split_method": "EQUAL",
  "participants": [{"member_id":1},{"member_id":2},{"member_id":3}]
}
~~~

EXACT 的参与人填写 member_id、amount_cents；SHARES 填写 member_id、shares。不要在 EQUAL 中提交金额或份数，也不要同时混用 amount_cents 与 shares。一次最多选择 100 个分摊成员，份数是 1–1000000 的整数。

金额必须以 JSON 整数分传输，不能传浮点数、字符串或布尔值；费用总额必须大于零。金额上限为 JavaScript 安全整数 9007199254740991 分。后端计算并返回 shares，其中包含每位成员实际承担的整数分。

### 费用创建的重复提交保护

创建费用的 JSON 可额外携带 request_id，格式为 UUID v4。甲在一次新保存开始时调用 `crypto.randomUUID()` 生成编号，并保留这次提交的完整 JSON；双击保护和网络超时重试必须复用原编号及原内容。

| 请求情况 | 后端结果 |
| --- | --- |
| 新编号、合法费用、活动 ACTIVE | 201，创建费用、分摊、请求登记和一条历史 |
| 同一活动、同一记录者、同编号、相同业务内容 | 200，返回已创建费用的当前版本；不新增费用、分摊或历史 |
| 复用已登记编号但修改业务内容 | 409，不修改原费用 |
| 原费用已软删除后再重试 | 409，不恢复、不另建费用；请求登记继续保留 |
| 已保存成功，随后活动封账，再重试原请求 | 200，只查询已存在费用；新编号仍被拒绝创建 |
| 请求验证失败或事务回滚后再次重试 | 失败不占用编号，修正错误后仍可提交 |
| 省略 request_id 或传 null | 保持原接口行为，每次合法请求都创建一笔；不提供重复提交保护 |

请求编号按“活动 + 记录者用户”隔离，与付款人无关。编号和请求摘要不进入公共费用响应或操作历史。分摊成员的输入顺序、JSON 字段顺序、默认空备注和已被输入模型裁剪的首尾空格不影响同一请求的判断；金额、付款人、说明、日期和分摊规则变化都视为内容不同。

修改已保存费用使用 PATCH 和 version。重试创建只返回当前费用，不撤销后来的编辑；即使当前费用已被改成另一内容，原 request_id 仍绑定最初创建内容。遇到超时应先重试原请求，不能为了绕过 409 自动更换编号重复记账；确认要记另一笔新费用时才生成新编号。

### 查询与修改

| 方法与路径 | 行为 |
| --- | --- |
| GET /activities/{id}/expenses | 按 category、payer_member_id、participant_member_id、q、start_date、end_date 组合筛选；日期区间包含端点 |
| GET /activities/{id}/expenses/{expense_id} | 查询单笔有效费用 |
| PATCH /activities/{id}/expenses/{expense_id} | 携带当前 version 和需要变更的字段 |
| DELETE /activities/{id}/expenses/{expense_id}?version=2 | 软删除；成功返回 204 |
| GET /activities/{id}/audit-logs | 按操作 id 倒序查询历史 |

上表路径均需加 /api/v1 前缀。

费用查询的 q 搜索标题和备注中的字面子串，忽略 ASCII 字母大小写，裁剪首尾空格后长度为 1–120；不搜索时省略 q。百分号、下划线和斜线按普通字符匹配。participant_member_id 用成员 ID 筛选参与分摊的费用，与付款人不同；指定承担零分的参与人也算参与。筛选可叠加，按费用日期倒序、同日按费用 id 倒序分页，始终排除软删除记录。

PATCH 示例：

~~~json
{"version":1,"amount_cents":12000}
~~~

均摊和按份数分摊会依据原参与人重新计算；指定金额方式改变总额时，需要同时给出与新总额一致的 participants。修改 split_method 时必须同时提交 participants。notes 可用 null 清空，其他费用字段不能设为 null。

保存成功后使用响应中的新 version。过期 version 返回 409，界面应提示刷新并保留尚未提交的输入，不能自动覆盖新版本。付款人并不自动拥有修改权；修改和删除只允许费用记录者或活动创建者执行。

### 操作历史筛选与追溯

GET /api/v1/activities/{id}/audit-logs 支持以下可组合的参数，仍返回按历史 id 倒序排列的数组：

| 参数 | 含义 |
| --- | --- |
| action | 精确匹配动作，如 EXPENSE_UPDATED；格式为大写字母、数字和下划线，首位为字母，最长 40 位 |
| object_type | 精确匹配对象类型，如 expense、activity、membership；格式为小写字母、数字和下划线，首位为字母，最长 30 位 |
| object_id | 对象编号，使用时必须同时提供 object_type，避免不同类型的同号对象混在一起 |
| actor_user_id | 操作者的用户 ID；不是成员 ID |
| before_id | 只返回早于该历史 id 的记录，搭配 limit 加载更早历史；不能与非零 offset 混用 |

例如 `?object_type=expense&object_id=12` 可追溯某笔费用的创建、修改与删除，包括 before、after 快照。软删除费用和归档活动仍可查历史；权限始终限定为本活动成员。

首次请求使用 limit，下一页将上一页最后一条的 id 作为 before_id，并保留原筛选条件。这样新增历史不会导致继续向前翻页时出现重复记录；要查看刚发生的操作，重新请求第一页。原 limit、offset 用法仍保留，查询本身不会新增历史。

## 错误处理约定

业务接口错误在原有 detail 之外增加稳定的 code 和布尔值 retryable；HTTP 状态和原中文提示保持原含义。前端按 code 分支处理，不依赖中文文本匹配。例如：

~~~json
{"detail":"费用已被修改，请刷新后重试","code":"EXPENSE_VERSION_CONFLICT","retryable":false}
~~~

| HTTP 状态 | 前端处理 |
| --- | --- |
| 401 | 登录失效或凭证错误，提示重新登录 |
| 403 | 用户已属于活动，但没有此项操作权限 |
| 404 | 资源不存在，或不属于用户可访问的活动 |
| 409 | 版本冲突、活动已封账、唯一约束冲突或数据库暂时忙 |
| 422 | 字段格式或业务输入校验失败 |
| 500 | 未预期错误；先核对是否已有结果，不盲目再次新增 |
| 503 | 数据库未准备好，检查迁移和运行环境 |

detail 可能是字符串，也可能是字段错误数组。数组项包含 loc、msg、type，不回显输入的密码。无论页面是否禁用按钮，都以接口返回为准。

| code | 恢复方式 |
| --- | --- |
| AUTHENTICATION_REQUIRED | 清理失效令牌并重新登录；保留未提交的表单 |
| INVALID_CREDENTIALS、USERNAME_EXISTS | 在登录或注册表单显示错误，修正输入 |
| ACTIVITY_NOT_FOUND、EXPENSE_NOT_FOUND、INVITE_INVALID | 提示资源不可访问或邀请码无效；非成员与不存在活动使用相同错误码 |
| ACTIVITY_OWNER_REQUIRED、EXPENSE_EDIT_FORBIDDEN | 提示当前账号无权操作 |
| ACTIVITY_LOCKED | 刷新活动状态，停止新增或修改账目 |
| EXPENSE_VERSION_CONFLICT | 保留草稿，重新读取费用，由用户核对后再提交新版本 |
| REQUEST_ID_CONFLICT | 核对原保存请求；不能自动更换编号再次记账 |
| EXPENSE_DELETED | 刷新列表或查历史，不自动恢复费用 |
| VALIDATION_ERROR、INVALID_QUERY、INVALID_EXPENSE、EXPENSE_MEMBER_MISMATCH | 根据 detail 修正参数、日期、金额或成员 |
| DATABASE_BUSY | 唯一标记 retryable 为 true 的错误；等待 Retry-After 秒后有限次重试原请求 |
| DATABASE_NOT_READY | 检查数据库连接与迁移，不按暂忙处理 |
| DATA_CONFLICT | 刷新数据后核对唯一约束冲突，不自动重新提交 |
| INTERNAL_ERROR | 显示通用错误；费用保存可用原 request_id 和原内容查询式重试，不能新生成编号盲目新增 |
| NOT_FOUND、METHOD_NOT_ALLOWED、HTTP_ERROR | 检查调用路径、方法或其他 HTTP 错误；原 HTTP 状态与必要响应头保留 |

DATABASE_BUSY 返回 409 和 `Retry-After: 1`，允许的前端来源可跨域读取该响应头。retryable 不是自动重试授权：仍需限制重试次数，并复用费用 request_id 和原内容；其他业务冲突都为 false。500 的响应使用通用信息，不返回异常堆栈或 SQL 参数，且仅向配置允许的前端来源提供跨域读取权限。

公共定义位于 [app/errors.py](../backend/app/errors.py)。其他模块映射领域异常时应复用 ApiError、ErrorCode 和 error_response；新增稳定错误码先加入 ErrorCode。健康检查 /health 继续使用独立的 status、schema_revision 或 expected_schema_revision 格式。

## 丙的接入位置

| 位置 | 用法与约束 |
| --- | --- |
| [分摊函数](../backend/app/domain/split.py) | calculate_split 接收已验证的 SplitInput，返回按成员 id 排序的 ShareRead 列表 |
| [输入输出结构](../backend/app/schemas.py) | 复用 SplitInput、Participant、ShareRead；预览也必须检查活动成员权限 |
| [数据模型](../backend/app/models.py) | 复用 ActivityStatus、Expense、ExpenseShare、Membership 与 AuditLog |
| [事务入口](../backend/app/database.py) | transaction(engine, write=True) 在第一次读取前使用 BEGIN IMMEDIATE |
| [接口依赖](../backend/app/api/dependencies.py) | 复用 Database 与 CurrentUser；写请求在发送成功响应之前提交事务 |
| [活动权限](../backend/app/services/activity.py) | require_activity 检查活动隔离；require_owner 检查创建者 |
| [历史记录](../backend/app/services/audit.py) | record_audit 与业务变更共用同一个 Session 和事务 |

费用被软删除后，旧分摊仍保留用于追溯。计算余额时必须连接 Expense，并过滤 is_deleted 为 false，不能直接累计全部 ExpenseShare。

付款登记、封账和确认必须使用同一个写事务规则，先拿写锁，再读取状态、余额和待确认占用，再校验并写入。不要仅使用 SQLite 默认的延迟事务替代它；不要在路由外检查状态后再另起事务写入。

当前迁移最新版本为 0002，新增费用请求登记表 expense_requests，为费用创建的重复提交保护提供持久化存储；既有账单、分摊和历史表保持原结构。旧库需要先执行 `uv run --locked alembic upgrade head`；健康检查在数据库版本与当前代码不一致时返回 503。

付款功能请基于当前迁移 head 新增后续迁移；不要重写已经交付的 0001、0002，也不要在应用启动时自动 create_all。将 0002 回退到 0001 会移除请求登记记录；迁移回退验证只在独立测试库执行。

## 乙的答辩准备

可以沿这条链说明一次费用更新：

1. 路由解析金额、成员和 version。
2. JWT 身份校验，查询成员关系，确认费用归属。
3. 在写事务内检查 ACTIVE 状态、编辑权限和最新 version。
4. 通过共享分摊函数重新计算；替换分摊并增加 version。
5. 保存修改前后历史；整个事务成功后返回响应。
6. 发生异常时回滚；并发旧版本更新返回 409。

[测试记录](BACKEND_TEST_REPORT.md)给出已验证的边界。完整课程演示仍需甲、丙、丁的后续功能和集成。

重复保存的实现可沿下面这条链讲解：

1. [ExpenseCreate](../backend/app/schemas.py)验证 request_id 为可选 UUID v4；旧调用保持兼容。
2. [transaction](../backend/app/database.py)在查询请求记录之前取得 SQLite 写锁，两个并发请求不能同时把同一编号判断为未使用。
3. [create_expense 与 creation_fingerprint](../backend/app/services/expense.py)先验证成员权限，再按活动、记录者和编号查已有结果；输入归一化后比较摘要，防止同号异内容。
4. [ExpenseRequest](../backend/app/models.py)的唯一约束提供数据库级保护；新费用、分摊、请求登记和历史一起提交或回滚。
5. 重试已成功的请求返回现有费用的当前版本；若费用已删除则拒绝，避免误恢复。封账后的重试只读，不创建新费用。
6. [请求重试测试](../backend/tests/test_expense_requests.py)验证并发、失败回滚、重建应用、删除和封账边界；[迁移测试](../backend/tests/test_request_migration.py)验证旧数据保留及健康检查。

## 提交规则

每新增一项功能逻辑，完成必要测试后立即建立一次有明确含义的 commit，并推送当前功能分支，不积压到全部功能结束。修复和测试说明可单独提交；不造空提交或修改历史日期。PR 经同伴检查后再合并，保留真实开发记录。
