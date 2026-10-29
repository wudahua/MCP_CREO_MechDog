# Release 0.8.4 发布验收记录

日期：2026-10-29（Asia/Shanghai）。版本与条目：0.8.4 PATCH，[DEV-051](../work-items/DEV-051.md)、[BUG-032](../work-items/BUG-032.md)、[FEAT-014](../work-items/FEAT-014.md)、[BUG-046](../work-items/BUG-046.md)。公开工具 94 个，无新增工具。开发分支 `codex/dev051-feedback070`；本卡在发布前写入源码包，发布后的完整 ZIP SHA256 与远端对象核对放在 Release body 和最终交付报告，避免源码包自指。

## 环境、源码与命令

- 环境：Windows x64、PowerShell、Python 3.12；已发生的原生实测为本机 Creo 12.4.0.0 / 匹配 Toolkit SDK。0.8.4 发布阶段不连接 Creo、不使用 WorkBuddy。
- 实机受测源码：首壁准入修复 `42281aa`；钣金基体/贴边面诊断 `7eb2466`、`e5fe021`；后续库存截面重建已编译但尚无实机结果。各轮工作区 dirty 标志、执行器指纹及原始 job/model 以 [T03](../development/DEV051-T03-ACCEPTANCE.md)、[T11](../development/DEV051-T11-ACCEPTANCE.md) 的当轮记录为准；不能用本版发布提交冒充这些实机的受测源码。
- `.venv\Scripts\python.exe tools\dev_check.py`：exit 0，`success=true`、`unit_tests=passed`，**1353 tests / 0 失败 / 0 错误**，耗时 261.386 s；`checked_source_sha256=eb0bc73cec0e320d7a746ed7abd6f6605cd8fb445d70e637efcfdfb6622ead26`，运行时 `commit=cda3a11`、`dirty=true`，`native_validation=not_run`。存量风格摘要为 30 lint、16 个未格式化文件，不能宣称严格全库格式通过。
- 未修改的 `.venv\Scripts\python.exe tools\package_seeds.py` 三次构建均为 24 文件 / 9 seeds，ZIP SHA256 均为 `0d83805cd1a3c5fc2b8597d8246bd84eec6f374abc07214e1deb9d1cc92e3245`；前版 0.8.3 种子包 SHA256 为 `a5dfc704ba141a202222c765812fe9c0b2dc05abd0991807012838c08d8ecd61`。前两次一致，回填 `seeds.py expected_digest` 后第三次仍一致。
- `.venv\Scripts\python.exe tools\package.py` 从同一候选树重复构建源码包；两次均为 1042 文件、SHA256 一致，ZIP 完整性通过，禁入路径 0。源码包与种子包完整 SHA256 直接写入 Release body 和最终交付报告，避免本卡在源码包内自指。

## 原生修改、保存重载与失败边界

T03 五组首壁参数修复后实测体积分别为 **42 920、42 920、185、370、92.5 mm³**，误差 0，均 `saved_file_reloaded_and_verified=true`，`driving_face_id=60`、`driving_axis=1`；旧报告的 9 957 440 mm³ 在本机该矩阵被证伪。0.8.0—0.8.3 的准入把草图坐标系误计为几何，合法单线壁在那几版均被阻断；不能把本轮成功追记到旧版本。

旧折边夹具 `depth=1, thickness=232` 的板厚实际是 232 mm；修正为 `plane="XZ"`、`depth=232, thickness=1`。非壁面边由 `ProSmtedgeContourGet=-8` 在建树前拒绝。真正 1 mm 板上，前两道折边各 +18 560 mm³、rev 2/3、保存重载成功，`smt_contour=4`；但 bbox 仅在 X 方向各扩展 80 mm，Z 不变，属于平铺延伸，**折弯几何未通过**。第三道曾在原生创建路径挂起；四壁及 relief 未验。按库存截面重建后的新驱动仅离线就绪，尚未实机运行。

T04 普通件 add +400 mm³、钣金 cut −100 mm³ 已取得实机对照；钣金 add 仍 `-1`，修正 1 mm 基体后的隔离重跑未执行。T02 4/4、T06 9/9、T07 3/3、T08A 4/4 属 [0.8.3 原有证据](RELEASE-0.8.3.md)，本版不重标为新跑结果。

## 会话阻塞与未测范围

Windows 2026-10-29 19:51:03 记录 `xtop.exe` `AppHangB1`。后续重启几分钟内自行退出，只留 `pro_comm_msg`；服务只读探测为 `session_health.reason=session_identity_stale`、`connection_state=not_found_or_unreadable`，`creo_startup_status` disabled，`auto_start_creo=false`。本次发布不尝试重新挂接或连接 Creo。T05 四壁、T04 钣金 add 隔离、T08B/T09A/T09B/T12/T13 实机未执行；新折边截面也未实测。WorkBuddy 未执行，Creo 9 SDK 本机不可用、Creo 9 编译与建模未验，Creo 10 未独立复测。原始缺件案例及 BUG-085 断连根因仍开放。

## 发布状态与逐 ID 核对

候选状态：待发布执行者完成 dev_check、两包重复构建、种子摘要回填、源码白名单检查及远端发布。**正式交付结论以最终远端核对为准**。本卡不预填 main 提交、附注标签对象、Release URL 或四附件哈希。

| ID | 技术状态 | 交付版本与开放范围 | 当前入口 |
| --- | --- | --- | --- |
| DEV-051 | 首壁修复及本轮证据纳入；整体未收口 | 0.8.4；四壁及列明实机未测 | [工作卡](../work-items/DEV-051.md)、[主台账](../BACKLOG.md)、[版本说明](../RELEASE_NOTES_0.8.4.md)、[开发入口](../DEVELOPMENT.md) |
| BUG-032 | 本机 T03 五组首壁通过 | 0.8.4；外部环境及下游范围未外推 | [工作卡](../work-items/BUG-032.md)、[主台账](../BACKLOG.md)、[版本说明](../RELEASE_NOTES_0.8.4.md) |
| FEAT-014 | 两道折边创建，但几何平铺；新截面未实测 | 未收口；四壁、relief、真实折弯待验 | [工作卡](../work-items/FEAT-014.md)、[主台账](../BACKLOG.md)、[版本说明](../RELEASE_NOTES_0.8.4.md) |
| BUG-046 | 普通件 add 与钣金 cut 对照通过；钣金 add `-1` | 未收口；修正基体后隔离待验 | [工作卡](../work-items/BUG-046.md)、[主台账](../BACKLOG.md)、[版本说明](../RELEASE_NOTES_0.8.4.md) |

附注标签 `v0.8.4`、正式 Release 与四附件必须由最终 main 提交生成并逐件下载核对；完整 SHA256 直接列在 Release body。发布后不追加自指的 main 提交。
