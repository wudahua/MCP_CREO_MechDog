# 发布后附件核对记录（2026-11-07）

本文件补记 [DEV-075](../work-items/DEV-075.md) 指出的缺口：`RELEASING.md` 第 7 步要求「发布后用 `gh release view` 或 `tools/check_release_assets.py --tag <tag>` 核对远端恰有四个附件、两个 sidecar 与对应远端 ZIP 摘要一致，核对结果写入发布记录」，但此前只在各版 `RELEASE-*.md` 里记结论，没有可复核的发布后留存。原有小节记录**发布之后**对远端实际对象的重新下载与重算结果；2026-11-08新增小节另标历史索引、外部元数据和未核验事实；发布前的本地打包、CI 与验收结论仍以各版版本说明和发布记录为准。

## v0.47.0（2026-11-26，打包时点）

- 交付 [BUG-194](../work-items/BUG-194.md)、[BUG-195](../work-items/BUG-195.md)、[FEAT-091](../work-items/FEAT-091.md) 与 [FEAT-092](../work-items/FEAT-092.md)：`auto` 草图求解器回归修复与自助出口提示、包围盒面细分内缩误差界披露、空件平面报错与边选择器歧义提示、`round` 期望凹凸/加减料断言、`sheetmetal_base_flange` 包络偏移字段、只读 `creo_server_info`（工具数 112）与 `region.closed_chain` 封闭链选区；Windows x64 / Python 3.12.10 / Creo 10.0.0.0（release 42）10 项全链路实机通过。 [版本说明](../release-notes/RELEASE_NOTES_0.47.0.md) · [验证与发布记录](../validation/RELEASE-0.47.0.md)
- 四件附件为 `MCP_CREO_MechDog-0.47.0-source.zip`、`MCP_CREO_MechDog-0.47.0-source.zip.sha256`、`MCP_CREO_MechDog-0.47.0-seed-library.zip` 和 `MCP_CREO_MechDog-0.47.0-seed-library.zip.sha256`。种子包 SHA256 为 `1145977816e4abbfc99eff079da56491a37c9da5eb02c46bb2fb41b7c712e952`。两份同名 sidecar 分别记录对应 ZIP 的摘要。
- 远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.47.0)

## v0.46.1（2026-11-26，打包时点）

- 交付 [BUG-193](../work-items/BUG-193.md) 的提交前零锁 callback 预检：`callback_admission_status()` 零锁判定 `loft` / `surface_loft` 准入，未就绪时在建 job 与取 Toolkit 锁之前拒绝；Creo 10.0.0.0（release 42）未加载零锁/零作业拦截、启动回调自动准入与加载态建模保存重载全链路实机通过。另交付 [DEV-103](../work-items/DEV-103.md) 文档目录治理（`docs/README.md`、`GOVERNANCE_HISTORY.md`、`docs/archive/` 归档）。环境为 Windows x64 / Python 3.12.10。 [版本说明](../release-notes/RELEASE_NOTES_0.46.1.md) · [验证与发布记录](../validation/RELEASE-0.46.1.md)
- 四件附件为 `MCP_CREO_MechDog-0.46.1-source.zip`、`MCP_CREO_MechDog-0.46.1-source.zip.sha256`、`MCP_CREO_MechDog-0.46.1-seed-library.zip` 和 `MCP_CREO_MechDog-0.46.1-seed-library.zip.sha256`。种子包 SHA256 为 `8305c26aa2c91e20c0260ec7d61532ce64595e9d033084266b646adad0f46b0d`。两份同名 sidecar 分别记录对应 ZIP 的摘要。
- 远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.46.1)

### v0.46.1 发布后核对

- 正式 Release `459283150` 发布于 2026-11-26 10:53:15 UTC（非 draft、非 prerelease），附注标签 `v0.46.1` 指向发布主干提交 `742b2736d209a48629eb965b0c7662fb3d42c601`。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.46.1)
- 干净主干提交 `742b2736d209a48629eb965b0c7662fb3d42c601` 在 Windows x64 / Python 3.12.10 运行 `tools/test_unit.py` 共 **4,543** 项，0 失败、0 错误、6 跳过（`run_id=7f8d5d2b2c3641cca299b9dfe5be1572`，受测源码指纹 `049c3ccb46765405455e3c13277038bf73c045a5510e88b79164e743496e37f8`）；随后 `tools/dev_check.py` 通过（Ruff 0 lint / 0 unformatted）。合并前分支门禁中 `tools/test_mcp.py --offline` 与 `--offline --legacy-entry` 均 exit 0（`tool_count=111`，`capability_contract_verified=true`）。
- `PYTHONUTF8=1 tools/check_release_assets.py --tag v0.46.1` 退出码 0（`v0.46.1: four assets downloaded and verified; both sidecars match; release body self-proof verified`）：

