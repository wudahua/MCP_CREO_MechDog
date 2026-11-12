# 发布后附件核对记录（2026-11-07）

本文件补记 [DEV-075](../work-items/DEV-075.md) 指出的缺口：`RELEASING.md` 第 7 步要求「发布后用 `gh release view` 或 `tools/check_release_assets.py --tag <tag>` 核对远端恰有四个附件、两个 sidecar 与对应远端 ZIP 摘要一致，核对结果写入发布记录」，但此前只在各版 `RELEASE-*.md` 里记结论，没有可复核的发布后留存。原有小节记录**发布之后**对远端实际对象的重新下载与重算结果；2026-11-08新增小节另标历史索引、外部元数据和未核验事实；发布前的本地打包、CI 与验收结论仍以各版版本说明和发布记录为准。

## 方法与范围

- 工具：`tools/check_release_assets.py --tag <tag> --version <version>`（gh 取 API 元数据 → 精确 tag 附件 → 下载四文件 → 重算 SHA256 → 比对 sidecar 内容）。
- 时间：2026-11-07T16:58:23Z 起（本机 +08:00），逐版连续执行，exit code 均为 0。
- 环境：Windows x64；Python 3.12 虚拟环境（`.venv`）；`gh` 已登录；源码目录 `C:\i0182`（`origin/main` 的独立工作树，0.18.2 开发分支），核对对象是已发布远端 Release，不受工作区改动影响。
- 命令输出原文见本轮 `build/postcheck/postcheck.log`；下表 digest 由 GitHub Release API 的 `assets[].digest` 读出，与本地重算结果一致。

## v0.17.4

- 标签对象：`v0.17.4` → 提交 `b57dbdac7747c670433b964a5294f8373b6c757b`；发布 2026-11-07T05:24:16Z；非 Pre-release。
- 核对结果：**四附件齐全，两个 sidecar 与对应 ZIP 摘要一致**（exit 0）。

| 附件 | SHA256（远端 digest 与本地重算一致） | 字节 |
| --- | --- | ---: |
| `MCP_CREO_MechDog-0.17.4-source.zip` | `8f8f649c2d7c8420145d23a79f1f0749a525bae4f5f348a97401b71fea4fbc09` | 8 382 351 |
| `MCP_CREO_MechDog-0.17.4-source.zip.sha256` | `34e00b85164135df86fdab798dfa39b413e33a45581618c829f75ca2d9652bd8` | 101 |
| `MCP_CREO_MechDog-0.17.4-seed-library.zip` | `a6c633b49cb243ca1f58e6f3b8756f30a9e0b32eefebcc0e185bec1bd79a3583` | 493 442 |
| `MCP_CREO_MechDog-0.17.4-seed-library.zip.sha256` | `f53acf87a22b9641d9ae2d8b732993451b3ecc05d0ef760150b0c3b23e3e64b2` | 107 |

## v0.18.0

- 标签对象：`v0.18.0` → 提交 `58dd76b2d47e180e7e54d701cfaa4449aae49654`；发布 2026-11-07T07:04:07Z；非 Pre-release。
- 核对结果：**四附件齐全，两个 sidecar 与对应 ZIP 摘要一致**（exit 0）。

| 附件 | SHA256（远端 digest 与本地重算一致） | 字节 |
| --- | --- | ---: |
| `MCP_CREO_MechDog-0.18.0-source.zip` | `dab4ca04ee58ae643e4e492ef3870d04d8724921c57be8e554c96136ee874849` | 8 485 592 |
| `MCP_CREO_MechDog-0.18.0-source.zip.sha256` | `3c4bd463dadc967eba2d3fd52f66b8c2998bb4d0186834ff811fef731fed9dfa` | 101 |
| `MCP_CREO_MechDog-0.18.0-seed-library.zip` | `b6acab41fd727bb555ec6bb825116df2eab1e81e214db1c7c804e4f5e709a05b` | 493 442 |
| `MCP_CREO_MechDog-0.18.0-seed-library.zip.sha256` | `02c3823da9f59a745b3a3685c82d7342abf24d95b4260ffa06d046aa6069b51b` | 107 |

## v0.18.1

- 标签对象：`v0.18.1` → 提交 `9d725691c556c8063316a2cdf4d506c818a7baf7`；发布 2026-11-07T08:53:07Z；非 Pre-release。
- 核对结果：**四附件齐全，两个 sidecar 与对应 ZIP 摘要一致**（exit 0）。

| 附件 | SHA256（远端 digest 与本地重算一致） | 字节 |
| --- | --- | ---: |
| `MCP_CREO_MechDog-0.18.1-source.zip` | `658950c837895f96e4ec254610d18b8fe5012ae585d5a567cc5c2409940d08a7` | 8 444 988 |
| `MCP_CREO_MechDog-0.18.1-source.zip.sha256` | `ea9b403e87d9139fe299b7f5f61770dbac6ecb5eb46093508496bdddb3daf901` | 101 |
| `MCP_CREO_MechDog-0.18.1-seed-library.zip` | `8e5f512571de9ff494db3a0964f7ff00d0c49a4c5f9767f93e08f385436a640e` | 493 442 |
| `MCP_CREO_MechDog-0.18.1-seed-library.zip.sha256` | `c2b3df7825c85203990722b51ab5e80fae589f444845f292b503e8c62bc1f937` | 107 |

