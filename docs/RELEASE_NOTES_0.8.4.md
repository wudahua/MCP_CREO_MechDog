# MCP_CREO_MechDog 0.8.4

0.8.4 是 [DEV-051](work-items/DEV-051.md) 的 PATCH：修复 0.8.0—0.8.3 的钣金第一壁建造阻断，补充钣金基体与折边贴边面准入的诊断及已取得的本机实机证据。公开工具仍为 **94** 个，没有新增工具。升级请使用与 0.8.4 匹配的种子包；已发布的 0.8.0—0.8.3 提交、标签和附件保持原样。

## 修复与实测

- **第一壁准入阻断已修复。** 0.8.0—0.8.3 把草图必写的坐标系实体误计为几何，合法单线壁也报 `2 drawing entities (1 straight lines)`，因此当时的钣金壁均建不出来。修复提交 `42281aa` 后重新编译，本机 Windows x64 / Creo 12.4.0.0 的 T03 五组参数全部通过：体积依次为 **42 920、42 920、185、370、92.5 mm³**，误差均为 0，均保存重载核验；回显 `driving_face_id=60`、`driving_axis=1`。旧报告的 **9 957 440 mm³** 在这组实测中被证伪。详见 [BUG-032](work-items/BUG-032.md) 与 [T03 验收](development/DEV051-T03-ACCEPTANCE.md)。
- **厘清板厚与边的归属。** 旧“185×232×1 底板”夹具传入 `sheetmetal_wall(depth=1, thickness=232)`，虽然体积与包围盒看似正确，钣金板厚实际上是 **232 mm**。夹具现使用 `plane="XZ"`、`depth=232`、`thickness=1`。折边入口增加 `ProSmtedgeContourGet` 检查：所选边不在钣金壁面轮廓时，于建树前拒绝并保留原码 `-8`。相关提交 `7eb2466`、`e5fe021`；详见 [T11 验收](development/DEV051-T11-ACCEPTANCE.md)。
- **已确认的其他实机结果。** T02 弧方向 4/4、T06 新件倾斜草图 9/9、T07 多环替代夹具 3/3、T08A 预览文件写出 4/4 已在 0.8.3 记录。本轮 T04 普通件 add 净增 **400 mm³**、钣金 cut 净减 **100 mm³** 通过；这两项不能证明钣金 add 可用。

## 仍未解决与未执行

在修正为真正 1 mm 板后，前两道折边特征成功创建：每道体积增加 **18 560 mm³**、revision 依次为 2/3，均保存重载核验，`smt_contour=4`。但包围盒只在 X 方向增长 80 mm，Z 范围未变，几何是**平铺延伸，尚未成弯**；体积正确不能替代折弯判定。随后已按 Creo 库存 `flange_shapes` 截面重建并增加只看包围盒方向的 `tools/test_flange_direction.py`，**新截面尚未实机运行**。第三道折边曾挂起，四壁 T05 尚未完成。T04 钣金 add 仍返回 `-1`，原因未定。

2026-10-29 19:51:03，Windows 记录 `xtop.exe` 的 `AppHangB1`。之后 Creo 重启虽能启动，却在几分钟内自行退出，只留下 `pro_comm_msg`；服务只读探测报告 `session_health.reason=session_identity_stale`、`connection_state=not_found_or_unreadable`，`creo_startup_status` 为 disabled（`auto_start_creo=false`）。当前会话无法重新挂接，本次发布不再连接 Creo。因此 **T05 四壁、T04 钣金 add 隔离、T08B/T09A/T09B/T12/T13 实机均未执行**，不能记为通过。WorkBuddy 未执行；Creo 9 SDK 本机不可用，Creo 9 编译与建模未验，Creo 10 未独立复测。

离线检查、受测源码身份、种子包和源码包核对见 [0.8.4 发布记录](validation/RELEASE-0.8.4.md)。
