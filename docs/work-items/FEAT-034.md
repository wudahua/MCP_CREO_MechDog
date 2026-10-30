# FEAT-034：草图弧方向、扫角与实际几何回显

日期：2026-10-17；当前核对：2026-10-30。类型：功能。优先级：P1。状态：已随 0.8.0 交付实现；**2026-10-29 实机几何验收通过**（4/4，误差 ≤5.6e-9 mm³，显式 `dir=-1` 确认反转主弧，回显为原生动量）；**2026-10-30 编辑/下游/保存重载/非法编辑的判定与覆盖已离线交付，实机未验**。目标版本：0.8.0；剩余与 WorkBuddy 验收继续开放。

当前实现与真实检查结果见 [DEV051-T02-ACCEPTANCE](../development/DEV051-T02-ACCEPTANCE.md)，提交 `a3c1f4b`；后续按 [0.7.2 续版计划 T02](../development/0.7.2-FEEDBACK-PLAN-2026-10-28.md)补真实集成实机入口。29项专项和构建通过不代表原生闭环；T02较早的1项安装沙箱网络错误保留为历史，[T03验收卡](../development/DEV051-T03-ACCEPTANCE.md)已提供后续全量检查通过记录，按各自指纹解释。已随 0.8.0 交付离线实现，但不能据此宣布原生验收通过。下文保留最初登记时的目标与证据，已定契约以T02验收卡为准。

来源：[0.3.3 反馈补录](../validation/FEEDBACK-0.3.3-2026-10-17.md)报告 B 第 4 节；关联 FEAT-008、BUG-050/051。

## 目标与范围

报告在 Creo 10 / MCP 0.3.3 对 R10、弧加弦封闭截面拉伸 5 mm：角度 0→90 得 `142.699081698 mm³`，90→0 得 `1428.097245102 mm³`，均成功。报告称现有 start/end 按逆时针归一化；两个输入对应不同扫角，不能据体积约差 10 倍认定数值计算错误。合法大于 180° 的弧继续允许。

评估显式 `dir` 或 `sweep_deg`，先确定字段、正负/跨零/整圆及互斥规则；保留旧 start/end 请求的明确兼容语义。回显实际起止点、方向、扫角及其坐标系；可选提供大弧提示，不能把 >180° 一律当错。统一草图创建、计划及几何更新入口，不以端点四舍五入掩盖闭合/精度问题。

## 验收标准

| 环境 / 用例 | 可判断的预期结果 |
| --- | --- |
| Windows / schema 与回归 | 旧角度请求语义稳定；新字段和冲突/零扫角/超范围输入有明确契约；运行统一开发检查 |
| 本机 Creo 12.4 / 匹配 SDK | 顺/逆时针、小弧/大弧、跨 0°、半圆及明确支持的整圆分别核对端点、切向、扫角；弧加弦截面体积符合所选扇段解析值 |
| 编辑与持久化 | 修改方向/扫角后几何、下游特征、revision 及保存重载正确；非法输入保留检查点；提示不拒绝合法大弧 |
| WorkBuddy | 仅 MCP 输入与几何/参数回读验收；报告实际扫角、体积、job/model、保存重载及原始错误 |

## 实现与证据

本次仅登记能力建议，未选择接口或改变原生弧方向。外部 0.3.3 对照不代表当前 0.3.4 已复测；来源原件与摘要见补录。实机执行须先满足当前会话安全约束。

## 2026-10-30：T02 弧方向编辑与保存重载补验——离线阶段（实机未验）

分支 `codex/dev051-feedback070`，提交 `3851963`。基线 `641edb3`。本节只改驱动与单元（`tools/test_arc_direction_live.py`、新增 `tests/unit/test_arc_direction_live.py`），**未改生产代码**、未连 MCP/Toolkit、未启动 Creo、未改版本、未合 main、未 push、未发布。

- **修掉两个判定缺陷**：①驱动「只看体积即可 passed」；②「从 terminal 顶层取 `saved_file_reloaded_and_verified`」——该字段实际只在 `result` 块，顶层永远为 null。改为要求 job succeeded ∧ 实测体积对上独立 oracle ∧ `arc_geometry` 原生回显 ∧ `result.saved_file_reloaded_and_verified is True`，缺任一项即 `passed=false`；回归 `test_missing_native_arc_echo_cannot_pass`、`test_missing_reload_evidence_cannot_pass`、`test_volume_only_evidence_cannot_pass`、`test_top_level_reload_flag_is_not_evidence`。
- **补覆盖**：方向编辑（就地切 dir、跨零、XZ 倾斜帧）、下游特征跟随（体积变为 to_dir oracle 且 revision 恰好 +1、feature_id 不变）、非法编辑（模型体积与 revision 不变、须有回滚证据，随后合法回切并保存重载）、保存重载后方向与几何仍正确。旧四例数值以回归钉死，未放宽。
- **离线证据**：145 项定向单测 OK、离线驱动 exit 0、ruff 通过。
- **仍未测（本节零 MCP/Toolkit/Creo 调用）**：真实 `arc_geometry` 原生回显、方向编辑后的下游再生体积、revision 递增语义、保存重载、非法编辑的原生拒绝/回滚字段形态、busy/单通道（须真实并行调用才可报告）、WorkBuddy、Creo 9/10。
- 实机入口：`.\.venv\Scripts\python.exe tools\test_arc_direction_live.py --live --confirm-session-usable`（唯一 dev 服务 `MCP_CREO_MechDog_dev`，先满足 BUG-001 会话条件）。

详见 [T02 验收卡](../development/DEV051-T02-ACCEPTANCE.md) 2026-10-30 节。本条保持开放（编辑/下游/重载/非法编辑实机未验）。