## v0.18.2（2026-11-08 DEV-077 补齐四附件数据）

- 发布链接：[v0.18.2](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.18.2)。标签对象 `v0.18.2` → annotated tag `4c659f5e1fe24e0ff76a1142f15ea80c3bc48e08` → 提交 `43862f00237d1aac34bce5cc1e576e2424c3ba39`；发布时间 `2026-11-07T10:18:16Z`；非 Pre-release。
- 核对结果：`tools/check_release_assets.py --tag v0.18.2 --version 0.18.2` exit 0，「v0.18.2: four assets downloaded and verified; both sidecars match」。
- 历史独立核对：[2026-11-07 POSTCHECK 第1节C5与第3节](../validation/feedback-0.17.4-2026-11-07/POSTCHECK-RELEASE.md)：C5 同一命令 exit 0，四附件已下载、两个 sidecar 与 ZIP 一致；C9 另核本地 SHA256 与 API digest 一致。历史窗口 2026-11-07 18:50–19:00 +08:00。
- 数据来源：本批归档的 [0.18.2 离线升级复核原件](../validation/feedback-0.18.2-2026-11-08/originals/2026-11-07CREO10.0.0.0-0.18.2-本版交付卡DEV075仍开发中与台账计数166实为165及POSTCHECK本版段未回填.md) §二.2 与 §七；报告方取值时间 `2026-11-07 18:22 +08:00`，取值方式为 `download_report.json` 的 `api_digest`（GitHub API `assets[].digest`）与本机 `local_sha256` 逐项比对一致。两个 sidecar 均为 ASCII + LF。**DEV-077 只按原件转录补齐本节，本轮未联网重跑、未重新下载重算；精确 tag 的当轮核对仍见 G12。**

| 附件 | SHA256（报告方远端 digest 与本地重算一致） | 字节 |
| --- | --- | ---: |
| `MCP_CREO_MechDog-0.18.2-source.zip` | `4e33ebc713be62485d932267766eb8a1092b2b01f918876848925ef1c55d673b` | 8 458 979 |
| `MCP_CREO_MechDog-0.18.2-source.zip.sha256` | `727cf550231b5fe5bc0e230b409de289adedf2a99478801e68d700c66d65e7af` | 101 |
| `MCP_CREO_MechDog-0.18.2-seed-library.zip` | `676536ca85601d0ce7e954a000fad0af8a73b7579f02ab27f1a8f2bbac606a1a` | 493 442 |
| `MCP_CREO_MechDog-0.18.2-seed-library.zip.sha256` | `6d76cbee146f68ad2200343c382d07177532688b17f3aa83298f21b120d98c7d` | 107 |

四件名称逐个列出，未用通配；两份 sidecar 内容分别是对应 ZIP 的摘要。`docs/validation/RELEASE-0.18.2.md` 是发布前历史原件，按既有策略保持字节不变，其「发布后记录 / 结果补记」两行由本节与统一入口收口，不回写旧文件。

## v0.18.3 / v0.18.4（2026-11-08离线整合，非本轮远端实测）

依据：[原件manifest](../validation/feedback-0.18.4-2026-11-08/manifest.json)、其`release_meta.json`及反馈报告；[勘误与范围](RELEASE-ERRATA-2026-11-08.md)。本轮仅从本地Git对象确认标签提交。平台时间、发布状态、四方摘要结论来自所给资料，未重新访问GitHub，当前main/远端最新版本未确认。

| 版本 | 本地标签指向提交 | 资料所报发布时间UTC | Release链接 |
| --- | --- | --- | --- |
| 0.18.3 | `5cf7c11750711ffc16675e7f82cbaa0fd79465ad` | 2026-11-07T15:45:17Z | [v0.18.3](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.18.3) |
| 0.18.4 | `04927a99a9b8e2ac2a572b11ac9be66ea3f9f391` | 2026-11-07T17:41:40Z | [v0.18.4](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.18.4) |

0.18.4所给元数据：非draft、非prerelease、4附件；声称本地SHA256/sidecar/Release body/API digest四方一致。**以下只是外部记录转录，不是本轮下载重算结果**：

| 附件 | 资料SHA256 | 资料字节数 |
| --- | --- | ---: |
| `MCP_CREO_MechDog-0.18.4-source.zip` | `81ff64939c9b14ae94635bb49928664526d8fd4b64bda25836381320eb0f8f4f` | 8752689 |
| `MCP_CREO_MechDog-0.18.4-source.zip.sha256` | `be337e203d0a0e9e2edfc9d7eeeaa0fa074df8be0eb1ed7f8fe1f3636704e0e5` | 101 |
| `MCP_CREO_MechDog-0.18.4-seed-library.zip` | `1a030983c448d1f76cf5b74d878abce653e5d389ff939468b5cd314b43eb8647` | 493442 |
| `MCP_CREO_MechDog-0.18.4-seed-library.zip.sha256` | `168f7f4a277ad8b92d6b039839ed73626bb2af5ef66d85bcacbceeff27623aca` | 107 |