| 远端附件 | 字节 | 核对实算 SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.46.1-source.zip` | 12,379,997 | `a371c74c59143e319975791a40defe9b3d5a8fbaedb0514bce0fff20ea7dd514` |
| `MCP_CREO_MechDog-0.46.1-source.zip.sha256` | 101 | 与对应 ZIP 摘要一致 |
| `MCP_CREO_MechDog-0.46.1-seed-library.zip` | 493,442 | `8305c26aa2c91e20c0260ec7d61532ce64595e9d033084266b646adad0f46b0d` |
| `MCP_CREO_MechDog-0.46.1-seed-library.zip.sha256` | 107 | 与对应 ZIP 摘要一致 |

- 未测范围与打包时点记录一致：Creo 9 / Creo 12.4 实机、本版零锁预检提交后的外部 WorkBuddy 黑盒复测。

## v0.46.0（2026-11-26，打包时点）

- 交付 [BUG-192](../work-items/BUG-192.md)、[FEAT-090](../work-items/FEAT-090.md)、[BUG-193](../work-items/BUG-193.md) 与 [DEV-102](../work-items/DEV-102.md)：拔模基准面方向说明与 `material_effect`、近容差 `arc-arc` 端点焊接与草图参数公开、`loft`/`surface_loft` 统一 `runtime_ready` 与 before-job callback 预检、`creo_capabilities` 操作列表口径与 `region.interior_point_yz_mm` 文档。环境为 Windows x64 / Python 3.12.10 / Creo 10.0.0.0（release 42）。 [版本说明](../release-notes/RELEASE_NOTES_0.46.0.md) · [验证与发布记录](../validation/RELEASE-0.46.0.md)
- 四件附件为 `MCP_CREO_MechDog-0.46.0-source.zip`、`MCP_CREO_MechDog-0.46.0-source.zip.sha256`、`MCP_CREO_MechDog-0.46.0-seed-library.zip` 和 `MCP_CREO_MechDog-0.46.0-seed-library.zip.sha256`。种子包 SHA256 为 `7ccae6e93dd1d7ed413c796a605d1488901e42abe93e8edbeb4e0fb190446384`。两份同名 sidecar 分别记录对应 ZIP 的摘要。
- 远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.46.0)

### v0.46.0 发布后核对

- 正式 Release `458917064` 发布于 2026-11-26（非 draft、非 prerelease），附注标签 `v0.46.0` 指向发布主干提交 `d6055f9b101aa40013a6f8daf8330ccff837b824`。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.46.0)
- 干净主干提交 `d6055f9b101aa40013a6f8daf8330ccff837b824` 在 Windows x64 / Python 3.12.10 运行 `tools/test_unit.py` 共 **4,542** 项，0 失败、0 错误、6 跳过（`run_id=fe5df2953b65475f8c8b78ca600e5d69`）；`tools/dev_check.py --skip-unit` 通过（Ruff 0 lint / 0 unformatted，`test_update_check`、`test_model_reconciliation`、`test_mcp --offline` 全通过）。
- `PYTHONUTF8=1 tools/check_release_assets.py --tag v0.46.0` 退出码 0（`v0.46.0: four assets downloaded and verified; both sidecars match; release body self-proof verified`）：

| 远端附件 | 字节 | 核对实算 SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.46.0-source.zip` | 12,360,590 | `4d9b789a44cca7c5ca3d2f835c4e6a25d4d8da27bf1de9238daf8e3f12d612bc` |
| `MCP_CREO_MechDog-0.46.0-source.zip.sha256` | 101 | 与对应 ZIP 摘要一致 |
| `MCP_CREO_MechDog-0.46.0-seed-library.zip` | 493,442 | `7ccae6e93dd1d7ed413c796a605d1488901e42abe93e8edbeb4e0fb190446384` |
| `MCP_CREO_MechDog-0.46.0-seed-library.zip.sha256` | 107 | 与对应 ZIP 摘要一致 |

- 本机 Creo 10.0.0.0（`release_numeric=42`）实机验收覆盖 `BUG-192`（8/8 拔模方向与 `material_effect`）、`FEAT-090`（40 弧 10 轮廓微间隙吸附拉伸，作业 `5ced5a2ea83a40049ebe5499299853b9`，体积 `1047.002224 mm³`，保存重载 true）与 `BUG-193`（ready 态 `callback_status` 与 compact `runtime_ready`）。Creo 9 / Creo 12.4、外部原始 `gear10.json` 文件、未加载 callback 实机会话及 WorkBuddy 黑盒仍未验收。

## v0.45.2（2026-11-26，打包时点）

