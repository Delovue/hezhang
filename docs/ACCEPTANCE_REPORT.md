# 合账系统验收与测试报告

## PR #8 付款刷新及并行整合补充

首轮提交 `ae0fbee` 的 Ubuntu 前后端与 Windows 后端检查通过，但 [Windows 浏览器检查](https://github.com/Delovue/hezhang/actions/runs/41279569608/job/124768531048) 为 **22 通过、1 失败**。已下载核对失败报告：三人结算流程在付款被拒绝后立即登记剩余金额，余额尚未刷新完成，客户端按旧额度拒绝提交，弹窗提示“付款金额超过双方可登记额度”；随后界面才显示新的可登记额度。没有通过延长断言或自动重试消除该失败。

`f9f9729` 让普通登记、按建议登记及弹窗提交等待活动、成员、余额和建议成功加载，并在失败后保留重试入口与输入。新增慢响应和 503 回归均先失败、后通过；相关 9 项浏览器检查及类型检查通过，随后该干净提交的构建、66 项单元测试和完整 **25 项浏览器测试**通过，无失败／跳过／重试／flaky。后端及脚本未变化，345 项后端和 HTTP／重启结果沿用下节基线。

推送时发现队友同时提交了 `d1d0248`，包含相同的付款入口保护。本轮正常合并双方历史，保留队友的慢响应回归和本地的 503 恢复回归，去掉重复场景；继续保留弹窗内提交保护。整合后的应用源码与已验证的 `f9f9729` 一致，整合后的 6 项协作回归及类型检查再次通过。最终远端验证以 [PR #8 最新 Checks](https://github.com/Delovue/hezhang/pull/8/checks) 为准，旧失败不会被当作通过。

版本、报告哈希、失败 CI 与整合范围记录在 [collaboration-refresh.json](verification/collaboration-refresh.json) 的 `payment_refresh_followup` 中；完整前端报告在本地 `.e2e/payment-refresh-full/`。以下 23 项为付款刷新修复之前的历史验证。

## 2026-11-01 协作刷新修复

在已合并 PR #6、PR #7 的 `068c55c` 上检查实际协作流程，新增四项真实后端浏览器回归，先复现失败再修复：

- `0c7da28`：切换标签统一刷新活动、成员、统计及常驻结算摘要；侧栏“去处理”也使用相同入口。修复伙伴加入后成员页仍显示旧名单，以及付款撤销后再次进入已打开的结算页仍显示待确认的问题。
- `759355b`：活动和成员加载期间或加载失败时，暂停费用新增、编辑和删除入口；成功刷新后恢复。受控响应等待与 503 故障注入分别验证慢速加载和重试恢复，新增表单包含刚加入的成员，1.01 元两人分摊为 0.51／0.50 元。既有表单草稿不因刷新重新初始化。

在干净提交 `759355b243078565f380c10d6fc387e57121431c` 上运行 `scripts/acceptance.py`，11 个阶段全部通过：后端 **345** 项、前端单元 **66** 项、浏览器 **23** 项，0 失败／跳过，浏览器无重试或 flaky；Ruff、类型检查、构建、隔离迁移及 schema 检查、18 项 HTTP 流程和 3 项重启检查均通过。app 语句覆盖仍为 1344／1359（98.8962%）。本地环境为 Windows、Python 3.12.16、Node.js 24.18.0、npm 11.16.0。

机器可核对的版本、逐阶段结果、四项新增用例、修复前失败和原始报告哈希见 [collaboration-refresh.json](verification/collaboration-refresh.json)。完整本地原始报告保存在 `.e2e/collaboration-acceptance-20261101/`；该目录被 Git 忽略。本段记录本地验证，后续远端结果以此次 PR 的最新提交 Checks 为准。人工课堂验收仍待完成，已有候选标签不移动。下文保留历史测试数量与版本边界。

2026-11-01 后续界面集成：PR #6 与 PR #7 组合后，统一验收 11 阶段通过，后端 345、前端单元 66、浏览器 19 项及服务重启通过。三处界面修复、后续费用回归、提交和截图版本边界见 [PR #6 集成复核](PR6_REVIEW.md)。以下保留各阶段历史验证记录。

## PR #7 Windows CI 后续修复

`b211e21` 的 [PR 前端检查](https://github.com/Delovue/hezhang/actions/runs/41272977245) 在 Windows 上有 7 项浏览器失败；同提交的 Ubuntu 前端、双平台后端和 push 前端检查通过，不能据此忽略 PR 检查失败。已下载并核对失败的 JSON、截图上下文和 trace。

五项失败发生在注册后的 5 秒导航断言。trace 中注册返回 201，耗时约 2.50 秒；随后登录返回 200，耗时约 5.86 秒，`/auth/me` 也返回 200。测试先到期，不是接口拒绝注册。另外两项结算失败来自成员刷新尚未完成就打开费用表单，导致缺少新成员，甚至仅由创建者承担后直接平账。

修复将认证辅助函数统一为等待真实 register／login／me 响应并检查状态，再断言页面；刷新辅助函数等待活动、成员、统计三项响应及加载状态结束，再继续操作。三人长流程单独提供 120 秒总预算，单次页面断言仍为默认 5 秒，自动重试仍为 0。新增两项受控延迟回归：登录响应延迟 5.5 秒、成员响应延迟 1 秒；延迟仅用于故障注入，不作为同步手段。

本地 4 项针对性测试通过，随后完整浏览器 **19 项通过、0 失败／跳过**；类型检查与构建通过。此次只修改测试及记录，未修改应用或后端账务逻辑。证据见 [pr7-ci-repair.json](verification/pr7-ci-repair.json)，修复后最终提交的远端状态见 [PR #7 Checks](https://github.com/Delovue/hezhang/pull/7/checks)。下文 17 项是本轮早先的浏览器基线，予以保留。

## 2026-11-01 角色丁复核

本轮在 main `9193449` 的已合并功能上完成角色丁集成工作，见 [PR #7](https://github.com/Delovue/hezhang/pull/7) 和 [交接与未完成工作](ROLE_D_HANDOFF.md)。下文 2026-10-31 结果保留为历史证据，不覆盖原始记录。

| 本轮检查 | 实际结果 |
| --- | --- |
| 环境 | Windows 11，Python 3.12.13，项目缓存中的 Node.js 22.12.0、npm 10.9.0，锁定依赖及 Chromium |
| 后端 | 345 项通过，0 失败／跳过；含新增 11 项验收工具测试及 1 项带不可用代理的真实 HTTP／重启回归 |
| app 语句覆盖 | 1344／1359，98.8962%；本轮未修改账务业务代码 |
| 前端 | 59 项单元测试、17 项真实后端浏览器测试通过；0 失败／跳过；类型检查及构建通过 |
| 迁移与代码检查 | 独立数据库升级至 0003，alembic check、Ruff check／format、actionlint 1.7.12 通过 |
| HTTP 与服务重启 | 18 项流程检查及 3 项重启持久化检查通过 |
| 统一验收 | `scripts/acceptance.py` 的 11 个阶段全部通过，失败、中断及未运行阶段会单独记录 |
| 人工验收 | T20 目标课堂电脑、四名成员独立运行、两次现场计时仍为 TODO |

逐项结果、用例名称、覆盖率、环境及原报告哈希见 [role-d-results.json](verification/role-d-results.json)。本地运行开始于 `0769214`，文档仍在编辑，浏览器阶段使用后续提交为 `60baf98` 的刷新等待断言；记录如实保留 dirty 状态，不称为干净检出验证。最终 head 的干净环境结果应核对 [PR #7 Checks](https://github.com/Delovue/hezhang/pull/7/checks)；新增 CI 使用 Windows／Ubuntu 矩阵，指定测试证据保存 14 天，不上传数据库或密钥文件。

本轮发现并修复：

- 本机 Node 18 低于要求：使用项目缓存中的 Node 22.12，保留系统原有安装。
- 首次统一验收的 HTTP 阶段被系统代理影响，健康检查正文无法解析：本地探测及冒烟客户端直接访问回环服务，并用不可用代理环境完成真实回归。
- Windows CI 的均摊用例在成员刷新完成前打开表单，预览只有创建者：测试改为等待成员数量更新，再打开表单，未通过延时或自动重试掩盖失败。
- Windows CI 未正确传递 npm 报告参数，隐藏目录默认不归档：前端步骤统一使用 bash，上传仅显式允许的测试报告路径并启用隐藏文件。

以上开发期失败保留在新结果 JSON；最终本地全量为通过。既有 Starlette／HTTPX TestClient 弃用提示仍存在，未导致失败。

## 2026-10-31 历史验收记录

汇总日期：2026 年 10 月 31 日。最终浏览器验证基线 `905ac57`；后端与前端单元测试基线 `bfc238b`，相关源文件之后未变化；干净目录和已记录 CI 的基线为 `878c803`。PR #5 集成费用、结算、历史、导出、演示工具和课程材料。当前状态为课程候选版：自动化及本机验证通过，T20 中实际第二台电脑和团队现场验收未执行。

## 一 环境与证据

| 项目 | 本次实际结果 |
| --- | --- |
| 本地环境 | Windows，Python 3.12.16，Node.js 24.18.0，npm 11.16.0，Chromium |
| 后端 pytest | 333 通过，0 失败，0 跳过；约 118.69 秒 |
| app 语句覆盖 | 1344／1359，98.8962%；15 行未覆盖，详见结果 JSON |
| 前端 Vitest | 59 通过，0 失败，0 跳过 |
| 浏览器 Playwright | 17 通过，0 失败，0 跳过；约 69.35 秒；真实后端、隔离数据库 |
| 类型检查与构建 | vue-tsc、Vite 构建成功 |
| Python 静态检查 | Ruff check 与 format check 通过 |
| 数据库迁移 | 0001 → 0002 → 0003 成功；alembic check 无待生成变更 |
| 真实 HTTP 流程 | 18 项检查通过，随后重启服务的 3 项持久化检查通过 |
| 干净目录复现 | git archive 导出 `878c803`；新建虚拟环境、uv sync --locked、npm ci、构建、三人浏览器流程与重启验证通过 |
| 依赖审计 | 本次 npm ci 报告 0 vulnerabilities；不代表未来不会披露新漏洞 |
| 桌面与手机布局 | 1280 宽桌面、390 宽移动视口截图检查；移动端未出现页面横向溢出 |

逐用例名称、执行时间、结果及未覆盖行保存在 [local-results.json](verification/local-results.json)。截图来自本次真实应用的 Playwright 浏览器运行，使用虚构测试账号：[结算桌面](assets/settlement-desktop.png)、[结算移动端](assets/settlement-mobile.png)、[历史记录](assets/history-desktop.png)、[统计概览](assets/activity-overview.png)。

`878c803` 的 [后端 CI](https://github.com/Delovue/hezhang/actions/runs/41086025356) 与 [前端 CI](https://github.com/Delovue/hezhang/actions/runs/41086025320) 均成功。它们在 Ubuntu 24.04 的新 runner 中安装锁定依赖；后端 CI 也执行真实 HTTP 和服务重启验证。最终合并时还需检查 PR 最新 head 的 CI，不能使用旧提交的成功结果替代。

## 二 T01–T20 验收对应

| 用例 | 实际检查与结果 | 主要自动化证据 | 状态 |
| --- | --- | --- | --- |
| T01 | 100 元三人均摊 33.34／33.33／33.33 | domain/test_split.py、test_split.py | 通过 |
| T02 | 一分钱分配、输入顺序变化仍确定 | domain/test_split.py | 通过 |
| T03 | 按份数分摊并保持金额守恒 | domain/test_split.py、expenses.spec.ts | 通过 |
| T04 | 错误合计、非法份数、重复成员被拒绝 | test_split.py、test_expenses.py、expense.test.ts | 通过 |
| T05 | 车费仅 A、B 分摊，C 不承担 | settlement.spec.ts、domain/test_balance.py | 通过 |
| T06 | 三人例子余额 50／−10／−40 元 | test_balance_api.py、settlement.spec.ts | 通过 |
| T07 | 待确认 20 元不改余额，只占用额度 | test_payments_api.py、settlement.spec.ts | 通过 |
| T08 | 确认后余额 30／−10／−20 元 | test_payment_actions_api.py、settlement.spec.ts | 通过 |
| T09 | 重试、重复确认、并发确认只生效一次 | test_settlement_concurrency.py、浏览器丢响应重试 | 通过 |
| T10 | 并发付款不能超过双方额度 | test_settlement_concurrency.py、test_payments_api.py | 通过 |
| T11 | 确认与撤销竞争只允许一个终态 | test_settlement_concurrency.py | 通过 |
| T12 | 非收款人和跨活动操作被拒绝 | test_api_errors.py、test_payment_actions_api.py、浏览器 403 检查 | 通过 |
| T13 | 封账后编辑被拒绝；封账与编辑并发保持一致 | test_settlement_concurrency.py、settlement.spec.ts | 通过 |
| T14 | 旧 version 不覆盖新内容，前端保留草稿 | test_expenses.py、expenses.spec.ts | 通过 |
| T15 | 审计失败时费用、分摊、付款和去重编号回滚 | test_payment_rollback.py、test_expense_requests.py、test_expenses.py | 通过 |
| T16 | 结清可归档，未结清被拒绝 | test_lifecycle_api.py、settlement.spec.ts | 通过 |
| T17 | 空活动或净额全零时直接结清 | test_lifecycle_api.py、settlement.spec.ts | 通过 |
| T18 | 付款不计入消费；CSV 中文、份额、公式转义 | test_reports_api.py、export.spec.ts、settlement.spec.ts | 通过 |
| T19 | 刷新重新登录、保存数据保留、进程重启后核对 | activities.spec.ts、course.py verify | 通过 |
| T20 | 三人 UI 全流程及新目录、Ubuntu CI 复现通过；实际第二台电脑与四名成员验收待执行 | settlement.spec.ts、干净目录记录、CI | 部分完成 |

前端文件位于 `frontend/e2e/` 或 `frontend/tests/`，后端文件位于 `backend/tests/`。并发测试使用同一文件数据库上的独立连接；浏览器账号使用独立会话，测试不复用演示数据库。覆盖率为语句覆盖，未进行形式化正确性证明或高并发容量测试。

## 三 缺陷与验证过程

| 发现 | 处理 | 回归证据 |
| --- | --- | --- |
| 测试工具依赖含已知漏洞 | Vitest 升至锁定的 4.1.12，重新安装依赖 | 单元测试通过，npm 审计当前为零 |
| 成功状态但响应正文不完整会被当成成功 | 客户端返回 INVALID_RESPONSE，写表单保留原请求编号 | client.test.ts；费用、付款丢响应的真实浏览器重试 |
| 读取响应正文期间切换账号可能接收旧数据 | 正文读取后再次检查绑定令牌 | client.test.ts |
| 费用加载更多使用尚未提交的新筛选值 | 分页使用已提交的筛选快照 | expenses.spec.ts 的 21 笔费用分页用例 |
| 删除费用的冲突说明被列表刷新清掉 | 单独保存操作错误，冲突时刷新最新记录与活动状态 | expenses.spec.ts 删除冲突用例 |
| 同名成员在金额选择中难以区分 | 重复显示名追加成员编号 | members.test.ts |
| 窄屏活动页签被截断 | 改为多列换行布局 | 390 像素视口及截图检查 |
| 首轮浏览器断言未匹配原生 select 的可访问名称 | 补显式 aria-label 后复测 | expenses.spec.ts 通过 |
| 首轮 CSV 测试错误假设备注在导出契约中 | 按真实契约测试费用说明、中文、逗号和公式前缀 | export.spec.ts 通过 |
| 删除冲突用例与创建后的异步刷新竞争，整套运行时未必产生旧版本 | 在 DELETE 捕获版本后制造竞争更新，连续 3 次针对性验证通过，再全量 17 项通过 | expenses.spec.ts；失败记录摘要保留在结果 JSON |
| 历史断言同时匹配错误提示和成功通知 | 将断言限定到历史面板 | history.spec.ts 通过 |

开发期失败已如实记录，最终全量运行无失败。运行时仍有 Starlette 对现有 HTTPX TestClient 的弃用提示；它未影响此次测试，但后续升级依赖时应验证替代方案。没有为了隐藏提示而更改已锁定的后端依赖。

## 四 重现命令

后端，在 `backend/`：

```text
uv sync --locked
uv run --locked ruff check app tests migrations
uv run --locked ruff format --check app tests migrations
uv run --locked pytest -q --cov=app --cov-report=term-missing
```

前端，在 `frontend/`：

```text
npm ci
npm run build
npm test
npm run test:install-browser
npm run test:e2e
```

系统重启检查，在仓库根目录：

```powershell
backend/.venv/Scripts/python.exe scripts/course.py verify --directory .e2e/acceptance-new
```

目录必须尚不存在；Linux/macOS 使用 `backend/.venv/bin/python`。没有 uv 命令时，可用已安装 uv 模块的解释器执行 `python -m uv`。CI 使用相同锁文件与业务测试。

## 五 尚待人工完成

课程正式发布前，需在实际第二台／课堂电脑完成 [DEMO_GUIDE.md](DEMO_GUIDE.md) 的最终验收清单，填写操作者、设备环境、版本哈希、运行结果和演示时长。此处不能用本机干净目录或云端 CI 冒充课堂设备验收。目前没有已知阻塞主流程的代码缺陷，也没有声称全部课程验收已完成。