两个sidecar的101/107字节来自所给报告第2节表格（JSON摘要未列大小）。

2026-11-08T07:41Z 前后补齐精确 tag 重下重算：`tools/check_release_assets.py --tag v0.18.2/v0.18.3/v0.18.4` 三条均 exit 0（「four assets downloaded and verified; both sidecars match」）。0.18.3 与 0.18.4 的 API `assets[].digest` 与本地重算一致：

| 版本 | 附件 | 字节 | SHA256 |
| --- | --- | ---: | --- |
| 0.18.3 | `MCP_CREO_MechDog-0.18.3-source.zip` | 8 650 655 | `042959b54dab8de15044b9991f7defc3abce476c0cee8228997f7f00979b45bb` |
| 0.18.3 | `MCP_CREO_MechDog-0.18.3-source.zip.sha256` | 101 | `de4e08b40a4127d483fb4f93d93d62d726c7a2d7f5d8644ebaee1af0678df657` |
| 0.18.3 | `MCP_CREO_MechDog-0.18.3-seed-library.zip` | 493 442 | `7325485f26201c0242a315e7aa0291714a3de81e852eccbba6e60f6288831102` |
| 0.18.3 | `MCP_CREO_MechDog-0.18.3-seed-library.zip.sha256` | 107 | `06b9ba48b97a240ce4d784e22ee69851f0305b8ac835642a8b77867de165ba6b` |
| 0.18.4 | `MCP_CREO_MechDog-0.18.4-source.zip` | 8 752 689 | `81ff64939c9b14ae94635bb49928664526d8fd4b64bda25836381320eb0f8f4f` |
| 0.18.4 | `MCP_CREO_MechDog-0.18.4-source.zip.sha256` | 101 | `be337e203d0a0e9e2edfc9d7eeeaa0fa074df8be0eb1ed7f8fe1f3636704e0e5` |
| 0.18.4 | `MCP_CREO_MechDog-0.18.4-seed-library.zip` | 493 442 | `1a030983c448d1f76cf5b74d878abce653e5d389ff939468b5cd314b43eb8647` |
| 0.18.4 | `MCP_CREO_MechDog-0.18.4-seed-library.zip.sha256` | 107 | `168f7f4a277ad8b92d6b039839ed73626bb2af5ef66d85bcacbceeff27623aca` |

0.18.3 / 0.18.4 均为非 draft、非 prerelease，`published_at` 分别为 `2026-11-07T15:45:17Z`、`2026-11-07T17:41:40Z`。0.18.2 的四附件数据仍以本节上方报告方转录为准，本轮 `--tag` 命令同样 exit 0，但未逐项重列摘要。

0.18.3/0.18.4 的精确 tag 重下重算已于 2026-11-08T07:41Z 补记；Release body 原文未逐字比对，当前 main 的包含关系见 v0.19.0 段。

## v0.19.0（2026-11-08 本轮联网实测）

- 核对时间：`2026-11-08T07:41:05Z` / `2026-11-08 15:41:05 +08:00`。
- 标签对象：`v0.19.0` → annotated tag `3f17e887de89e8c7f655908371ef04e86ed1258d` → 提交 `86020e71397137600f748b3433de2f9a75383b22`；tagger 时间 `2026-11-08T06:40:44Z`。
- Release：[v0.19.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.19.0)，id `438079516`，非 draft、非 prerelease；`created_at=2026-11-08T06:40:44Z`，`published_at=2026-11-08T06:40:55Z`，`target_commitish=main`。
- 核对命令：`tools/check_release_assets.py --tag v0.19.0 --version 0.19.0` → exit 0，「v0.19.0: four assets downloaded and verified; both sidecars match」。
- 四附件逐个列出（未用通配）；API `assets[].digest`、下载后本地实算 SHA256 与 sidecar 内容三者一致：

| 附件 | 字节 | SHA256 | API 创建时间 |
| --- | ---: | --- | --- |
| `MCP_CREO_MechDog-0.19.0-source.zip` | 8 908 094 | `9caa479041c2303e5e923faf48d0e5406de516e39050d71495ea3ec8c00a9878` | 2026-11-08T06:40:50Z |
| `MCP_CREO_MechDog-0.19.0-source.zip.sha256` | 101 | `0eb2615c836a8b96655e12c3fc6f5d443e2e9b5d8e209040d79be9cb3c9a2d9e` | 2026-11-08T06:40:50Z |
| `MCP_CREO_MechDog-0.19.0-seed-library.zip` | 493 442 | `05859ac1ae89d0c0455f6b4aa8a02a34b232588c4d1b4da74d6842f21041a072` | 2026-11-08T06:40:50Z |
| `MCP_CREO_MechDog-0.19.0-seed-library.zip.sha256` | 107 | `9cce3894e4ebd5ae2f3cfe650334becf83e0f398a62bb5234e179c0ffc7d506b` | 2026-11-08T06:40:50Z |

