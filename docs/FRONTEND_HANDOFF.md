# 角色甲前端交接与推进计划

## 2026 年 10 月 31 日完整交接

FR01–FR12 的页面均已接入真实后端。第一阶段之后新增费用增删改查、三种分摊预览、结算与付款状态处理、封账归档、历史前后变化与游标分页、CSV 导出。费用与付款创建都保留 UUID 请求编号，网络结果不确定时可安全重试；费用版本冲突要求加载最新记录并核对。所有最终权限仍由后端决定。

新增组件为 `ExpensePanel`、`ExpenseEditor`、`SettlementPanel`、`PaymentDialog`、`AuditPanel`、`ExportButton`。`src/api/types.ts` 和 `src/api/index.ts` 直接对应 `backend/app/schemas.py` 及路由。所有金额使用整数分；成员字段使用 Membership.id；重复显示名追加成员编号。未引入第二套分摊算法。

该日期验证：类型检查与构建成功，59 项单元测试、17 项真实后端浏览器测试通过；Windows 干净目录复现和 Ubuntu CI 通过。演示初始化与联合启动使用 `scripts/course.py`。当前已改为角色丁本机统一验收并发布 v1.0.0，课堂设备与现场演示另行完成，见 [系统报告](ACCEPTANCE_REPORT.md) 与 [演示指南](DEMO_GUIDE.md)。

以下内容保留为第一阶段历史记录，其中“待开发”仅描述当时范围，已由上述集成工作补齐。

本轮从已合并乙、丙后端的 `origin/main` 提交 `aac4fe1` 开始，在 `feat/frontend` 实现第一段可运行流程：注册登录 → 创建活动 → 邀请码加入 → 查看成员和预算统计。本轮没有修改后端业务逻辑。

## 已实现范围

| 需求 | 当前前端实现 |
| --- | --- |
| FR01 | 注册并登录、登录错误提示、内存令牌、退出、路由保护、过期后原账号重新登录 |
| FR02 | 活动列表、名称与状态筛选、游标加载更多、创建活动、创建者在 ACTIVE 状态编辑名称与预算 |
| FR03 | 邀请码加入、创建者查看和复制邀请码、成员列表、当前用户和创建者标记 |
| FR11 的概览 | 读取统计接口展示消费总额、预算、剩余额度、超预算提示、分类消费与成员承担 |

页面没有示例活动或本地伪造数据。新账号先显示空状态；有后端费用数据时，概览会显示真实统计。只开放已实现的概览和成员页签，不把其他首版页面标记为完成。

## 运行与契约

在仓库根目录启动 `backend/` 后端，在第二个终端进入 `frontend/` 执行 `npm ci`、`npm run dev`。默认前端为 http://127.0.0.1:5173，后端为 http://127.0.0.1:8000；Vite 转发 `/api`，无需浏览器直接跨域访问后端。

- 认证：`POST /api/v1/auth/register`、`POST /api/v1/auth/login`、`GET /api/v1/auth/me`。注册返回用户而非令牌，所以成功后再登录。
- 活动：`GET/POST /api/v1/activities`、`GET/PATCH /api/v1/activities/{id}`、`POST /api/v1/activities/join`。
- 概览与成员：`GET /api/v1/activities/{id}/statistics`、`GET /api/v1/activities/{id}/members`。
- 当前类型对应 `backend/app/schemas.py`，不是自行发明的请求格式；新增模块继续先核对 `/docs`、`/openapi.json` 和两份后端交接文档。

本地 main 如果仍在初始化提交，不能只看 main 的工作目录判断后端进度。当前 `feat/frontend` 已快进到上述合并基线；独立后端 worktree 不会随主目录自动更新。

## 关键实现

| 文件 | 作用 |
| --- | --- |
| `frontend/src/api/client.ts` | Bearer 请求、查询编码、204、字符串或字段数组错误、稳定错误码、取消旧账号响应 |
| `frontend/src/api/types.ts` | 本轮接入接口的 TypeScript 类型 |
| `frontend/src/stores/session.ts` | 内存会话、原账号恢复、退出后清空页面、避免迟到登录恢复会话 |
| `frontend/src/router.ts` | 未登录保护、刷新后返回原活动、限制登录跳转目标 |
| `frontend/src/utils/money.ts` | 字符串与 BigInt 转分，安全整数上限，两位小数格式化 |
| `frontend/src/views/ActivitiesView.vue` | 筛选、游标分页、取消旧请求、创建和加入入口 |
| `frontend/src/views/ActivityDetailView.vue` | 活动状态、创建者权限、成员 ID 映射、真实预算统计 |
| `frontend/src/components/ActivityFormDialog.vue` | 创建与编辑共用表单、校验、失败保留输入 |
| `frontend/e2e/activities.spec.ts` | 独立浏览器账号与真实后端的完整第一阶段验证 |

令牌不写入 localStorage、sessionStorage、URL 或磁盘。过期时页面与草稿保持挂载，通过遮罩要求原账号重新登录；主动退出会清空页面，再登录另一账号不会沿用原草稿。旧账号未完成的 API 响应会被丢弃。

预算空白发送 null；0 发送整数 0。金额按十进制字符串计算，不依靠浮点乘法取整。用户 ID 用于判断活动 owner_id；成员承担则使用 members 返回的成员 id，不能混用。

错误按 code 和状态识别，前端展示中文 detail；422 数组转换为字段提示。HTTP 请求不自动重试。活动创建没有 request_id 契约，因此网络或 5xx 导致结果不确定时，保留输入并阻止在原弹窗再次创建，提示先关闭并核对活动列表。DATABASE_BUSY 暂忙错误可以由用户明确重试，不盲目重放其他写操作。

## 下一阶段顺序

1. **费用与分摊（FR04–FR05）**：费用列表与组合筛选、新增编辑共用表单、三种分摊、后端预览、version 冲突、软删除；创建使用 UUID v4 request_id，重试保留同一请求内容。
2. **余额与结算（FR06–FR09）**：正式余额、待确认占用、可登记额度、转账建议、创建者封账；付款只能在 SETTLING 登记，收款人确认或拒绝、付款人撤销，最后刷新活动自动结清状态及归档入口。
3. **历史与导出（FR10、FR12）**：历史筛选、修改前后对照、游标分页；带令牌取得 CSV Blob 并下载。
4. **整系统验收**：在当前第一阶段浏览器测试基础上增加三人完整账单与结算流程，由丁补齐 T01–T20 对应证据、重启持久化、本机干净目录复现和报告。

每一阶段先按实际接口完成一个流程，再提交独立 PR，由丁统一审查验收。前端不重新实现后端的最终余额、分摊与权限判断。当前第一阶段测试不能替代课程要求的完整记账至归档验收。

## 验证

命令、环境、实际结果和限制见 [前端测试记录](FRONTEND_TEST_REPORT.md)。CI 定义在 `.github/workflows/frontend.yml`，检查构建、单元测试和真实后端浏览器流程；新增配置的远端执行结果需在推送后记录，不能将本地通过视为远端 CI 已通过。
