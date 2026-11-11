# MCP_CREO_MechDog 0.21.0

日期：2026-11-11。类型：MINOR。公开工具：107（与 0.20.0 相同，新增能力是工具参数与回执字段，不是新工具）。源码版本以 [version.py](../version.py) 为准。

## 概览

0.21.0 交付 [FEAT-065](work-items/FEAT-065.md) 的 M2：`surface_loft` 增加**第二方向**（`PRO_E_BNBLN_2DIR`）导线支持，并一并入库 0.20.0 之后工作区里积压的 0.19.3 反馈批修复与工程整理（[DEV-081](work-items/DEV-081.md)）。

`surface_loft` 新增公开参数 `guides`，属新增功能，按约定递增 MINOR。原有调用与省略 `guides` 的行为不变。

## 本版变化

### FEAT-065/M2 曲面放样第二方向（新增公开参数）

- `surface_loft` 新增可选 `guides`：2—8 个草图，每个草图恰好一条非复合曲线，作为第二方向与截面一起决定曲面。第二方向与第一方向（`PRO_E_BNBLN_1DIR`）并列挂在 `PRO_E_BNBLN_CURVES` 下，结构同构：`PRO_E_BNBLN_2DIR` → `PRO_E_BNBLN_DIR_CURVES` → 每导线一个 `PRO_E_STD_CHAIN_HOLDER`。
- 提交前拒绝（无作业产生）：少于 2 条导线、重复导线、导线与截面复用同一草图、单草图非单曲线。少于 2 条不是保守限制：实测单条 2DIR 曲线能创建特征但永不再生。
- 导线是否真正穿过每个截面由内核判定，Python 与原生都不猜；不穿过则再生失败并把回执写进结果，不会静默忽略。
- 回执新增 `guides`、`guide_count`、`guide_curve_ids`；compact 投影同步。曲面仍是单张开放 quilt（`quilt_closed_native`），不产生实体。
- 能力文案（`creo_capabilities` 的 `surface_loft`/`surface_chain`/`loft` 限制）、[REFERENCE_SYNTAX](REFERENCE_SYNTAX.md)、[COMPATIBILITY](COMPATIBILITY.md) 与 [G5 原生契约](development/G5-NATIVE-CONTRACT.md) §2.1 同步更新；原「导线不发布」表述改为「2—8 条导线、单导线不发布」。

### DEV-081 入库的既有工作（0.20.0 之后积压）

- [BUG-115](work-items/BUG-115.md)/[BUG-116](work-items/BUG-116.md)/[BUG-117](work-items/BUG-117.md)：0.19.3 反馈批的曲面链与引用问题（trim/merge 标签复用、draft 中性面按几何位置解析、原生聚合编译校验）。
- [DEV-082](work-items/DEV-082.md)/[DEV-083](work-items/DEV-083.md)：SDK 头条件与原生编译工程整理。
- [FEAT-039](work-items/FEAT-039.md)：曲面链收尾（advanced/project_curve/quilt_merge/quilt_query/surface_boundary_fill 与 generic 分发）。
- [FEAT-033](work-items/FEAT-033.md)：`execute_plan` 的 `timeout_seconds` 预算。
- [FEAT-018](work-items/FEAT-018.md)：作业完成度复核（`completion_review`、`recovery.py`、`feature_state`）。
- 这些条目的验收范围以其工作条目文档为准；本版本不新增它们之外的结论。

## 验证

环境：Windows x64 / Python 3.12.14 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK / 本机许可。实机执行经用户 2026-11-11 当次明确确认；未结束或重启 Creo/nmsd、未清 `toolkit.lock` 或 unknown 保护、未做故障注入、未改用户模型与历史证据。

- FEAT-065/M2 驱动 `tools\test_surface_loft_guides.py --live --confirm-session-usable`（报告 `build/surface_loft_guides/20261111-120758.json`）：离线 10 项 + 实机 17 项全 PASS。
  - 直导线基线 job `900fa9b3092541e681deeae0e2bf9ba6`（模型 `4b4b19c5…`，revision 1）：面积 800.0 mm²、包围盒 x 止 40.0 mm、`guide_count=2`、单张开放 quilt、无实体、`saved_file_reloaded_and_verified=true`。
  - 曲线导线 job `4d0f3e10b1f54c14b794f3ecd7e8760a`（模型 `332b574d…`，revision 1）：面积 600.0 mm²、包围盒 x 达 44.24 mm（截面止于 40 mm，圆弧导线外鼓 4.142 mm）、单张开放 quilt、无实体、保存重载后面积一致。
  - 单导线计划在提交前被拒绝，未产生作业。
  - 3 截面 + 2 直导线 job `2fd4ab48c67e402ab4e8d0f5fa826091`：面积 1600.0 mm²（40×40），这一步由一次性探针取得；驱动中新增的同几何用例在 2026-11-11 12:37 之后因 Toolkit 未确认就绪未能复跑，见下方限制。
- 元素树实验（同日）：单条 2DIR 曲线不再生；导线端点与截面相切时不再生，切线 45° 相交时成功；抽取树保留 `PRO_E_BNBLN_2DIR` 且内核补齐 `PRO_E_BBL_ADD_CLOSED`。
- 全量单元测试：`Ran 3314 tests ... OK`（工作树）。
- 种子包按确定性流程构建三次（含回填后重建），SHA256 均为 `da2a2936afdc5c1afbc1c7ffd5c9d70390020ec41f3cdb2f086d2151259a0f46`，已回填 `docs/seed_package.json`。
- 源码包与种子包各自生成 `.zip.sha256` sidecar；提交号、受测源码指纹与两个包的 SHA256 见 Release 正文与[发布记录](validation/RELEASE-0.21.0.md)。源码包的摘要在打包后写入 Release 正文，本文件不再重复固定值（本文件本身在包内）。

## 未测范围与已知限制

- 曲线导线得到的曲面**形状未在 GUI 或等价可视化中核对**：本版只声明可测数值（面积、包围盒、开放状态、保存重载），不声明形状符合 Creo 交互式「双方向边界混合」的预期；600.0 mm² 与直纹基线 800.0 mm² 的差异也没有几何解释。
- 3 截面 + 导线的驱动用例未在发布前复跑（Toolkit 未确认就绪），证据来自同日一次性探针的同一几何。
- `PRO_E_BNBLN_ADV_VIA_CRV`、`PRO_E_CTRL_PTS`/`PRO_E_BLEND_TYPE`、G1/G2 连续性、端点收敛、任意正交平面截面、导线草图内含 2 条曲线（闭合轮廓）均未测。
- Creo 9/10 无 SDK，未编译、未建模；本版实机结论仅覆盖 Creo 12.4.0.0。
- WorkBuddy 黑盒验收未执行；开发者实机证据不替代黑盒验收。