- DEV-002 第四、五批交付 Python 实现包化、新安装入口和 AI Agent 兼容说明。发布回归覆盖 Windows x64 / Python 3.12.10 的离线 stdio、安装配置和源码分发。 [版本说明](../release-notes/RELEASE_NOTES_0.45.2.md) · [验证与发布记录](../validation/RELEASE-0.45.2.md)
- 四件附件为 `MCP_CREO_MechDog-0.45.2-source.zip`、`MCP_CREO_MechDog-0.45.2-source.zip.sha256`、`MCP_CREO_MechDog-0.45.2-seed-library.zip` 和 `MCP_CREO_MechDog-0.45.2-seed-library.zip.sha256`。种子包 SHA256 为 `ae0c8928d9febbd001524bc821d709a499d4235452bac64bea365e1304c336fc`。两份同名 sidecar 分别记录对应 ZIP 的摘要。
- 远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.45.2)

### v0.45.2 发布后核对

- 正式 Release 458852053 发布于 2026-11-26 01:53:12 UTC。2026-11-26 01:54:14 UTC（09:54:14 +08:00）独立查询的远端 `main` 和解引用后的 `v0.45.2` 标签均指向 `77aaa85ed318208fef0e6628773a1cefd31ab4f7`。Release 为正式公开版本。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.45.2)
- Windows x64 / Python 3.12.10 下，候选 Git 工作树和分发 ZIP 独立解包分别运行 `tools/dev_check.py --work-item DEV-002`，各 4,525 项，均为 0 失败、0 错误，分别跳过 13 与 14 项。工作树提交为 `77aaa85ed318208fef0e6628773a1cefd31ab4f7`，dirty=false，受测源码指纹为 `a5b786c2d114a3457c52c9ab3d6f40551769b27b911eda70402cdcdb50804c8a`。两个环境均离线安装锁定依赖，在仓库外验证新旧 stdio 入口及 111 个工具。compact 为 17,330 B，full 15 页中最大页为 32,129 B。
- 分发 ZIP 的 2,459 个成员在测试后逐字节核对，正式打包件和受测 ZIP 的整体 SHA256 相同。解包路径位于 `build/`，单测报告的目录回退指纹只统计了根目录模块。另按正式包清单复核了 678 个 Python 及原生源码文件，指纹为 `6e4450c4a131ac5d2c68efc45246ba1d572d201101f1f7a7cff189a1d69b8cbe`。
- `gh release download` 独立下载了四件附件。下表为下载实算 SHA256，与 GitHub API 的 digest 和正式打包件相同。两份 sidecar 匹配各自 ZIP，Release 正文列出的摘要亦吻合。默认 Windows 编码读取中文正文时首次报解码异常，设置 `PYTHONUTF8=1` 后重跑 `tools/check_release_assets.py --tag v0.45.2` 返回 0。对独立下载目录和实际 Release 正文的本地复核同样返回 0。

