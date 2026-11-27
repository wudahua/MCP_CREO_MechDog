# 0.47.1 反馈：0.47.0/0.47.1 发布后 POSTCHECK 实证未回填，main 停在发布提交、0.47.1 snapshot 仍为 pending

- 日期：2026-11-26（证据抓取截止 UTC `2026-11-26T15:25:49Z`）
- 验证对象：`wudahua/MCP_CREO_MechDog` v0.47.1（Release id `459515636`，node_id `RE_kwDOU_ueTM4bY6b0`，published `2026-11-26T14:22:21Z`；0.46.1→0.47.1 中间正式版 0.47.0 已逐版处理，未跳版）
- 本地环境：Windows / Creo 10.0.0.0 ProToolkit SDK / WorkBuddy MCP 客户端 / Python `.venv`
- 验证性质：原始 JSON 定版、四附件四方哈希、差异链、覆盖升级与零补丁编译、注册指纹、静态台账、门禁对照/篡改/反向闸门、fourref、官方干净树单测与 flaky 复测
- 实机边界：本轮**未**连接 Toolkit、**未**启动或关闭 Creo、**未**做故障注入；Release 正文中的 Creo 10 实机结论是作者自述，本轮未复核运行期行为。

## 1. 结论摘要

0.47.0/0.47.1 的**产品功能与交付链 technical 项全部通过**（四附件四方一致、零补丁编译、包一致性 2500/2500、注册指纹、工具数 112、BACKLOG 278、门禁负例全捕获、BUG-175 flaky 外部复测通过）。但发现一个**交付后流程问题**：

| 编号 | 问题 | 关键证据 | 判定 |
| --- | --- | --- | --- |
| P1 | 0.47.0、0.47.1 均**没有发布后 backfill 提交**；`main` 仍等于 0.47.1 发布提交；两版 POSTCHECK 在 tag、发布提交、main 三处都只有打包时点措辞，没有 Release id、没有 `exit 0`/`退出码 0`、没有四附件发布后核对表；0.47.1 snapshot 仍 `remote_verification: pending` | 见第 4 节；抓取截止时 0.47.0 已发布 6881s、0.47.1 已发布 3808s；此前各版 backfill 通常在发布后 63～831s 完成 | 与 `docs/development/RELEASING.md` 的强制要求冲突，**建议修复** |

这不是「编译/功能缺陷」，也不是「作者已声明延后」：`docs/development/RELEASING.md`、`docs/validation/RELEASE-0.47.1.md` 仍要求发布后把实证回填到 main 的唯一 POSTCHECK 入口，且 0.47.1 发布记录直接写「发布后远端核对见 发布后核对记录 和 Release 正文」，但这两个指向都不含实证。

## 2. 数据层正项（便于区分「技术交付」与「发布后台账」）

### 2.1 定版与四附件

- 重新以 GitHub API 原始 JSON 定版：v0.47.1 为最新正式版；0.46.1 之后存在中间正式版 0.47.0（id `459454832`，published `13:31:08Z`，发布提交 `baeb3d66…`），逐版处理。
- 两版各四附件（`source.zip` / 两个 `.sha256` / `seed-library.zip`）本地实算、sidecar、GitHub asset `digest`、Release body 四方一致，`FOUR_WAY_OK=true`，`body_hash_mismatch=[]`，sidecar ASCII+LF。
- 0.47.1 source.zip `12,432,963 B / 03757ed9a7774c4543c5305628b37ccd1f376e181de3ef2475a916fb35e01540`；seed-library.zip `493,442 B / 326eb7ac1c140fdf26205c2e17d282a326b34d2417b6bac459c53a9fde3e58d8`。Release body 只列 seed 摘要并明确 source 摘要在 sidecar，符合既定口径。
- 发布链：annotated tag `042fb6fe…` → 发布提交 `937dd2b2…`（20 文件，发布前 51s）；0.47.1 snapshot 的 `previous_release_commit=baeb3d66…` 正是 0.47.0 的真实发布提交（不是 nonexistent backfill）。

### 2.2 编译、包一致性与注册