- 本记录只证明远端附件、两个 sidecar 与对应 ZIP 摘要一致；不重新验证包内功能、Creo 实机或安装结果，也不回写 `RELEASE-0.19.0.md` 历史原件。v0.18.2/0.18.3/0.18.4 的精确 tag 已在各自段落按同一命令重下重算并记录（见上），本行旧的「仍待补」表述已删除（DEV-079，2026-11-08）。

## v0.19.1（2026-11-08 本轮联网实测）

- 核对时间：`2026-11-08T08:08:02Z` / `2026-11-08 16:08:02 +08:00`。
- 标签对象：`v0.19.1` → annotated tag `e34075d3a7ec453bec29807329b6c4686bc54c1f` → 提交 `9dcf5ee`。
- Release：[v0.19.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.19.1)，id `438114011`，非 draft、非 prerelease；`created_at=2026-11-08T08:07:26Z`，`published_at=2026-11-08T08:07:49Z`，`target_commitish=main`。
- 核对命令：`tools/check_release_assets.py --tag v0.19.1 --version 0.19.1` → exit 0，「v0.19.1: four assets downloaded and verified; both sidecars match」。
- 四附件逐个列出（未用通配）；API `assets[].digest`、下载后本地实算 SHA256 与 sidecar 内容三者一致：

| 附件 | 字节 | SHA256 | API 创建时间 |
| --- | ---: | --- | --- |
| `MCP_CREO_MechDog-0.19.1-source.zip` | 9 160 836 | `eb1644599cff11fb53450c3f02ee5625a71d9b194a6a6170bd515d55cb5b71ef` | 2026-11-08T08:07:46Z |
| `MCP_CREO_MechDog-0.19.1-source.zip.sha256` | 101 | `e6b776917e8492b044659b8c97fbebaa9a4a94c3548376a4e148fc1ba1ca3442` | 2026-11-08T08:07:46Z |
| `MCP_CREO_MechDog-0.19.1-seed-library.zip` | 493 442 | `a7d864271b2e188e1f2a51eeea2046d15cf8615b10fde9b87beb466e8350657f` | 2026-11-08T08:07:46Z |
| `MCP_CREO_MechDog-0.19.1-seed-library.zip.sha256` | 107 | `16206fd52e2aa91f755bfc321beb02fa2403fd8049132d26d34f333befb161e2` | 2026-11-08T08:07:46Z |

## v0.21.0（2026-11-11 本轮联网实测）

- 核对时间：`2026-11-11T05:15:33Z` 发布后立即核对（本机 +08:00）。
- 标签对象：`v0.21.0` → annotated tag `1932c03b7842f04603a979393ffb607db2beaa7a` → 提交 `990c88a`。
- Release：[v0.21.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.21.0)，id `441266770`，非 draft、非 prerelease；`created_at=2026-11-11T05:14:44Z`，`published_at=2026-11-11T05:15:33Z`，`target_commitish=main`。
- 核对命令：`tools/check_release_assets.py --tag v0.21.0` → exit 0，「v0.21.0: four assets downloaded and verified; both sidecars match」。
- 四附件逐个列出（未用通配）；API `assets[].digest`、下载后本地实算 SHA256 与 sidecar 内容三者一致：

| 附件 | 字节 | SHA256 | API 创建时间 |
| --- | ---: | --- | --- |
| `MCP_CREO_MechDog-0.21.0-source.zip` | 9 509 982 | `ff3ef09eb27409089375b61a61505c1a1fa359f16cd5507858325dcaac1be4ec` | 2026-11-11T05:15:30Z |
| `MCP_CREO_MechDog-0.21.0-source.zip.sha256` | 101 | `f7b66d0158c79272291a66adda430ab46bca8f74c4222bce791bb8d67b6bcaf0` | 2026-11-11T05:15:30Z |
| `MCP_CREO_MechDog-0.21.0-seed-library.zip` | 493 442 | `da2a2936afdc5c1afbc1c7ffd5c9d70390020ec41f3cdb2f086d2151259a0f46` | 2026-11-11T05:15:30Z |
| `MCP_CREO_MechDog-0.21.0-seed-library.zip.sha256` | 107 | `9309ac3dd750d0f720963ddb9ab31f5fcbdcc8a3945e7103ed613873f6014bfe` | 2026-11-11T05:15:30Z |

