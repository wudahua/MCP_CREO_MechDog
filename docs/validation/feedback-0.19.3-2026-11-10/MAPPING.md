# 0.19.3 反馈映射（2026-11-10）

关联：[manifest](manifest.json)（四份原件逐字节归档）· [统一台账](../../BACKLOG.md) · [分批计划](../../superpowers/plans/2026-11-10-feedback-0193.md)

四份原件对象均为 MCP_CREO_MechDog **0.19.3**（Creo Parametric 10.0.0.0，`release_numeric=42`），本仓当前基线为 **0.20.0**（提交 `074ea67`）。因此表内「本仓结论」区分三种：**0.20.0 已交付**、**本轮离线已修/已登记**、**仍开放**。报告方证据只作报告方证据，不外推为本机验收。

## 一、报告 A：拔模中性面解析与多会话选择及超时恢复缺陷

| 编号 | 报告现象 | 本仓结论 | 台账 ID | 批次 |
| --- | --- | --- | --- | --- |
| A-P1 | 能力文档 `references.creo_draft.neutral_plane` 示例是 `{kind:'datum_plane',axis:'z',offset:0}`；真实模型同高度多张面时被拒，改 `{kind:'plane',normal,offset}` 才成功；两种形式语义无说明 | **本轮已修（离线）**：示例改为几何平面形式，`syntax.plane_by_position` 说明两者差异；原生命名候选数与候选 ID | [BUG-116](../../work-items/BUG-116.md) | A |
| A-P2 | 多 Creo 会话 `-36 ambiguous`；`config.json` 运行中修改不生效，且无工具可枚举会话 ID，提示语按字面执行必然失败 | **本轮已改文案**：说明需关闭多余实例并 `retry=true`，或改配置后**重启服务**，并显式声明当前无法程序化选择。会话枚举、`session_id` 入参、热读仍开放 | [FEAT-001](../../work-items/FEAT-001.md) | A（文案）/ C（能力） |
| A-P3 | 378 特征模型 28 op 批次 25 分钟后 `unknown_outcome`，几何实际成功；`native_progress` 全程 `no_phase_lines`；超时预算与模型规模无关；reconcile 缺「疑似已完成」捷径 | 进度**已随 0.20.0 交付**（B3/F06）；**B 批交付受控预算**：`execute_plan(timeout_seconds)` 60—7200、默认不变，`timeout_seconds`/`timeout_source` 进 request/job，runner 与看门狗同用冻结值；自动放大公式与 reconcile「疑似已完成」捷径仍**未实现** | [DEV-081](../../work-items/DEV-081.md)（B3 已交付）+ [FEAT-033](../../work-items/FEAT-033.md)（预算，部分交付）+ [FEAT-018](../../work-items/FEAT-018.md)（恢复捷径） | B / C |
| A-P4 | `feature_state delete` 级联依赖是 MCP 自动创建的 `no_name` 基准面，首次必然失败；`targets` 用对象形式时报错暴露内部校验器名、不说明合法形态 | **本轮已修（离线）**：对象形式改为单条可读拒绝并给合法示例；依赖列表追加「把上面 feature_id 加进 targets 重提」。自动基准面合并开关未实现 | [BUG-117](../../work-items/BUG-117.md) | A / C |
| A-P5 | 原生失败不指名是 `surfaces[]` 还是 `neutral_plane` 解析失败 | **本轮已修（离线）**：`failed_reference field=... value=... detail=...`；平面解析失败带候选数/ID/推荐形式 | [BUG-116](../../work-items/BUG-116.md) | A |
| A-历史 P10 | `ExtrudeOp` 仍无 `draft_angle`/`top_scale` | 未实现（B6 未启动） | [DEV-081](../../work-items/DEV-081.md) | C |
| A-历史 P9 | 预览仍为线框+全部基准叠加 | 未实现（B5 未启动） | [DEV-081](../../work-items/DEV-081.md) | C |

## 二、报告 B：曲面链验收通过但 Creo 10 兼容性与链式引用缺陷

