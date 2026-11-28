# 0.48.3 反馈：JSON 原子替换把瞬时 WinError 5 误判为永久 ACL 失败，全量单测偶发 2 errors

- 反馈日期：2026-11-27
- 版本：`MCP_CREO_MechDog` **0.48.3**（`main@f2827a86`，tag `v0.48.3`，工具数 112）
- 反馈性质：本项目自身代码的健壮性缺陷（非 Toolkit SDK / 许可 / 用户环境等客观原因；环境只是触发条件）
- 关联：`DEV-066` 第 5 条已登记 `lock_files.py` 的 `open_lock_file` 初始 `OPEN_EXISTING` 瞬时 WinError 5 未兜底（低优先级建议），本反馈为**同类问题在 `bridge.write_json`/`_replace_json` 的又一次实际触发**，建议合并评估 Windows 文件锁的容错策略。

## 一、现象

本机按标准流程升级到 0.48.3 后，运行 `tools/test_unit.py` 全量单测：

| 轮次 | 结果 | 耗时 | run_id |
|---|---|---|---|
| 首轮 | **4578 项 / 0 failures / 2 errors / 4 skipped / exit 1** | 1975.8 s | `bd8431944446473498afeeeffd43aadb` |
| 重跑（仅重跑，未改任何代码/环境） | 4578 项 / 0 failures / 0 errors / 4 skipped / **exit 0** | 1763.9 s | `c1135e52213a4c89aa8eb9c7068a6678` |

两轮 report 与 run state 的 run_id / version / success 均自洽。首轮 2 个 error 均为同一用例：

```
ERROR: test_unknown_reservation_still_rejects_loft_without_callback_or_replay
  (unit.test_callback_admission.CallbackAdmission.test_unknown_reservation_still_rejects_loft_without_callback_or_replay)
```

该用例在 `unittest` 输出中出现两次 ERROR（一次测试体失败、一次 `TemporaryDirectory` cleanup 失败），因此 error 计数为 2。

## 二、错误堆栈与直接原因

```text
File "...\tests\unit\test_callback_admission.py", line 67, in test_...
  first = self.submit()
File "...\tests\unit\test_toolkit_channel.py", line 67, in submit
  return general.submit([], **kwargs)
File "...\src\creo_mechdog\generic_bridge.py", line 1852, in submit
  bridge.write_json(directory / "job.json", manifest)
File "...\src\creo_mechdog\bridge.py", line 311, in write_json
  _replace_json(temp, path)
File "...\src\creo_mechdog\bridge.py", line 276, in _replace_json
  _atomic_replace(temp, path)
PermissionError: [WinError 5] 拒绝访问。:
  '...\.tmp\bug009_b6ed5awp\jobs\8eb1d6916a7a4d87854e435cb2e63273\.ad30d37dba494751ab840552da4d6cd8.tmp'
  -> '...\.tmp\bug009_b6ed5awp\jobs\8eb1d6916a7a4d87854e435cb2e63273\job.json'
JSON atomic replace failed: ...\job.json; attempts=1; budget=1.0s
Could not remove this writer's temporary file ...\.ad30d37dba494751ab840552da4d6cd8.tmp: [WinError 5] 拒绝访问。
```

cleanup 阶段的第二个 ERROR：

```text
File "...\tempfile.py", line 910, in onexc
  _os.unlink(path)
PermissionError: [WinError 5] 拒绝访问。: '...\.ad30d37dba494751ab840552da4d6cd8.tmp'
```

首轮结束后，该 `.tmp` 文件实际仍留在磁盘上（`job.json` 已存在、1098 字节的 `.tmp` 未被删除），说明失败时目标文件与临时文件同时处于被外部句柄短暂锁定的状态。

## 三、根因分析（指向本项目代码）

关注 `src/creo_mechdog/bridge.py` 的 `_replace_json()`：

```python
JSON_REPLACE_TIMEOUT = 1.0          # line 166
JSON_REPLACE_MAX_ATTEMPTS = 25      # line 167

def _replace_json(temp, path):
    deadline = time.monotonic() + JSON_REPLACE_TIMEOUT
    delay = 0.005
    for attempt in range(1, JSON_REPLACE_MAX_ATTEMPTS + 1):
        try:
            _atomic_replace(temp, path)
            return
        except OSError as exc:
            winerror = getattr(exc, "winerror", None)
            retryable = os.name == "nt" and winerror in (5, 32, 33)
            if retryable and winerror == 5:
                try:
                    retryable = not (path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
                except OSError:
                    retryable = False
            remaining = deadline - time.monotonic()
            if not retryable or remaining <= 0 or attempt == JSON_REPLACE_MAX_ATTEMPTS:
                exc.add_note(...); raise
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, 0.05)
```

