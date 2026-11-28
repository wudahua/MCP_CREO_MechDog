# 0.48.3 反馈：DEV-108 同刻度重试单测固定 2 秒 `join`，并发负载下仍随机失败

- 日期：2026-11-28
- 验证对象：`wudahua/MCP_CREO_MechDog` v0.48.3（Release id `460639975`，node_id `RE_kwDOU_ueTM4bY6b0`，published `2026-11-27T13:31:56Z`；0.47.1→0.48.3 含三个中间正式版 0.48.0/0.48.1/0.48.2，逐版核对，未跳版）
- 本地环境：Windows / Creo 10.0.0.0 ProToolkit SDK / WorkBuddy MCP 客户端 / Python `.venv`
- 验证性质：原始 JSON 定版、四附件四方哈希、逐版差异链、覆盖升级与零补丁编译、注册指纹、静态台账、门禁对照/篡改/反向闸门/发布后回填门禁、fourref、官方干净源码树多轮采样与因果探针
- 实机边界：本轮**未**连接 Toolkit、**未**启动或关闭 Creo、**未**做故障注入；Release 正文中的 Creo 10 实机结论为作者自述，本轮不复核运行期行为。

## 1. 结论摘要

0.48.3 的交付数据、编译、发布后回填和静态门禁全部通过；**上一轮反馈的 P1（发布后 POSTCHECK 实证未回填）已被作者完整闭环**（DEV-105 归档原件、补写实证、新增 `--post-release` 门禁）。但发现一个新的**测试时序问题**：

| 编号 | 问题 | 证据 | 判定 |
| --- | --- | --- | --- |
| P1（测试时序缺陷） | `tests/unit/test_startup_retry.py::StartupRetry::test_new_retry_gets_new_id_even_within_same_clock_tick` 仍以固定 `Thread.join(2)` + `assertFalse(thread.is_alive())` 等待异步协调线程；并发负载下偶发失败（`True is not false`、偶发 `3 != 2`） | 官方 0.48.3 干净树：隔离 2×120 次全过；并发负载 3×120 次为 8/120、1/120、0/120 失败（合计 9/360）；把测试内 9 处 `join(2)` 放宽为 `join(30)`、生产代码不变后，在同样负载下 120/120 全过 | **同族残留：测试固定 deadline，非产品运行期缺陷** |

这与 BUG-170 / BUG-175 的问题族一致：修复了 `retry_id` 同刻度重复的**产品逻辑**，但回归测试本身仍用固定墙钟等待线程结束。CI 并发或本机负载下会产生随机失败，阻断交付；作者 0.48.2 Release 正文已记录主干 CI 两次因同一启动重试 ID 断言失败，0.48.3 的修复未在测试时序层面完成。

## 2. 上一轮反馈闭环（先说清楚，避免被误读为未修）

- 0.48.0 的 `DEV-105` 工作卡首行明确引用本轮反馈归档：`docs/validation/feedback-0.47.0-0.47.1-2026-11-26/originals/v0471-postcheck-backfill-missing.md`，`SOURCE_MANIFEST.json` 中记录了用户反馈文档原文件名与 SHA256，原件逐字节归档。
- `src/creo_mechdog/release_integrity.py` 新增 `validate_post_release_backfill()`，`tools/check_release_records.py` 新增 `--post-release`；检查 snapshot `remote_verification == "verified"` 与 POSTCHECK 中 `### v<版本> 发布后核对` 段（Release 数字 id、`退出码 0`/`exit 0`、40 位提交哈希、四附件名与两个 ZIP SHA256）。
- 0.47.0/0.47.1 已真实回填：本地源码树两个 snapshot 均 `verified`，`--version 0.47.0/0.47.1 --post-release` 均退出 0。
- 0.48.0→0.48.3 每版都有发布后 backfill（发布后 107s / 88s / 196s / 1140s），`main` 为 0.48.3 回填提交 `f2827a86…`；0.48.3 frozen 包 snapshot 为 `pending`（设计），main 上 `verified`（回填完成），fourref 显示 tag/发布提交仅打包时点措辞，backfill/main 含 Release id、退出码 0、提交哈希与四附件摘要表。