| 远端附件 | 字节 | 下载实算 SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.45.2-seed-library.zip` | 493,442 | `ae0c8928d9febbd001524bc821d709a499d4235452bac64bea365e1304c336fc` |
| `MCP_CREO_MechDog-0.45.2-seed-library.zip.sha256` | 107 | `2c92d46a8a9711926f6518c3561a20c3a682e047ccac8d38f987f21df7c088ab` |
| `MCP_CREO_MechDog-0.45.2-source.zip` | 12,328,834 | `6585de7c12acbe36e226373f8c861bd2f9bdcf322835cfa92ad4da7d50dc6d74` |
| `MCP_CREO_MechDog-0.45.2-source.zip.sha256` | 101 | `31a9abe53c14f36a8cd6e656f452f000b0b2204c5ad7c4c3246e2b73b30442d5` |

相对 v0.45.1 正式源码包，第三方 JSON 源与许可证、九个种子 PRT 均逐字节相同。全部原生分发文件中 71 个字节相同，`native/generic.cpp` 和 `native/stl_export.h` 仅换行符字节有差异，经 LF 归一化后相同。回调源码沿用同一归一化口径。DLL、注册和 Creo 实机几何在本轮发布中未复验。发布后核对确认 [DEV-002](../work-items/DEV-002.md) 的交付范围与[台账](../BACKLOG.md)、[版本说明](../release-notes/RELEASE_NOTES_0.45.2.md)及[开发入口](../DEVELOPMENT.md)一致。

## v0.45.1（2026-11-25，打包时点）

- Windows x64 / Creo 10.0.0.0（release 42）完成 14 m 球鼻艏 STL 专项。 [版本说明](../release-notes/RELEASE_NOTES_0.45.1.md) · [验证与发布记录](../validation/RELEASE-0.45.1.md)
- 四件附件为 `MCP_CREO_MechDog-0.45.1-source.zip`、`MCP_CREO_MechDog-0.45.1-source.zip.sha256`、`MCP_CREO_MechDog-0.45.1-seed-library.zip` 和 `MCP_CREO_MechDog-0.45.1-seed-library.zip.sha256`。种子包 SHA256 为 `51c41e1e01d712302d639fa9302cf3af871148c7e2bbf8553a27e6d641a0a8f5`。两份同名 sidecar 分别记录对应 ZIP 的实际摘要。
- 候选工作树和独立解包的 `tools/test_unit.py` 各运行 4,532 项，均无失败或错误，分别跳过 7 项和 8 项。源码包 2,453 个文件逐字节核对通过。解包安装使用显式 MSVC/Windows SDK 路径，离线 stdio 验证 111 个工具，实机简单建模作业 `fb0bd5836c2546d6882288dd6c214904` 保存重载为 true。
- 正式 Release 458319515 发布于 2026-11-25 15:41:44 UTC。2026-11-25 15:43:26 UTC（2026-11-25 23:43:26 +08:00）重新查询，发布时的远端 `main` 与标签 `v0.45.1` 指向 `0177e227dd42587541e3e01628647deda53e4dea`。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.45.1)
- `tools/check_release_assets.py --tag v0.45.1` 返回 0。用 `gh release download` 独立重下四件，字节与本地打包件相同。两份 sidecar 匹配 ZIP，正文列出的 SHA256 与实算一致。下表摘要同时等于 GitHub API 的 digest。

| 远端附件 | 字节 | 下载实算 SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.45.1-seed-library.zip` | 493,442 | `51c41e1e01d712302d639fa9302cf3af871148c7e2bbf8553a27e6d641a0a8f5` |
| `MCP_CREO_MechDog-0.45.1-seed-library.zip.sha256` | 107 | `e9f9f4df4cb3eb54a1e5ff78e35544bc84cb34c1c96c35e3971a211daa20e412` |
| `MCP_CREO_MechDog-0.45.1-source.zip` | 12,319,665 | `95e2b04a685152c9ce6dedb17668ea2003b52162b06491da58f199bb8c92d470` |
| `MCP_CREO_MechDog-0.45.1-source.zip.sha256` | 101 | `4fd182b857a79c6a7232b6201cef00dc8b8e017252785722216325059bfaedc7` |

回调入口与前版源码包字节一致，第三方 JSON 和许可证逐字节相同，种子库仅兼容版本清单有变化。解包安装生成独立目录的注册文件。该环境下 worker SHA256 为 `a8e18596b427983ec2fbd933c0259e8c24bbe38514443a915749a3bd2e3ea016`，loader SHA256 为 `5d6897b5f7db29d3c90311ae0820025ce7f5100b0d63cf09c57a09f89e86cb0a`，callback SHA256 为 `fb2b3dd4a6ce0963dcc51c84dca2a0c1d2f946507ceb1c8c9fb3701bed9742c8`。

## v0.45.0（2026-11-25，打包时点）

- Creo 10.0.0.0（release 42）专项验收加料体积、实体面包围盒、默认草图、拔模、基准面角度和启动探针。 [版本说明](../release-notes/RELEASE_NOTES_0.45.0.md) · [验证与发布记录](../validation/RELEASE-0.45.0.md)
- 四件附件为 `MCP_CREO_MechDog-0.45.0-source.zip`、`MCP_CREO_MechDog-0.45.0-source.zip.sha256`、`MCP_CREO_MechDog-0.45.0-seed-library.zip` 和 `MCP_CREO_MechDog-0.45.0-seed-library.zip.sha256`。源码 ZIP 含 2448 个文件，与工作树逐字节一致，SHA256 为 `f7e9e69a855459a6f1f5f7479bf059e7f8e530fa8db48711ad7c14c91ab42576`。种子包 SHA256 为 `1ab6d9892f764a019642a1595f59c4f8de64f04933f6657da8597abab80fa73f`。两份同名 sidecar 分别记录对应 ZIP 的实际摘要。
- 解包后的重新安装未执行：本机安全策略禁止 `reg.exe`，临时目录内的 MSVC/Windows SDK 预检失败；不以候选安装结果代替，也不计为通过。
- 远端核对（2026-11-25）：标签 `v0.45.0` 指向 `378990cc16d75ea2a86417619c3fefce1ef2a972`，与远端 `main` 一致。从 Release 直链重新下载四件附件，`tools/check_release_assets.py --tag v0.45.0 --version 0.45.0 --dir build/release-assets/v0.45.0 --body-file release-notes/RELEASE_NOTES_0.45.0.md` 返回 `local_verified`；两份 sidecar 与 ZIP 摘要一致，正文自证通过，下载件与本地打包件逐字节相同。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.45.0)


v0.44.1 及更早版本的发布后核对记录已归档至 [历史核对归档](../archive/RELEASE-POSTCHECK-ARCHIVE-2026.md)。

