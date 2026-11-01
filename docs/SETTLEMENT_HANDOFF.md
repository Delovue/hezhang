# 角色丙结算后端交接说明

现行验收规则（2026-11-01）：角色丁在本机统一验收并发布 v1.0.0，不要求四人独立运行或同伴签字；课堂设备与演示另行完成，详见 [发布记录](RELEASE_V1.md)。下文未执行或待集成内容只表示当时模块分支的历史范围，不是当前发布缺口。

本轮交付分摊预览、余额与转账建议、付款登记与确认、封账与归档、预算统计和 CSV 导出，可供甲对接“概览、结算”标签页，供丁编写端到端测试。开发分支为 feat/settlement，已合并乙的 feat/backend-foundation。

## 当前实现与分工边界

| 范围 | 当前结果 |
| --- | --- |
| FR05 | 三种分摊纯函数；费用保存与分摊预览共用同一实现 |
| FR06 | 每位成员的垫付、承担、已确认付出与收到、待确认占用、余额和可登记额度 |
| FR07 | 基于可登记额度的转账建议；生成建议不修改余额 |
| FR08 | 付款登记（含 request_id 重试保护）、收款人确认或拒绝、付款人撤销 |
| FR09 | 创建者发起结算、结清自动判定、创建者归档 |
| FR10 的丙侧部分 | 付款状态变化与活动状态变化写入操作历史 |
| FR11 | 消费总额、剩余预算、超预算提示、分类汇总、成员承担 |
| FR12 | 费用明细 CSV，UTF-8 BOM，公式注入防护，归档后仍可导出 |

数据库迁移新增 0003，创建 payments 表。旧库需要先执行 `uv run --locked alembic upgrade head`。

## 接口一览

路径均加 /api/v1 前缀，均需登录，且只允许本活动成员访问；非成员统一返回 404。

| 方法与路径 | 行为 |
| --- | --- |
| POST /activities/{id}/split-preview | 请求体与费用的 amount_cents、split_method、participants 相同；返回分摊结果，不保存 |
| GET /activities/{id}/balances | 每位成员一行，按成员 id 升序 |
| GET /activities/{id}/settlement-suggestions | 转账建议列表 |
| GET /activities/{id}/payments | 付款列表，按登记倒序；可用 status 筛选，支持 limit、offset |
| POST /activities/{id}/payments | 当前用户作为付款人登记付款 |
| POST /activities/{id}/payments/{payment_id}/confirm | 收款人确认 |
| POST /activities/{id}/payments/{payment_id}/reject | 收款人拒绝 |
| POST /activities/{id}/payments/{payment_id}/cancel | 付款人撤销 |
| POST /activities/{id}/start-settlement | 创建者发起结算 |
| POST /activities/{id}/archive | 创建者归档已结清的活动 |
| GET /activities/{id}/statistics | 预算与消费统计 |
| GET /activities/{id}/export.csv | 下载费用明细 CSV |

所有成员标识都是成员 id（members 接口返回的 id），不是用户 user_id。

同一活动内有效费用总额上限为 MAX_CENTS（9007199254740991 分），由费用创建和修改接口检查，超限返回 422 INVALID_EXPENSE。所有余额、额度、统计和转账建议都不超过这个总额，前端可以按普通 JSON 数字解析，不会丢精度；每条转账建议的金额都可以直接用于登记付款。

错误响应沿用乙定义的统一格式 `{"detail", "code", "retryable"}`，前端按 code 处理，见下文“错误码”。

## 甲的接入说明

### 余额页

GET balances 每行字段：

| 字段 | 含义 | 建议展示 |
| --- | --- | --- |
| paid_cents | 累计垫付 | 垫付 |
| owed_cents | 累计承担 | 承担 |
| confirmed_out_cents / confirmed_in_cents | 已确认付出 / 收到 | 已结算 |
| pending_out_cents / pending_in_cents | 待确认付出 / 收到 | 待确认 |
| balance_cents | 正式余额，正数应收、负数应付 | 应收 X 元 / 应付 X 元 / 已结清 |
| available_out_cents / available_in_cents | 扣除待确认占用后还能登记的付出 / 收到 | 登记付款时的金额上限 |

待确认付款不改变 balance_cents，只减少 available_*。收款人确认后才进入正式余额。

转账建议每项为 payer_member_id、payee_member_id、amount_cents，可直接作为“登记付款”表单的预填值（当前用户是建议中的付款人时）。

### 登记付款

~~~json
{"payee_member_id": 1, "amount_cents": 2000, "request_id": "由 crypto.randomUUID() 生成"}
~~~