- 官方原包零补丁编译：`BUILD_EXIT=0`，`error C` / `error LNK` / C1083 / C2065 / C3861 / C2039 / `fatal error` / C4819 / `Traceback` 全部 0。
- worker `12,093,440 B / 7ad76c08d75c7b2492aa5e8ad652719633867c6b80491d9c1a62eeb6c5ea9bce`；loader fingerprint `23f540b7…`、callback `02eac3e0…` 与 0.46.1 稳定一致。
- 包一致性 `2500/2500`，`real_diff=[]`，`eol_only=[]`，`missing=[]`；注册内部一致性 10/10。差异链 2480→2494→2500（REAL 186/20），native 改动集中在 `base_flange.cpp`、`generic.cpp`、`geometry_selectors.cpp`、`sketch_coordinates.cpp`、`solid_bounds.h`。

### 2.3 静态核对、门禁与单测

- 工具数 112（`@mcp.tool` 113 − `remove_tool` 1），与 `creo_capabilities.tool_count=112` 一致；BACKLOG `exit 0`，总数 278（BUG 142 / FEAT 89 / DEV 47）。
- DEV-104 将 `docs/DEVELOPMENT.md` 的版本入口改为「以 version.py 为准」，属单一 source of truth 策略；其他硬编码版本入口均为 0.47.1。
- `release_integrity.py` 从 72,384B 增至 72,884B，用于支持 `docs/release-notes/` 与 `docs/archive/work-items/` 布局并保留旧路径 fallback；门禁负例仍全部捕获。
- 门禁：`check_release_assets.py --tag` + body `exit 0`；本机 records 无 unit evidence `exit 1`（BUG-137/144 正确行为）；21 类记录门禁负例中除 G3 snapshot 删除 0（设计可选）外全部非 0，合法夹具 `exit 0`；source-zip 6 类篡改全 1、correct/untouched 全 0；反向闸门篡改种子 1 / 缺 sidecar 1 / 正常 0。
- 单测：官方干净树 `test_release_integrity` 55 tests OK、宿主保护 30 tests OK；本机核心子集 31 模块 490 tests OK；BUG-175 两段统一假时钟代码自 0.46.1 起逐字节一致（sha `7039d135…`），无真实 `monotonic()+N` deadline，干净树两轮独立 60 次复测均 60/60、失败 0。本机全量单测未跑，不宣称通过。

## 3. 规范依据：发布后实证必须回填到 main 的唯一 POSTCHECK 入口

`docs/development/RELEASING.md` 中仍保留以下明确要求：

1. 「Release id 与发布时间只回填到 `main` 的 POSTCHECK，不要求进入已冻结的包。」
2. 「发布后把真实列表、标签指向、附件摘要和 `exit 0` 结果追加到 `main` 的 POSTCHECK；冻结包内快照不回写。」
3. 「发布后核对唯一入口为 `RELEASE-POSTCHECK-2026-11-07.md`。分散在 validation 的旧核对原件保持字节不变……不能只留『见发布记录/待回填』。」

`docs/validation/RELEASE-0.47.1.md` 也写：「发布后远端核对见 [发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md) 和 Release 正文。」但核对结果两处均不存在（第 4 节）。因此这不是「包内预写措辞」的设计问题——规范要求的是**发布后追加到 main**，而本次连追加都没有发生。

## 4. P1 详细证据：两版均无发布后实证

### 4.1 发布链与时间间隔

| 版本 | Release id | published (UTC) | 发布提交 | 发布后 backfill | 抓取时距发布 |
| --- | --- | --- | --- | --- | --- |
| 0.47.0 | `459454832` | `2026-11-26T13:31:08Z` | `baeb3d66aa7166a874d474187fb73bfcfdf210f4` | **无** | 6881s（约 1h55m） |
| 0.47.1 | `459515636` | `2026-11-26T14:22:21Z` | `937dd2b289c28a2d77b845a23c47e7773bb92721` | **无** | 3808s（约 1h03m） |

- `/commits?per_page=N` 与 `/commits/main` 交叉核对：main 最新提交就是 0.47.1 发布提交 `937dd2b2…`，提交时间 `14:21:30Z`（早于发布 51s）。发布后没有任何提交。
- 0.47.0 同样没有可识别的发布后回填提交；其发布后 51 分钟内发布了 0.47.1，但 main 仍未包含 0.47.0 的发布后实证。
- 对照历史：0.44.0 回填晚 80s、0.45.1 回填即 main、0.46.1 回填晚 134s；此前每版都有发布后回填提交，且 backfill/main 段的 POSTCHECK 含 Release id 与 `退出码 0`。本轮是**首次两版连续缺失**。