- 本记录只证明远端附件、两个 sidecar 与对应 ZIP 摘要一致；不重新验证包内功能、Creo 实机或安装结果。发布前本机四附件闸门（`tools/package.py`）同样通过，源码包解压单测的 MAX_PATH 例外见 [RELEASE-0.21.0](../validation/RELEASE-0.21.0.md)。
- **勘误（2026-11-11，FEAT-065 T4 补记，未改已发布原文）**：[0.21.0 版本说明](../RELEASE_NOTES_0.21.0.md)只列了 FEAT-065 M2（`guides`），漏列同版发布的 M1。对照标签源码可以确认：`src/creo_mechdog/surface_ops.py` 中 `SurfaceLoftOp.sections` 在 `v0.20.0` 为 `max_length=2`，在 `v0.21.0` 为 `max_length=32`；`interpolation` 同版放开为 `straight|smooth`，三截面以上必须用 `smooth`。M1 的实机证据见 [FEAT-065](../work-items/FEAT-065.md)「2026-11-11 M1 实施与实机验收」。这条补记不改变已发布附件及其摘要。

## v0.19.2（2026-11-08 本轮联网实测）

- 核对时间：`2026-11-08T12:20Z` / `2026-11-08 20:20 +08:00`。
- 标签对象：`v0.19.2` → annotated tag `fd8159cd5644d5e57f14cd0b80b35e0d5b7a1be0` → 提交 `df8e178553348fc1f438559a2d506ae6bfd5a9e0`。
- Release：[v0.19.2](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.19.2)，id `438226979`，非 draft、非 prerelease；`created_at=2026-11-08T12:19:21Z`，`published_at=2026-11-08T12:19:48Z`，`target_commitish=main`。
- 核对命令：`tools/check_release_assets.py --tag v0.19.2` → exit 0，「v0.19.2: four assets downloaded and verified; both sidecars match」。
- 四附件逐个列出（未用通配）；API `assets[].digest`、下载后本地实算 SHA256 与 sidecar 内容三者一致：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.19.2-source.zip` | 9 259 802 | `922fb7fdaf8d514f6cdc13b3b71984d1275213047f80afd5032aa495e447b7b5` |
| `MCP_CREO_MechDog-0.19.2-source.zip.sha256` | 101 | `ec17e070ef9cc696893855db77a5b551f568365496a46916291040ff66903279` |
| `MCP_CREO_MechDog-0.19.2-seed-library.zip` | 493 442 | `22a7a32d7636d6babf7b68b9526b6b935f4d97386ff06ba9c2487002f4e71558` |
| `MCP_CREO_MechDog-0.19.2-seed-library.zip.sha256` | 107 | `aeec87c4c01dbb91466253754cfa05c4210c13e1cd097d425c1fc9adb8bd434d` |

## v0.19.3（2026-11-09）

- 记录时间：2026-11-09。`main` 提交 `096e86a2a6d9a73c4716ca2e6758e03e9fcfab31`（`f1c0a94..096e86a` fast-forward），`origin/main` 同值；附注标签对象 `61d1d2b64fd2490853f2b5ec0bfb6ec74085e1d0`（`v0.19.3`，指向上述提交）。
- Release：[v0.19.3](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.19.3)，id `RE_kwDOU_ueTM4aLAs8`，非 draft（`isDraft=false`）、非 prerelease；`published_at=2026-11-09T12:15:07Z`。
- 核对命令：`tools/check_release_assets.py --tag v0.19.3` → exit 0，「v0.19.3: four assets downloaded and verified; both sidecars match」。
- 四附件逐个列出（未用通配）；下载后本地实算 SHA256 与 sidecar 内容一致：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.19.3-source.zip` | 9 333 252 | `aed3b422acd815dcf624423d1c9d43640c7fabb28c8a631c2eb2b0d0380df463` |
| `MCP_CREO_MechDog-0.19.3-source.zip.sha256` | 101 | `ddcc3a651173ef293974ffec35eabbb214559a3d7c4c19d56b032dad7f21470e` |
| `MCP_CREO_MechDog-0.19.3-seed-library.zip` | 493 442 | `bc85958afbf8f3da0affde7144c13a145ebdd95eb04df529015595c59ab1e64a` |
| `MCP_CREO_MechDog-0.19.3-seed-library.zip.sha256` | 107 | `8c1299fbb8066d3aefedeb6c3b98b4274a4d594a6a4d0266be4c90847b29f1d5` |

- 本版未改 `native/*.cpp`、未连 Creo、未编译执行器；验收与未测范围以 `docs/validation/RELEASE-0.19.3.md` 与 Release 正文为准。本段只做远端附件核对，不重新验证包内功能。

## v0.20.0（2026-11-10）