## 3. 数据层正项

### 3.1 定版与四附件

- 重新用 GitHub API 原始 JSON 定版：v0.48.3 为最新正式版；另有一个 prerelease `archive-validation-2026-11`（冷数据归档，非本次正式版对象）。
- 四个版本每版四附件（source.zip / seed-library.zip / 两份 `.zip.sha256`）均通过本地实算、sidecar、GitHub asset `digest`、Release body 四方校验，`FOUR_WAY_OK=True`、`body_hash_mismatch=[]`、sidecar ASCII+LF。0.48.3 body 同时列出两个 ZIP 的完整 SHA256。
- 0.48.3 source.zip `11,409,955 B / 85aecbee968a60a7b98ae786676a72d295e193f741fcb93209dad381e44ed23a`，seed `493,442 B / 2f392cb45dcadae72bfc3a62b63ff1cadbff42a66680f05a304ed58f2fa61b4e`。
- 发布链：tag 对象 `286379ef…` → 发布提交 `718b477f…`（1 文件，发布前 1077s）→ 回填 `f2827a86…`（发布后 1140s）= main。四版 `previous_release_commit` 均指向上一版真实发布提交。

### 3.2 编译、包一致性与注册

- 官方原包零补丁编译：`BUILD_EXIT=0`，`error C` / `error LNK` / C1083 / C2065 / C3861 / C2039 / C4819 / `fatal error` / `Traceback` 全 0。
- worker `12,094,464 B / 725dc07d6574651fdeaaae1f87113bce91685c2706704a162cd8b9942447a8d2`（0.47.1 为 `7ad76c08…`，变自 0.48.0 的 `native/solid_bounds.h`）；loader/callback 指纹 `23f540b7…`/`02eac3e0…` 稳定。
- 包一致性 `2515/2515`，`real_diff=[]`、`eol_only=[]`、`missing=[]`；注册内部一致性 10/10。
- 差异链 2500→2497→2501→2505→2515（REAL 21/175/11/20）。0.48.1 的 175 个 REAL 变化主要是 DEV-106 活跃文档链接与台账整理；0.48.0 移除 13 个冷文件（作者 0.48.0 前以 prerelease 归档，见 `COLD_DATA_INVENTORY.md`），属设计。

### 3.3 静态核对与门禁

- 工具数 112（`@mcp.tool` 113 − `remove_tool` 1），与 `creo_capabilities.tool_count=112` 一致；BACKLOG `exit 0`：276 项（BUG 143 / FEAT 89 / DEV 44），九组状态标题实际行数与声明一致，0 重复 ID。
- DEV-104 起 `docs/DEVELOPMENT.md` 写「当前版本以 version.py 为准」，其他版本入口均为 0.48.3；seed_package/seed_manifest 一致。
- `release_integrity.py` 0.48.0–0.48.3 逐字节同（76,244 B / `b36abf89…`），在 0.47.x 的 72,884 B 基础上新增发布后回填门禁；旧路径 fallback 与 BUG-144 单测证据仍在。BUG-175 测试文件自 0.46.1 起逐字节同 `7039d135…`，统一假时钟在、无真实 `monotonic()+N` deadline。
- 官方门禁：assets+body `exit 0`；本机 records 无 unit evidence `exit 1`（BUG-137/144 正确行为）。
- 记录门禁 21 类负例除 G3 snapshot 删除 0（设计可选）外全部非 0、合法夹具 0；source-zip 6 类篡改全部 `exit 1`、correct/untouched `exit 0`；反向资产闸门 1/1/0。
- 发布后回填门禁：main-like 正例 0；snapshot pending/删除、发布后小节缺失、Release id 缺失、退出码非 0、40 位哈希缺失、四附件名缺失、64-hex 摘要全删共 8 类负例全部 `exit 1`；CLI `--post-release` 正例 0。
- 单测：官方干净树 `test_release_integrity` 55 tests OK、宿主保护 30 tests OK；本机核心子集 37 模块 554 tests OK（排除受本地残留文档污染的 `test_doc_links`，见第 5 节）；BUG-175 干净树两轮独立 60 次均 60/60。官方 v0.48.3 git 检出 `test_doc_links` 8 tests OK，`tools/check_doc_links.py` 扫描 308 份活跃文档、3132 处链接，0 断链 0 坏锚点。本机全量单测未跑，不宣称通过。