### 4.2 四处引用（fourref）与 POSTCHECK 段落

对 0.47.1 抓取 tag `v0.47.1`、发布提交 `937dd2b2…`、main（以及 0.47.0 的 tag/发布提交段）：

| 引用 | POSTCHECK 段 | Release id | `exit 0`/`退出码 0` | 发布后核对段 | API digest/实算表 | 当前措辞 |
| --- | --- | --- | --- | --- | --- | --- |
| tag v0.47.1 | 796 B | 无 | 无 | 无 | 无 | 「远端校验发布后执行，当前未验证」 |
| 发布提交 937dd2b2… | 796 B | 无 | 无 | 无 | 无 | 同上 |
| main | 796 B | 无 | 无 | 无 | 无 | 同上 |
| tag v0.47.0 / 发布提交 baeb3d66… / main 的 v0.47.0 段 | 908 B | 无 | 无 | 无 | 无 | 同上 |

- `docs/releases/0.47.1.json`（tag / 发布提交 / main 三处一致）：`"remote_verification": "pending"`，`delivery_ids=["BUG-187","DEV-104"]`。
- Release 正文（0.47.1）只有版本说明与四附件清单、seed 摘要，没有 `exit 0`、API digest 或本地实算对照表。
- 工作树内全量检索 `459454832`、`459515636` 与 `v0.47.* + exit 0/退出码 0/发布后核对`，均无命中；即不存在「另写了独立 POSTCHECK 原件但未链接」的情况。

### 4.3 门禁为什么没有拦住

- `check_release_assets.py --tag v0.47.1 --dir <four assets> --body-file <body>` 返回 0；这只证明**本地附件与 body 自证一致**，不检查远端是否已发布后核对。
- `check_release_records.py --version 0.47.1`（带合法 unit evidence 夹具）返回 0；它检查的是冻结包内发布记录、逐 ID 表、snapshot `previous_release_commit` 等一致性，`remote_verification: pending` 在打包时点是**设计允许值**。
- 因此当前门禁无法发现「发布后没有追加实证到 main」这一流程缺口；需要新增跨远端状态检查，或至少在发布流程中把「main POSTCHECK 含 Release id + tag/main SHA + 四附件 API digest/实算对照 + `--tag` exit 0」作为交付完成的前置条件。

## 5. 建议

1. 为 0.47.0 与 0.47.1 补做发布后核对，或在确认策略变化时同步更新 `RELEASING.md`、`RELEASE-0.47.1.md` 中「发布后远端核对见……」的指向措辞，避免文档指向不存在的证据。
2. 在 `check_release_records.py` / CI 发布后阶段增加一项可执行检查：按版本号在 main 的 POSTCHECK 唯一入口中查找 Release id、`exit 0`/`退出码 0`、tag 对象与 main 提交、四附件名/大小/API digest/本地实算/sidecar 对照，并校验 snapshot `remote_verification` 已从 `pending` 变为完成态；缺失时非零退出。
3. 若确需延后回填，请在工作卡/发布记录中显式写明「待报告方复测/延后原因/计划时间」，而不是只留打包时点的「远端校验发布后执行，当前未验证」。

## 6. 本轮未发现的问题（避免误报）

- 0.47.0 的 DEV-104 开发入口统一、0.47.1 的 BUG-187 主基准面偏移法线对齐与 `frame_mismatch` 告警：作者标注实机范围 Creo 10 三组通过，Creo 9/12.4 与外部 WorkBuddy 黑盒未测；标准更新请求无实机授权，本轮记「未验证」，不作为新问题反馈。
- Release body 只列 seed 摘要、source 摘要在 sidecar：既定口径，四方校验通过，不重复报。
- `docs/DEVELOPMENT.md` 不再硬编码当前版本、gate 代码目录布局适配：均为设计变化，且负例实验仍全捕获，不报缺陷。
- 本机 `test_revolve_axis` 宿主 shim 污染现象本轮未复现；本机核心子集 490 tests OK，未跑全量单测，不宣称全量通过。