| 编号 | 报告现象 | 本仓结论 | 台账 ID | 批次 |
| --- | --- | --- | --- | --- |
| B-P12 | `surface_loft` 在 Creo 10 构建被编译剔除（缺 `Probbl.h`），提交前拒绝；建议给「Creo 版本 → 可用性」顶层速查 | 降级回执本身合格；**跨文件符号依赖**已在本轮按 DEV-082 门控修复；`Probbl.h` 等价元素树（H01 正解）与顶层速查未做 | [DEV-080](../../work-items/DEV-080.md)、[DEV-082](../../work-items/DEV-082.md)、[FEAT-009](../../work-items/FEAT-009.md) | A（门控）/ C（等价树） |
| B-P13 | `quilt_merge` 结果 quilt 不能被下一次 merge/solidify 引用（`ProFeatureGeomitemVisit -4`）；workaround 是恒引用首次 merge 的原始 target label | 原生根因未定；Python 已有同计划 trim→thicken 准入先例，merge 链的文档说明与别名解析未做 | [BUG-115](../../work-items/BUG-115.md)、[FEAT-039](../../work-items/FEAT-039.md) | B / C |
| B-P14 | `project_curve` 在 Creo 10 `ProFeatureWithoptionsCreate -1`；建议附带分支检测提示并在 `known_limitations` 点名 Creo 10 差异 | 未定因；既有拒绝文案质量已获报告方肯定 | [FEAT-039](../../work-items/FEAT-039.md) | C |
| B-P15 | 共面相邻 fill 的 `merge` 偶发 `-1`（干净上下文成功） | 复现率低，作观察项；建议输出 merge 前边界接触判定 | [FEAT-039](../../work-items/FEAT-039.md) | C |
| B-旧 P2 | 2.78e-08 mm 间隙在 Creo 10 内核不焊接，拉伸 `status=6` | API 层已降级为风险标志，内核层限制仍在 | [BUG-101](../../work-items/BUG-101.md)、[BUG-049](../../work-items/BUG-049.md) | 保持开放 |
| B-旧 P1 | Blend callback 需手工 GUI 注册，实体放样无人值守不可用 | 0.20.0 已交付 B1 seed 兼容性预检与无 callback 路线说明 | [DEV-081](../../work-items/DEV-081.md) | 已交付（有限） |

## 三、报告 C：球鼻艏导线曲面放样缺失

| 编号 | 报告现象 | 本仓结论 | 台账 ID | 批次 |
| --- | --- | --- | --- | --- |
| C-缺失1 | 无「≥3 截面 + 纵向导线」boundary blend；`surface_loft` 仅 2 截面、无导线、straight 插值，且 Creo 10 被剔除 | **多截面已交付并实机验收**（2026-11-11，Creo 12.4）：2—32 截面，两截面直纹、3 截面以上单张光滑面（40/60/40 mm 实测 2101.25 mm²，非分段直纹的 2000.00）；保存重载、thicken 体积一致。**纵向导线仍未实现** | [FEAT-065](../../work-items/FEAT-065.md)、[FEAT-009](../../work-items/FEAT-009.md) | B（多截面）/ C（导线） |
| C-缺失2 | `loft`/`surface_loft` 只支持 XY 截面按 Z 排列，球鼻艏截面在 YZ 按 X 排列 | 未实现；多截面本身已通，坐标系/截面方向改造与端点收敛仍归 FEAT-065 M2 | [FEAT-009](../../work-items/FEAT-009.md)、[FEAT-065](../../work-items/FEAT-065.md) | C |
| C-缺失3 | quilt_merge 链式引用 | 同 B-P13 | [BUG-115](../../work-items/BUG-115.md) | B / C |
| C-缺失4 | `cut` 无作用域（前次 P8）、Split Line 类投影分割 | `cut` 作用域已随 0.20.0 B4/F08 交付（`scope` + `scope_applied`）；`project_curve` 同上 | [DEV-081](../../work-items/DEV-081.md)、[FEAT-039](../../work-items/FEAT-039.md) | 已交付 / C |
| C-正面 | `extrude mode="surface"` 支持 ellipse 截面；`solver` 走 `unsupported_coordinate_entity → autodim` 恢复成功；分段柱面可原坐标复现；10 特征+10 自动基准面清理后体积精确恢复 | 正面证据，不建卡；同时再次复现 A-P4（级联 no_name 基准面） | — | — |

## 四、报告 D：0.19.3 升级核验（Creo 10 / Windows x64）