- 记录时间：2026-11-10 17:57（+08:00）。`main` = `origin/main` = `2d7b498cd793a3f4693a561df6ae0df8f809d0f7`（`2c78aaa..2d7b498`）；附注标签对象 `3f4ed82589536f572f7265b718d96970ecebe715`（`v0.20.0`，指向上述提交）。
- Release：[v0.20.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.20.0)，id `RE_kwDOU_ueTM4aPLew`，非 draft、非 prerelease，`published_at=2026-11-10T09:56:06Z`，target `main`。
- 核对命令：`tools/check_release_assets.py --tag v0.20.0` → exit 0，四附件齐全，两个 sidecar 与对应 ZIP 摘要一致。
- 四附件逐个列出（未用通配）；摘要与 sidecar 内容、远端 `sha256:` 逐一致：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.20.0-source.zip` | 9 398 084 | `896e03ffbdfa08c4c270e899c672b3812c98a88106cb575097d6f8da44d9c83d` |
| `MCP_CREO_MechDog-0.20.0-source.zip.sha256` | 101 | `091c580a1dbf0001a807802a72923e1e7c3aa5a4f1985b9b25e665299fa8a1ed` |
| `MCP_CREO_MechDog-0.20.0-seed-library.zip` | 493 442 | `6cde6888e80cf9dd9df1d8d86dec33eb308c193d3c5ca8c1e17af98f41ca0697` |
| `MCP_CREO_MechDog-0.20.0-seed-library.zip.sha256` | 107 | `3692847566796970abe5dbc8ca545b0f74458fcb3a134d03657a010f7368d23c` |

- 本版含 `native/*.cpp` 变更（B2/F11、B4/F08）与 B3/F06 进展字段；源码包解压后独立门禁 `Ran 3263 tests ... OK (skipped=5)`。本段只做远端附件与标签核对，不重新验证包内功能；功能验收以 [RELEASE-0.20.0](../validation/RELEASE-0.20.0.md) 与 Release 正文为准。

## v0.23.0（2026-11-12）

- 记录时间：2026-11-12 12:27（+08:00）/ 2026-11-12T04:27Z。`main` = `origin/main` = `0cfd42909f822dda7863f6d5a4c8dcb677f3dfb9`（`c6eb7f7..0cfd429`）；附注标签对象 `1962224cb99e2f860ca9e67b3cf4223ab03f43a3`（`v0.23.0`，指向上述提交）。
- Release：[v0.23.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.23.0)，id `442495969`，非 draft、非 prerelease，`created_at=2026-11-12T04:25:37Z`，`published_at=2026-11-12T04:26:54Z`，target `main`。
- 核对命令：`tools/check_release_assets.py --tag v0.23.0` → exit 0，「v0.23.0: four assets downloaded and verified; both sidecars match」。
- 四附件逐个列出（未用通配）；远端 `sha256:` digest、本地重算与 sidecar 内容逐一致：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.23.0-source.zip` | 9 694 983 | `a8abb957acd5f6989276ff4d5be426e14cc128050566f8507ec3be0656393e7a` |
| `MCP_CREO_MechDog-0.23.0-source.zip.sha256` | 101 | `6a8ac323bd30184acf288c5547fa7217c21782da796f57ba30c22be9989d30ca` |
| `MCP_CREO_MechDog-0.23.0-seed-library.zip` | 493 442 | `5394664c98f0f10777820dda8dd6ab07abf890b8324ec64ff59d662b1f978c0e` |
| `MCP_CREO_MechDog-0.23.0-seed-library.zip.sha256` | 107 | `ffcd1695bb04001a6adbf23556a0167d2ff63dae961cca6b78865482c317f0b5` |

- 本版含 `native/surface_loft.cpp`、`native/surface_boundary_fill.cpp`、`native/generic.cpp`、`native/sketch_coordinates.cpp`、`native/sketch_edit.cpp`、`native/worker.cpp` 变更（FEAT-066、DEV-082），升级后必须重编译 worker。源码包解压到短路径 `E:\r023\MCP_CREO_MechDog`（无 `.git`）后独立门禁 `Ran 3429 tests ... OK (skipped=6)`；首次在 `build/release-check-0.23.0` 深层路径下运行时有 1 项 `test_dev040_blackbox_fixture` 因 Windows 260 字符路径限制报 `Errno 2`，换短路径后通过，非产品缺陷。本段只做远端附件与标签核对，不重新验证包内功能；功能验收与未测范围以 [RELEASE-0.23.0](../validation/RELEASE-0.23.0.md) 与 Release 正文为准。

## v0.22.0（2026-11-11）

- 记录时间：2026-11-12 00:36（+08:00）/ 2026-11-11T16:36Z。`main` = `origin/main` = `2de2fa8d4e48a8ea0dbadb6c7c4cd7058513f280`（`ea753be..2de2fa8`）；附注标签对象 `e2e33bd1423eb33d097016d9cff68ffae3508809`（`v0.22.0`，指向上述提交）。
- Release：[v0.22.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.22.0)，id `441943346`，非 draft、非 prerelease，`created_at=2026-11-11T16:34:20Z`，`published_at=2026-11-11T16:35:24Z`，target `main`。
- 核对命令：`tools/check_release_assets.py --tag v0.22.0` → exit 0，「v0.22.0: four assets downloaded and verified; both sidecars match」。
- 四附件逐个列出（未用通配）；远端 `sha256:` digest、本地重算与 sidecar 内容逐一致：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.22.0-source.zip` | 9 636 010 | `5db68fe932019eebef3ad5b59e8ddc7f38f1f3c35e93122bb014e174a81af3ab` |
| `MCP_CREO_MechDog-0.22.0-source.zip.sha256` | 101 | `3dd87ec404b06cfb86c0171b01681f2914ea83b8e35a0cd23e5eee15ba7f3a42` |
| `MCP_CREO_MechDog-0.22.0-seed-library.zip` | 493 442 | `9fe456f2855fc165984e1bf715effd092f0d088a1551a50bcfda073d316e7743` |
| `MCP_CREO_MechDog-0.22.0-seed-library.zip.sha256` | 107 | `832968dced37a7e889e13ce043d05e51659a5a2935b8cbbf0243d319533e7000` |

- 本版含 `native/surface_group.cpp` 与 `native/surface_loft.cpp` 变更（FEAT-065 M3/M4）；源码包解压后独立门禁 `Ran 3413 tests ... OK (skipped=6)`。本段只做远端附件与标签核对，不重新验证包内功能；功能验收与未测范围以 [RELEASE-0.22.0](../validation/RELEASE-0.22.0.md) 与 Release 正文为准。

## v0.21.1（2026-11-11）

- 记录时间：2026-11-12（DEV-083 补齐历史缺口）。`main` 提交 `8622f1b3d11808d3c9c2cf76ebb1e3c937183a18`（`990c88a..8622f1b`）；附注标签对象 `f2ffc75ed7e95fd66bf7b1150797cd620e554955`（`v0.21.1`，指向上述提交）。
- Release：[v0.21.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.21.1)，id `441312185`，非 draft、非 prerelease，`created_at=2026-11-11T06:30:15Z`，`published_at=2026-11-11T06:31:05Z`，target `main`。
- 核对命令：`tools\check_release_assets.py --tag v0.21.1` → exit 0，「v0.21.1: four assets downloaded and verified; both sidecars match」。
- 四附件逐个列出（未用通配）；数据取自 [RELEASE-0.21.1](../validation/RELEASE-0.21.1.md) 的发布时记录，本轮未联网重下重算：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.21.1-source.zip` | 9 520 388 | `13952311b47b16dd0a6d90d6aca942d14245d660be3ae2e3264816d3a1b07add` |
| `MCP_CREO_MechDog-0.21.1-source.zip.sha256` | 101 | `f11fd5b9eebd620a8aff17131be47a1c65f9dbb52cb30676aaadb193767d4366` |
| `MCP_CREO_MechDog-0.21.1-seed-library.zip` | 493 442 | `49cfe0fdd691fd83796e05dc9a765f10189622d30a2645bbb87b8f42f511a736` |
| `MCP_CREO_MechDog-0.21.1-seed-library.zip.sha256` | 107 | `1ba5e65a6b4155aba788dfb81673e046b1f0d79895998af24633ab0fc2753364` |

- 包内快照与 `main` 的差异：源码包内的 `RELEASE-0.21.1.md`、`RELEASE_NOTES_0.21.1.md` 与 POSTCHECK 均为打包时点内容（当时没有本段）；本段与「源码包解压门禁 3315 项」只存在于 `main`，按冻结规则不回写、不重发已发布附件。本段只做远端附件与标签核对，不重新验证包内功能。

## v0.23.1（2026-11-12）

- 记录时间：2026-11-12（当日发布并回填）。`main` 提交 `3d250ac0340af933f021930db64324d91168d8b0`（`6dfbfba..3d250ac`）；附注标签对象 `fbd6a56e506b65c411919925dea90048c2138000`（`v0.23.1`，指向上述提交）。
- Release：[v0.23.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.23.1)，id `442581848`，非 draft、非 prerelease，`created_at=2026-11-12T06:42:32Z`，`published_at=2026-11-12T06:44:28Z`，target `main`。
- 打包顺序：`tools\package_seeds.py` → 回填 `docs/seed_package.json` → 重建确认摘要不变 → `tools\package.py`（内置发布记录门禁）→ 标签/发布 → `tools\check_release_assets.py --tag v0.23.1`。
- 种子包 SHA256 `46d8d1f5024a05c4585f051bab1243791a7a9149a9eb90e1764a5ec9afb6a926`（24 个文件、9 个种子，两次构建一致）。
- 核对命令：`tools\check_release_assets.py --tag v0.23.1` → exit 0，「four assets downloaded and verified; both sidecars match」；该命令对 ≥ 0.23.1 同时解压源码包运行记录门禁并通过。
- 四附件逐个列出（未用通配）；远端 `sha256:` digest、本地重算与 sidecar 内容逐一致；`source.zip` 的摘要见同名 sidecar，不写入包内：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.23.1-source.zip` | 9 723 011 | `df02e02fe923d92fd75d117373d7b90384dda565ac0f6dad9113f84276e4c100` |
| `MCP_CREO_MechDog-0.23.1-source.zip.sha256` | 101 | `8262fd01179ac6f71c5a5920ea93faf711fad0dcebab6d572dd0a4f33fd4f908` |
| `MCP_CREO_MechDog-0.23.1-seed-library.zip` | 493 442 | `46d8d1f5024a05c4585f051bab1243791a7a9149a9eb90e1764a5ec9afb6a926` |
| `MCP_CREO_MechDog-0.23.1-seed-library.zip.sha256` | 107 | `161c51d454fb47147daa5c92f3a21b181778b1b1b2925d7bd2ad802ba71bca20` |

- 源码包解压到短路径 `E:\r0231` 后，把该目录临时 editable 安装到本机 venv 并运行 `python -m unittest discover -s tests`：`Ran 3443 tests in 396.706s`、`OK (skipped=6)`；随后已把 venv 恢复到 `E:\Projects\MCP_CREO_MechDog`。包内 `test_standard_install_supports_import_from_unrelated_working_directory` 等 5 项依赖“当前源码目录就是安装目录”，未切换安装前会失败，属测试环境约束而非产品缺陷。
- 本版含 `native/surface_loft.cpp`、`src/creo_mechdog/job_projection.py`、`src/creo_mechdog/operation_results.py`、`src/creo_mechdog/release_integrity.py` 与打包工具变更（BUG-119、DEV-083），升级后必须重编译 worker。Creo 12.4.0.0 实机：已有实体模型放样 8 项、YZ/XZ 正交平面 13 项、guides 回归 38 项全 PASS（报告见 `docs/validation/RELEASE-0.23.1.md`）。
- 包内快照与 `main` 的差异：源码包内的 POSTCHECK、`RELEASE-0.23.1.md`、`RELEASE_NOTES_0.23.1.md` 与 BACKLOG 是打包时点内容（当时没有本段与实际 Release id/时间）；本段、源码包全量单测与远端核对结果只存在于 `main`，按冻结规则不回写、不重发已发布附件。

## v0.23.2（2026-11-13）

- 版本与范围：`0.23.2` PATCH，公开工具仍 107；交付 [BUG-120](../work-items/BUG-120.md) 的 `surface_loft` 提取失败诊断与运行期观测披露，以及 [DEV-083](../work-items/DEV-083.md) 的逐 ID 状态一致性与发布文档本地链接门禁，发布记录见 [RELEASE-0.23.2](../validation/RELEASE-0.23.2.md)。
- 打包顺序：`tools\package_seeds.py` → 回填 `docs/seed_package.json` → 重建确认摘要不变 → `tools\package.py`（内置发布记录门禁）→ 标签/发布 → `tools\check_release_assets.py --tag v0.23.2`。
- 种子包 SHA256 `4a47a58293f773d530c7ab2a771db075f3557222a207fb5dcff853594e66861a`（24 个文件、9 个种子、493 442 字节，两次构建摘要一致）。
- 源码包 `MCP_CREO_MechDog-0.23.2-source.zip` 由本提交源码构建，`package.py` 的四附件门禁与发布记录门禁均通过；字节数与 SHA256 见同名 sidecar，不写入包内文件。
- Release 地址：`https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.23.2`；四附件为 `MCP_CREO_MechDog-0.23.2-source.zip`、`MCP_CREO_MechDog-0.23.2-source.zip.sha256`、`MCP_CREO_MechDog-0.23.2-seed-library.zip` 与 `MCP_CREO_MechDog-0.23.2-seed-library.zip.sha256`；`source.zip` 的摘要见同名 sidecar，不写入包内。
- 核对命令 `tools\check_release_assets.py --tag v0.23.2` 需 exit 0；该版本 ≥ 0.23.1，会同时解压源码包运行记录门禁。实际标签对象、`main` 提交、Release id、发布时间与四附件名称/字节/SHA256 在发布后补记于本段，已发布附件不重传。
- 本批未连接 Creo（未取得本轮当次实机授权），按离线批次发布：Creo 12.4.0.0 实机回归与 `kernel_completion="supported"` 观测未执行，0.23.1 实机结论不外推。升级后必须重新编译 worker（`native/surface_loft.cpp` 变更）。
- 离线验证：`tools\dev_check.py --work-item BUG-120` 为 `success=true`（`Ran 3463 tests`、`OK`）；源码包解压到 `E:\r0232` 后切换 editable 安装运行全量单测为 `Ran 3463 tests in 479.169s`、`OK (skipped=6)`、exit 0，随后已恢复本机 venv 安装。
- 包内快照与 `main` 的差异：源码包内的本段、`RELEASE-0.23.2.md`、`RELEASE_NOTES_0.23.2.md` 与 BACKLOG 是打包时点内容；实际 Release id、发布时间与发布后核对只存在于 `main`，按冻结规则不回写已发布附件。

## 未覆盖

- 本核对只证明**远端附件与 sidecar、摘要三者一致**，不重新验证包内功能、Creo 实机或安装结果；这些结论分别属于各版 `docs/validation/RELEASE-*.md` 的实际范围。
- 只核对 GitHub Release 平台对象；镜像、本地下载缓存和客户端侧校验不在本文件范围。
- 本文件为首次补记，未回改 v0.17.4/v0.18.0/v0.18.1 已发布附件或原发布记录中的日期与结论。