## 4. P1 详细证据：DEV-108 固定 2 秒 `join` 的残留 flaky

### 4.1 失败现象

在官方 0.48.3 source.zip 解压的干净树中，反复运行新增回归用例：

```python
# tests/unit/test_startup_retry.py
controller.start(retry=True)
first_thread = controller._thread
first_thread.join(2)                 # 固定 2 秒墙钟等待
self.assertFalse(first_thread.is_alive())
...
controller._thread.join(2)
self.assertFalse(controller._thread.is_alive())
self.assertEqual(self.fixture.probe.call_count, 2)
```

失败行集中在 `assertFalse(thread.is_alive())`（`AssertionError: True is not false`），偶发在 `assertEqual(probe.call_count, 2)`（`3 != 2`）。这些是测试对线程完成时限的断言，不是产品 API 返回错误。

### 4.2 采样统计

| 场景 | 采样 | 结果 |
| --- | --- | --- |
| 干净树、隔离运行（无并发负载） | 2 轮 × 120 次（两方法各 60） | 120/120 + 120/120，失败 0 |
| 干净树、与 BUG-175 采样进程并发 | 3 轮 × 120 次 | 112/120（8 败）、119/120（1 败）、120/120；合计 351/360，失败 9 |
| 因果探针：同一并发负载，只把测试内 9 处 `join(2)` 改为 `join(30)`，生产代码不变 | 1 轮 × 120 次 | 120/120，失败 0 |

失败全部发生在 `test_new_retry_gets_new_id_even_within_same_clock_tick`；另一个同刻度跨进程用例 `test_cross_process_coordination_adopts_different_retry_id_in_same_tick` 在全部采样中通过。并发负载来自同一干净树上的 BUG-170/BUG-175 采样进程；隔离运行时负载移除，失败归零。

### 4.3 判定与建议

- 产品侧的 `retry_id` 同刻度重复问题已由 DEV-108 修复；本条不是「修复无效」。
- 残留点是测试用固定 `join(2)` 等待异步协调线程，与 BUG-170/BUG-175 的 `monotonic()+0.3/5.0` 同属「以墙钟超时代替确定性同步」的测试时序缺陷；在 CI 并发或负载波动时会随机失败。
- 建议沿用 BUG-175 的处理方式：以可控假时钟/事件驱动同步替代 `join(2)` 的固定时限，或显式用 `Event.wait()` 加足够宽松的兜底；不要用「重跑一次通过」作为闭环证据。
- 闭环证据应为：修改后官方包在干净树多轮采样 0 失败（至少两轮 60 次），并附并发负载下的采样结果。

## 5. 本机观察，不作为产品问题反馈

- 本机覆盖升级后 `test_doc_links` 失败：本地树仍保留官方 0.48.0 已迁出的 442 个旧 `docs/` 文件（例如旧 `docs/RELEASE_NOTES_*.md`），导致 48 个断链、11 个断锚点。官方 v0.48.3 source.zip 干净树只有 5 个刻意不打包的 `.docx`/`.pro`/`.agents` 链接、0 断锚点；官方 git 标签检出 308 文档、3132 链接、0 断链 0 断锚，`test_doc_links` 8 tests OK。判定为本地历轮覆盖未删除旧文件造成的环境污染，不反馈作者。
- 0.48.2 Release 正文如实记录主干 CI 两次失败与干净树/ZIP 全量通过；本报告不把作者已声明的 CI 失败重复作为新问题，仅把 0.48.3 的残留 flaky 按同族反馈。
- 0.48.0 冷数据从源码包移除并有 prerelease 归档与清单，属设计；`docs/DEVELOPMENT.md` 指向 version.py、gate 因新文档布局变化，也属设计。
- Creo 9 / 12.4 实机与外部 WorkBuddy 黑盒复测不在标准更新授权范围，记「未验证」。