| 编号 | 报告现象 | 本仓结论 | 台账 ID | 批次 |
| --- | --- | --- | --- | --- |
| D-P1-1 | `C1083` 已修，但 `native/surface_boundary_fill.cpp` 无 `MECHDOG_HAS_PROBBL_HEADER` 门控却复用 `surface_loft.cpp` 内被门控的 `SURFACE_LOFT_TREE_SAMPLE_LIMIT` / `loft_element_json` / `PRO_E_DTM_SRF_TYPE_BND_BLEND`，整包编译 4×`C2065`+1×`C3861` | **本轮已修（离线）**：该 TU 主体按同一宏门控，缺头分支给 `SURFACE_BOUNDARY_FILL_SDK_UNAVAILABLE` stub；`-DMECHDOG_HAS_PROBBL_HEADER=0` 聚合 TU 语法检查 `EXIT=0`（仅存量 C4819）。抽 `element_tree_json.h` 的正解仍开放 | [DEV-082](../../work-items/DEV-082.md)、[DEV-080](../../work-items/DEV-080.md) H01 | A（门控）/ C（抽头） |
| D-P1-2 | 新增头门控契约测试只查 `#include` 行与单个隔离 TU，不覆盖聚合编译，无法拦截 P1-1 | **本轮已补**：`tests/unit/test_native_aggregate_compile.py` 静态检查跨 TU 符号可见性；已验证「去掉门控即报错」 | [DEV-082](../../work-items/DEV-082.md) | A |
| D-P2-3 | `RELEASE-POSTCHECK` 的 `## v0.19.3` 段晚于发版落地，tag 与分发包内无该段 | v0.19.3 段已在 `main`；**本轮补 `## v0.20.0` 段**（同一问题族在当前版重现） | [DEV-083](../../work-items/DEV-083.md) | A |
| D-P3-4 | 版本说明/发布记录中「保留发布前占位」「见本文件发布后回填段」与实际内容不符 | **本轮已改**：`RELEASE-0.20.0.md` 首段与 `RELEASE_NOTES_0.20.0.md` 两处措辞改为发布前快照 + 指向 POSTCHECK `## v0.20.0` | [DEV-083](../../work-items/DEV-083.md) | A |
| D-正面 | 四附件四方一致、sidecar ASCII+LF、`--tag` exit 0、回调八项指纹 SAME、包一致性 1694/1695、版本入口四处同步、台账计数一致、108 装饰器/107 公开工具 | 不建卡；报告方「未改 native/*.cpp」声明经其复核属实 | — | — |

## 五、本轮离线证据与未测范围

**已执行**

- 归档四份原件（`originals/`，逐字节；`manifest.json` 记字节数与 SHA256）。
- 代码/文档离线修改：`references.py`（draft 示例与语法说明）、`schema.py`（targets 形态拒绝）、`feature_state.py` 与 `native/feature_state.cpp`（依赖列表重提提示）、`creo_startup.py`（`-36` 文案）、`native/advanced.cpp`（`failed_reference` 与 `pull_direction` null 默认）、`native/generic.cpp`（平面候选数/ID/推荐形式）、`native/surface_boundary_fill.cpp`（缺头门控与 stub）、`docs/REFERENCE_SYNTAX.md`。
- 新增测试：`tests/unit/test_feedback_0193_contract.py`（10 项）、`tests/unit/test_native_aggregate_compile.py`（4 项）；`tools/dev_check.py --work-item DEV-082` → `success=true`、`unit_tests=passed`、`Ran 3277 tests`、无新增语言回归。
- 原生编译：`bridge.py build` 成功（Creo 12.4.0.0 SDK）；`-DMECHDOG_HAS_PROBBL_HEADER=0` 的 `worker.cpp` 语法检查 `EXIT=0`，`error C`/`LNK` 均为 0，仅存量 `C4819`。
- 发布记录：`docs/development/RELEASE-POSTCHECK-2026-11-07.md` 增 `## v0.20.0` 段；`RELEASE-0.20.0.md` 与 `RELEASE_NOTES_0.20.0.md` 措辞更正。

**2026-11-11 实机（仅覆盖 FEAT-065 M1，用户当次确认后执行）**

- `surface_loft` 三截面 40/60/40 mm（间距 20 mm，`interpolation="smooth"`）：`job bd976c4c…`、模型 `f16d2075…`、revision 1、`saved_file_reloaded_and_verified=true`、单张开放 quilt、面积 2101.2524427513217 mm²、重载后 id/面积一致；thicken 2 mm（`job f40d0a73…`，revision 2）体积 4202.507981502071 mm³ = 面积×2；两截面回归（`job 7c6c80a4…`）800.0 mm²。
- 该实测推翻了「多截面等于分段直纹」的假设，契约已按实测修正（3 截面以上必须 `smooth`）。
- 报告：[20261111-104718.json](../../../build/surface_loft_multisection/20261111-104718.json)（本机 build 目录，不入库）。

**未验证（不得据本轮结论外推）**

- 本批其余改动（`failed_reference` 文案、`-36` 恢复路径、draft 中性面新示例、`timeout_seconds` 长作业、`completion_review`、`quilt_merge`/`project_curve` 诊断）**均未做实机**：本轮实机只跑了 surface_loft 三截面/两截面与 thicken。
- 真实 Creo 10.0.0.0 SDK 整包编译：本机无该 SDK；`-DMECHDOG_HAS_PROBBL_HEADER=0` 只模拟缺头分支，不等于 Creo 10 SDK 全部头文件齐备。
- 会话枚举工具、`session_id` 入参、配置热读：未实现。
- `feature_state` 自动基准面合并开关：未实现。
- 多截面+导线 boundary blend、`Probbl.h` 等价元素树、`quilt_merge` 链式引用根因、`project_curve -1`：未实现/未定因。
- WorkBuddy 黑盒：本轮未执行。