- 付款人固定为当前登录用户，不能代他人登记。
- request_id 必填，格式为 UUID v4。用户点击“登记”时生成一次，双击或超时重试必须复用原编号和原内容。
- 首次登记返回 201；同编号同内容重试返回 200 与原记录；同编号不同金额或收款人返回 409 REQUEST_ID_CONFLICT。
- 只有 SETTLING 状态的活动可以登记付款，其他状态返回 409 PAYMENTS_CLOSED。
- 金额超过付款人 available_out_cents 或收款人 available_in_cents 返回 409 PAYMENT_QUOTA_EXCEEDED，detail 中带有当前上限。
- 给自己付款或收款人不属于本活动返回 422 INVALID_PAYMENT。

### 确认、拒绝、撤销

| 操作 | 谁可以执行 | 结果 |
| --- | --- | --- |
| confirm | 收款人 | CONFIRMED，进入正式余额 |
| reject | 收款人 | REJECTED，释放占用额度 |
| cancel | 付款人 | CANCELLED，释放占用额度 |

创建者也不能代替收款人确认。操作者不符返回 403 PAYMENT_ACTION_FORBIDDEN；付款已处于其他终态返回 409 PAYMENT_STATUS_CONFLICT；对同一付款重复执行同一动作返回 200 与当前记录，不会重复入账。页面可按“当前成员 id 是否等于 payee_member_id / payer_member_id 且状态为 PENDING”决定是否显示按钮，但仍以接口返回为准。

最后一笔确认使全部余额归零时，活动自动变为 SETTLED。确认成功后请重新获取活动详情、余额和建议。

### 封账与归档

- start-settlement 只有创建者可调用（否则 403 ACTIVITY_OWNER_REQUIRED），只能在 ACTIVE 状态调用一次（否则 409 SETTLEMENT_ALREADY_STARTED）。返回更新后的活动：有未结余额时为 SETTLING；没有费用或净额恰好全零时直接为 SETTLED。
- 进入 SETTLING 后，乙的费用、成员和预算写接口都返回 409 ACTIVITY_LOCKED，邀请码不再返回。
- archive 只有创建者可调用，且仅在 SETTLED 状态可用，否则返回 409 ACTIVITY_NOT_SETTLED。归档后所有查询和导出仍可用。

### 概览与导出

statistics 返回 total_spent_cents、budget_cents、remaining_budget_cents、over_budget、by_category、by_member。未设预算时 budget_cents 与 remaining_budget_cents 为 null，over_budget 为 false；超预算时 remaining_budget_cents 为负数。结算付款不计入消费。

导出直接用带令牌的请求下载 export.csv。由于令牌只在内存中，不能使用普通链接跳转，需要用 fetch 取得 Blob 后触发下载。文件名在 Content-Disposition 的 filename* 中，为“活动名-费用明细.csv”。

### 操作历史中的新动作

| action | object_type | 说明 |
| --- | --- | --- |
| PAYMENT_CREATED | payment | 登记付款 |
| PAYMENT_CONFIRMED / PAYMENT_REJECTED / PAYMENT_CANCELLED | payment | 付款状态变化，含 before、after |
| SETTLEMENT_STARTED | activity | 发起结算 |
| ACTIVITY_SETTLED | activity | 确认付款后自动结清 |
| ACTIVITY_ARCHIVED | activity | 归档 |

付款历史中不包含 request_id。

### 错误码

以下为丙接口新增或复用的 code，定义在 [app/errors.py](../backend/app/errors.py)。通用错误码（AUTHENTICATION_REQUIRED、VALIDATION_ERROR、DATABASE_BUSY 等）的处理方式见[后端交接说明](BACKEND_HANDOFF.md)。

| code | HTTP | 场景 | 前端处理 |
| --- | --- | --- | --- |
| ACTIVITY_NOT_FOUND | 404 | 活动不存在或当前用户不是成员 | 返回活动列表 |
| PAYMENT_NOT_FOUND | 404 | 付款不存在或不属于该活动 | 刷新付款列表 |
| INVALID_PAYMENT | 422 | 金额非法、给自己付款、收款人不属于本活动 | 在表单显示 detail，修正输入 |
| EXPENSE_MEMBER_MISMATCH | 422 | 分摊预览的成员不属于本活动 | 刷新成员列表后重选 |
| INVALID_EXPENSE | 422 | 分摊参数在领域校验中不成立；保存费用后活动有效费用总额会超过上限 | 在表单显示 detail |
| ACTIVITY_OWNER_REQUIRED | 403 | 非创建者发起结算或归档 | 隐藏按钮并提示无权限 |
| PAYMENT_ACTION_FORBIDDEN | 403 | 非收款人确认或拒绝、非付款人撤销 | 提示无权限，刷新付款列表 |
| PAYMENTS_CLOSED | 409 | 活动不在结算中，不能登记或处理付款 | 刷新活动状态 |
| PAYMENT_QUOTA_EXCEEDED | 409 | 超过付款人或收款人的可登记额度 | 刷新余额，按新的 available_* 修改金额 |
| REQUEST_ID_CONFLICT | 409 | 同一 request_id 提交了不同内容 | 核对原登记，不能换编号自动重试 |
| PAYMENT_STATUS_CONFLICT | 409 | 付款已是其他终态 | 刷新付款列表 |
| SETTLEMENT_ALREADY_STARTED | 409 | 重复发起结算 | 刷新活动状态 |
| ACTIVITY_NOT_SETTLED | 409 | 未结清时归档 | 提示先完成全部付款确认 |
| ACTIVITY_LOCKED | 409 | 结算开始后修改费用、成员或预算（乙的接口） | 刷新活动状态，停止编辑 |

