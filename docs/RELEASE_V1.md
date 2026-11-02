# v1.0.0：课堂演示前第一版

## 验收责任与发布范围

2026-11-01 按项目负责人要求调整验收制度：由角色丁单独统筹并执行本机整系统测试、代码与交付材料复核、缺陷复测和发布。不再要求甲乙丙丁分别独立运行、四人签字、同伴审查或甲单独确认界面作为发布门槛。开发岗位与真实 Git 作者记录保持不变。

T01–T19 的金额、权限、事务、统计及持久化要求不变；T20 改为“角色丁在本机独立干净目录安装锁定依赖，完成三账号真实浏览器全流程、CSV 导出、服务重启与演示启动复现”。课堂电脑、投影可读性、现场计时和答辩归入课堂演示，独立于本次软件发布验收。

首次正式软件版本为 `v1.0.0`，发布名称“课堂演示前第一版”。既有 `v1.0.0-rc.1` 保留原历史指向；课堂完成后按需要另立 `v1.0-course` 课程提交标签，不移动已发布标签。

## 本机验收记录

### 最终验收（v1.0.0 发布代码）

首轮验收之后，PR #8 又补充了付款弹窗提交保护（`f9f9729`）和审查修复（切换标签重复请求、加载提示闪烁、删除费用不必等待成员、刷新期间隐藏旧额度），新增 1 项浏览器回归，并以 `24df689` 合并入主分支。发布分支以合并提交 `5f652de` 合入该最终代码，解决四处文档冲突后，在干净工作树上重新执行完整 11 阶段，后端 345、单元 66、浏览器 26 项通过。

合并后主分支的 Windows CI 两次出现费用列表刷新超时。CI trace 显示请求均已发出并成功返回，但经 Vite 代理的请求在 Windows 运行器上单次需 3–6 秒，而刷新先等待活动信息再加载列表，两段时延相加超过 5 秒断言。`a5c7bcd` 让列表、右侧摘要与活动信息并行加载（录入按钮仍等待活动与成员就绪），`5264b56` 新增活动信息慢响应回归，修复前失败、修复后通过；未延长断言超时。在 `5264b56` 的干净工作树上重新执行完整 11 阶段：

- 后端 345 项、前端单元 66 项、Chromium 浏览器 27 项全部通过，无失败、跳过或 flaky；app 语句覆盖率 1344/1359（98.90%）。
- Ruff、迁移检查、构建、18 项 HTTP 流程与 3 项重启检查通过；同提交 Windows／Ubuntu CI 通过。
- 环境：WSL2 Debian（Linux），Python 3.12.15，Node.js 24.16.0，npm 11.13.0；锁文件哈希与报告哈希见 [preclass-v1-final.json](verification/preclass-v1-final.json)。

v1.0.0 以此最终验收为准；下文首轮记录与 [preclass-v1.json](verification/preclass-v1.json) 保留为历史证据。

### 首轮验收

验收负责人：角色丁。设备：当前 Windows 本机。首轮受验代码：`e66c6c2`，包含当时 PR #8 的协作刷新与付款入口修复（不含其后续提交，见下文“最终验收”）。先在 `4e829dd` 的独立干净目录重新安装 Python 与 npm 锁定依赖，随后在同一干净工作树切换到最终代码重跑完整验收；锁文件未变化，Chromium 使用本机已安装缓存。测试结果和环境精确值见 [preclass-v1.json](verification/preclass-v1.json)。后续提交仅补齐说明与交付证据；最终发布提交还需通过 Windows／Ubuntu CI。

首轮完整验收 11 阶段全部通过：后端 345 项、前端单元 66 项、Chromium 浏览器 24 项，无失败、跳过或 flaky；Ruff、类型检查、构建、迁移检查、18 项 HTTP 流程与 3 项重启检查通过。app 语句覆盖率 1344/1359（98.90%）。另实际执行 prepare + serve，验证默认演示端口、前端页面、OpenAPI 1.0.0、三个演示账号经前端代理登录、三人成员和空账本；检查后已停止本次启动的服务。

已复核 1280px 桌面和 390px 手机结算截图，报告四张截图均来自本次运行；需求到代码索引同步至 ActivityProgress 和 SettlementSummary。依赖安装期间 npm audit 报告 0 漏洞；pytest 有一条上游 Starlette／HTTPX 弃用提示，不影响本轮通过，也不等同于完整安全审计。

发布前复核：当前 FR01–FR12 已实现；PR #6、#7、#8 已合并关闭，本发布 PR #9 合入 PR #8 最终代码后重新验收。开发期模块报告与 JSON 保留历史结果，不将其当成当前缺口，也不补造历史任务。验收输出格式 2 使用 `acceptance_owner=role_d`、`acceptance_scope=local_preclass`，自动化结果与 `classroom_demo=pending` 分开；旧格式 `manual_acceptance` 只表示旧验收规则下的历史状态。


### 本轮 T01–T20 结果

| 用例 | 本轮验证内容 | 证据入口 | 结果 |
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
| T20（当前定义） | 丁在本机干净目录安装、三账号 UI、CSV、重启和联合启动 | preclass-v1.json、浏览器 JSON、JUnit、serve 记录 | 通过 |

## 交付内容与使用

- GitHub `v1.0.0` Release：带版本前缀的源码 ZIP、验收证据 ZIP、SHA256 校验文件和发布说明。
- 源码包含前后端、锁文件、迁移、测试、运行脚本、课程报告、演示指南和截图；不包含虚拟环境、node_modules、私人数据库或本地密钥。
- 首次运行先按 [README](../README.md) 安装依赖，再按 [演示指南](DEMO_GUIDE.md) 初始化独立演示目录。源码包需要安装依赖，不是免安装可执行程序。
- 验收证据仅收录核对后的 JSON、JUnit、检查日志及截图；不分发原始测试数据库、JWT 密钥或浏览器会话 trace。

## 唯一剩余阶段：课堂演示与提交

- 在实际课堂电脑与投影上核对启动和显示，连续两次完成 3–5 分钟演示，记录设备、操作者、时长与问题。
- 课堂代码讲解按功能定位到组件、接口、服务和测试；不要求四人重新独立验收。
- 用户已说明真实姓名／GitHub 岗位映射、教师账号和提交方式仅在课堂提交时提供。仓库目前私有；已核对现有协作者为 Aestas16、YalRinshow、Delovue、Salty-JellY，不猜测姓名或岗位对应。当前账号具有 push 权限、没有 admin 权限；课堂提交时由仓库所有者按实际方式处理教师访问。

上述事项均属于课堂演示与提交阶段，不阻塞本次 `v1.0.0` 软件发布；也不声明课堂演示或教师访问已经完成。


## 收尾期间纳入的协作刷新与 CI 修复

PR #8 原有四项浏览器回归覆盖跨标签刷新、付款撤销后“去处理”、成员加载延迟与 503 恢复。其 ae0fbee 的 [Windows 检查](https://github.com/Delovue/hezhang/actions/runs/41279569608) 有一项失败：收款人拒绝付款后，付款人的新额度尚未加载，仍能打开登记窗口，合法金额被旧额度误判。角色丁通过 trace 与受控延迟测试复现，d1d0248 使两个付款入口在活动／成员／余额／建议加载完成且无错误时才开放；修复前回归失败，修复后协作与结算 8 项通过。此修复同步回原 PR #8，并纳入 e66c6c2 的首轮 345／66／24 项全量验收；PR #8 之后的 `f9f9729` 与审查修复由最终验收（345／66／27 项）覆盖。没有通过加长断言超时或自动重试掩盖问题。