存在两个可改进之处：

1. **瞬时外部句柄锁被误判为永久 ACL / 只读失败**：日志明确是 `attempts=1` 就放弃重试。WinError 5 在 Windows 上既可能是永久 ACL/只读，也可能是杀毒软件、文件索引器、后台扫描进程短暂持有句柄。当前用 `path.stat().st_file_attributes` 判断只读：若 `stat` 本身因同一把外部锁失败（`except OSError: retryable = False`），就直接判为不可重试；即便 `stat` 成功，目标文件 `job.json` 本身不是只读，真正的锁在 `.tmp` 源文件上，判断对象也不对。于是 25 次重试和 1 秒预算在 `attempts=1` 时完全没用上。
2. **总预算仅 1.0 秒偏紧**：即使进入重试，杀软/索引器持有句柄常超过 1 秒；`delay` 从 5 ms 指数退避到 50 ms，25 次累计睡眠远不足 1 秒，实际会被 `remaining <= 0` 提前截断。

建议（供作者评估）：

- 将 WinError 5 的"永久只读"判定改为**只依据 `FILE_ATTRIBUTE_READONLY` 且 `stat` 成功时**才判永久；`stat` 失败时**按可重试处理**，而不是反过来判不可重试；并把只读检查对象覆盖到 `temp` 与 `path` 两者。
- 把 `JSON_REPLACE_TIMEOUT` 提到数秒量级（例如 3–5 s），或按重试次数/文件重要性做可配置预算；保留 `attempts` 上限防止死循环。
- cleanup 阶段对 `.tmp` 残留增加有限重试或延迟清理，避免一次瞬时锁就在磁盘留下垃圾并制造第二个 ERROR。
- 与 `DEV-066` 第 5 条 `lock_files.py` 的 WinError 5 兜底合并为统一的 Windows 文件锁容错策略。

## 四、可复现性与"非产品缺陷"边界（如实披露）

- 首轮失败用例相关文件在本版（0.48.1→0.48.3）**均未改动**：`tests/unit/test_callback_admission.py`、`tests/unit/test_toolkit_channel.py`、`src/creo_mechdog/generic_bridge.py`、`src/creo_mechdog/bridge.py` 的 diff 为空。
- 全测期间 `ps` 检查无 Creo / worker / nmsd 进程占用；错误发生在纯 Python 单测的临时目录。
- 单跑该用例 **5/5 通过**（3.7–4.3 s）；跑整个 `CallbackAdmission` 类 **5/5 通过**；重跑全量单测 **全绿**。因此这不是稳定的功能回归，而是 **Windows 文件锁导致的偶发失败**。
- 触发条件是外部环境瞬时持有句柄（本机为 Windows 10 + WorkBuddy 常驻环境，可能有杀软/索引器扫描 `.tmp`），**但直接导致测试失败的是本项目对 WinError 5 的错误分类与过短重试预算**——外部锁是诱因，代码健壮性不足是内因，故按"项目自身问题"反馈。

## 五、本版其余验证（全部通过，供参考）

- 依赖/安装器/`pyproject.toml` 无变化；`pip install --no-deps --editable .` 升级到 0.48.3；`seeds.py --install` 完成（种子清单 `compatible_server_version` 0.48.1→0.48.3，摘要 `2f392cb4…`）。
- 本版无 native 代码改动，`bridge.py build` 幂等 exit 0，执行器沿用。
- stdio 冒烟 3 组全 exit 0：`--protocol-only` / `--offline` / `--protocol-only --legacy-entry`，均 `tool_count=112`、`capability_contract_verified=true`、`capability_pages=3`。
- 新增门禁：`tools/check_doc_links.py` 扫描 308 文件 / 3132 链接，`broken_files=[]`、`broken_anchors=[]`、`consistent=true`；`tools/check_backlog_counts.py` 按状态分组一致（含 `开发中=0`）、`problems=[]`。

## 六、未测范围

- Creo 9 / 10 / 12.4 实机建模与外部 WorkBuddy 黑盒验收（本轮未连接 Creo 会话）。
- 未在 GitHub 托管 Windows CI 上复现本 flaky（作者 0.48.2/0.48.3 发布说明记录 CI 首轮也曾出现一项启动重试 ID 断言失败、次轮通过，已于 0.48.3 由 DEV-108 修复；本反馈的 `_replace_json` WinError 5 与之不是同一处）。