## 设计取舍

以下三点在开发计划中没有写明，由丙确定，需要甲、乙知悉：

1. 付款只在 SETTLING 状态登记。ACTIVE 时账目仍可修改，登记付款会让额度随改账变化，因此不开放。
2. 超出可登记额度返回 409 而非 422。额度取决于当前余额和其他待确认付款，同一金额在别的付款被拒绝后可能合法，属于状态冲突。
3. 对同一付款重复确认、重复拒绝、重复撤销都返回原结果；计划只要求重复确认如此，丙统一了三者的行为。

## 代码位置与答辩路线

| 位置 | 内容 |
| --- | --- |
| [domain/split.py](../backend/app/domain/split.py) | 三种分摊；calculate_split 为乙的费用服务保留的入口 |
| [domain/balance.py](../backend/app/domain/balance.py) | 余额公式与可登记额度 |
| [domain/settlement.py](../backend/app/domain/settlement.py) | 转账建议贪心匹配 |
| [domain/payment.py](../backend/app/domain/payment.py) | 付款登记校验、request_id 重试判断、付款状态机 |
| [domain/activity.py](../backend/app/domain/activity.py) | 活动生命周期与结清判定 |
| [domain/statistics.py](../backend/app/domain/statistics.py)、[domain/export.py](../backend/app/domain/export.py) | 统计与 CSV |
| [services/balance.py](../backend/app/services/balance.py) | 读取有效费用与付款，计算余额 |
| [services/payment.py](../backend/app/services/payment.py) | 写锁内登记、确认、拒绝、撤销 |
| [services/lifecycle.py](../backend/app/services/lifecycle.py) | 封账、自动结清、归档 |

一次付款确认的处理链：

1. 路由解析 payment_id，JWT 校验身份；POST 请求的事务以 BEGIN IMMEDIATE 开始，先取得写锁。
2. 校验活动成员关系，读取付款及当前成员。
3. 领域状态机判断操作者是否为收款人、付款是否仍为 PENDING；重复确认直接返回原结果。
4. 修改状态并写入 PAYMENT_CONFIRMED 历史。
5. 重新计算余额；全部为零且无待确认付款时，活动转为 SETTLED 并写入 ACTIVITY_SETTLED。
6. 整个事务提交后返回；任一步失败全部回滚。

领域层只做纯计算，不访问数据库；服务层负责读取、权限和事务。领域错误携带 ErrorCode，在 main.py 按类别映射为 422、403、409，并用乙的 error_response 输出统一格式。

## 测试

在 backend 目录执行 `uv run --locked pytest -q`。丙新增的测试与计划用例对应如下：

| 用例 | 测试文件 |
| --- | --- |
| T01–T05 | tests/domain/test_split.py、tests/test_split_preview.py |
| T05–T08 | tests/domain/test_balance.py、tests/test_balance_api.py、tests/test_payment_actions_api.py |
| T09–T11 | tests/test_payments_api.py、tests/test_payment_actions_api.py、tests/test_settlement_concurrency.py |
| T12 | 各接口测试中的非成员与错误操作者场景 |
| T13 | tests/test_lifecycle_api.py、tests/test_settlement_concurrency.py |
| T15 | tests/test_payment_rollback.py |
| 错误码契约 | tests/test_settlement_error_codes.py |
| T16、T17 | tests/domain/test_activity.py、tests/test_lifecycle_api.py |
| T18 | tests/test_reports_api.py、tests/domain/test_statistics.py、tests/domain/test_export.py |

并发测试使用独立 SQLite 连接，同时用“持有写锁期间观察另一请求是否等待写锁”的方式验证额度检查发生在锁内。T14、T19、T20 属于乙的接口或整系统验收，不在本文件范围。
