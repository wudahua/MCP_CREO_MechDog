# FEAT-014 四壁盒子实现路线：折边 Miter Cuts（调研定稿，供主会话实施）

> 状态：2026-11-06 调研定稿，代码未动。所有结论基于本机 Creo 12.4.0.0 SDK 头文件与 2026-11-06 实机证据（`build/post090_n05_live_20261106T1505/report.json`，FEAT-014 卡 2026-11-06 节）。

## ⚠️ 版本注意（先处理再动代码）

- **0.15.0 已由主会话发布**。本分支工作树里还有一批**未提交的本地版本号改动**，发布前写的，可能与已发布内容冲突，不得盲目提交：
  - `version.py`（本地改成了 0.15.0）
  - `README.md`（标题/当前版本段/版本说明链接）
  - `seed_library/seed_manifest.json`、`docs/seed_manifest.json`（`compatible_server_version`）
  - `docs/seed_package.json`（digest 回填为 `0954faaa…`）
  - `build/release_0_15_0/`（本地重建的种子包，未发布）
- 处理建议：先核对远端 `v0.15.0` 已含内容，把这批本地版本号改动 **revert 或与实际发布对齐**；`build/` 下的包不要当发布产物。
- 本分支已提交的 `4201f84`（connect 计时）等是否已进入 0.15.0 发布范围，需核对合并提交；没进去的就留给下一个版本。

## 一、现状与根因

实机证据（2026-11-06）：第三面壁在 `before_create` 被 `adjacent_bend_ends` 保护拒绝，特征根本没创建：

- 1 角上下文：附着边 span 181.46 / 期望 185（单端邻接折弯弧）。
- 2 角上下文：span 177.92 / 185（两端邻接，弧 R2.54，折弯界限 7.081）。
- `end_trim_mm` 实测是空操作（`trim_ignored`，两墙体积完全相同），不能用来让位。

拒绝逻辑：`native/advanced.cpp` 的 `flange_adjacent_bend_end_evidence`（约 L1215-1380）计算 `bound = 2*(radius+thickness)+1e-3`，用 `ProEdgeVertexdataGet` 枚举附着边两端的所有邻接边，任一端命中"弧半径 ≤ bound 且邻接圆柱面（折弯面）"即出证据；`generic_sheetmetal_flange`（约 L1515-1538）见到证据就抛错拒绝。

这不是几何建不出来，是保护把"折弯圆角吃掉附着边端部一小段"这个**正常情况**当成危险。SDK 有原生解法（见下），所以路线是：**显式请求 miter cuts 时放行保护 + 在折边元素树里让 Creo 自己切掉端部重叠**。

## 二、SDK 契约（已核对头文件）

`ProSmtFlangeWall.h`（generic.cpp L51 已 include，advanced.cpp 是 unity build：`worker.cpp` L315 → `generic.cpp` L3417 → `advanced.cpp`，**不需要新增 #include**）：

```text
PRO_E_SMT_MTR_CUTS                    Miter Cuts            Compound
  PRO_E_SMT_MTR_CUTS_ADD              Add Miter Cuts        PRO_VALUE_TYPE_INT    (PRO_B_TRUE/FALSE)
  PRO_E_SMT_MTR_CUTS_KEEP_DEF_AREAS   Keep Deformation Areas  PRO_VALUE_TYPE_INT
  PRO_E_SMT_MTR_CUTS_WIDTH            Compound
    PRO_E_SMT_MTR_CUTS_WIDTH_TYPE     ProMiterCutWidthType
    PRO_E_SMT_MTR_CUTS_WIDTH_VAL      PRO_VALUE_TYPE_DOUBLE
  PRO_E_SMT_MTR_CUTS_OFFSET           Compound
    PRO_E_SMT_MTR_CUTS_OFFSET_TYPE    ProMiterCutOffsetType
    PRO_E_SMT_MTR_CUTS_OFFSET_VAL     PRO_VALUE_TYPE_DOUBLE
```

类型枚举（同头文件 L527-542）：

- `ProMiterCutWidthType`：`BLIND = PRO_DIM_ENTER = -4`、`GAP = PRO_DIM_SMT_GAP = -22`、`PARAM = -18`
- `ProMiterCutOffsetType`：同样三值。

**选 GAP 型**（间隙）：切角后留一道间隙，这是盒子角落的自然语义，值就是 mm 数。

另有独立角部特征 `ProSmtCornerRelief.h`（`PRO_FEAT_SMT_CRN_REL`），但需要"平面 + 两条折弯圆柱面"三引用，建完墙后还要找角部引用，复杂度高——**不用这条路线**，Miter Cuts 跟墙一起建，一步到位。

## 三、原生改动（native/advanced.cpp）

### 1. 新增请求解析（放在 `flange_relief_request` 之后，约 L830 附近，仿照它的风格）

```cpp
struct FlangeMiterRequest {
    bool requested = false;
    double width = 0;   // gap 宽度 mm
    double offset = 0;  // gap 偏移 mm
};

static FlangeMiterRequest flange_miter_request(const J &op) {
    FlangeMiterRequest request;
    if (!op.contains("miter_cuts") || op.at("miter_cuts").is_null())
        return request;
    const J &mtr = op.at("miter_cuts");
    if (!mtr.is_object())
        throw std::runtime_error("miter_cuts must be an object with width and offset in model units");
    request.requested = true;
    if (!mtr.contains("width"))
        throw std::runtime_error("miter_cuts requires width (>0) in model units");
    request.width = mtr.at("width").get<double>();
    // 数字校验仿 relief：拒绝 bool，width > 0
    request.offset = mtr.contains("offset") ? mtr.at("offset").get<double>() : request.width;
    if (!(request.width > 0))
        throw std::runtime_error("miter_cuts width must be greater than zero");
    if (!(request.offset >= 0))
        throw std::runtime_error("miter_cuts offset must be zero or greater");
    return request;
}
```

### 2. guard 放行（`generic_sheetmetal_flange` 约 L1515-1538）

把现在的"见证据就抛错"改为：

```cpp
FlangeMiterRequest miter = flange_miter_request(op);   // 放在函数最前，与 relief_request 并列
{
    J adjacency = flange_adjacent_bend_end_evidence(op);
    if (!adjacency.empty() && !miter.requested) {
        // 现有拒绝路径原样保留，错误文案更新一句：
        // "...no miter route is implemented" 改为
        // "To build a wall whose ends meet existing bends, pass miter_cuts {width, offset}
        //  (FEAT-014); without it the adjacent guard refuses the wall before submission."
    }
    if (!adjacency.empty() && miter.requested) {
        // 不抛错。记录放行证据，带到结果里：
        adjacency["failure_reason"] = "adjacent_bend_ends";
        adjacency["allowed_by_miter_cut"] = true;
        log("FLANGE_ADJACENT_BEND_ALLOWED edge=%d miter=on\n", adjacency["edge_id"].get<int>());
        // 存到局部变量，create 成功后并入 extra
    }
}
```

**默认行为不变**：不带 `miter_cuts` 的请求依旧被拒。

### 3. 元素树（约 L1641-1645，`PRO_E_SMT_BEND_RELIEF` 两侧设置完之后）

```cpp
if (miter.requested) {
    ProElement mtr = node(root, PRO_E_SMT_MTR_CUTS);
    integer(mtr, PRO_E_SMT_MTR_CUTS_ADD, PRO_B_TRUE);
    integer(node(mtr, PRO_E_SMT_MTR_CUTS_WIDTH), PRO_E_SMT_MTR_CUTS_WIDTH_TYPE,
            PRO_MITER_CUT_WIDTH_TYPE_GAP);
    real(node(mtr, PRO_E_SMT_MTR_CUTS_WIDTH), PRO_E_SMT_MTR_CUTS_WIDTH_VAL, miter.width);
    integer(node(mtr, PRO_E_SMT_MTR_CUTS_OFFSET), PRO_E_SMT_MTR_CUTS_OFFSET_TYPE,
            PRO_MITER_CUT_OFFSET_TYPE_GAP);
    real(node(mtr, PRO_E_SMT_MTR_CUTS_OFFSET), PRO_E_SMT_MTR_CUTS_OFFSET_VAL, miter.offset);
}
```

`PRO_E_SMT_MTR_CUTS_KEEP_DEF_AREAS` 先不设（树注释标 optional）；如果 create 报元素缺失，从 `flange_tree_evidence` 的失败树里能看到，再补。

### 4. 回显（约 L1671-1689，仿 relief echo）

create 成功、regenerate 通过后，从已建特征树抽回 `PRO_E_SMT_MTR_CUTS` 段，核对 ADD=TRUE、WIDTH_TYPE=GAP(-22)、WIDTH_VAL、OFFSET_TYPE、OFFSET_VAL 与请求一致，不一致就抛错（防 Creo 静默重置，同 T11 relief 的教训）。然后并入结果：

```cpp
extra["miter_cuts"] = {{"requested", true},
                       {"add", add_echo},
                       {"width_type", width_type_echo}, {"width_mm", width_val_echo},
                       {"offset_type", offset_type_echo}, {"offset_mm", offset_val_echo}};
if (adjacency_allowed)
    extra["adjacent_bend_ends_allowed"] = adjacency;   // 带 allowed_by_miter_cut=true
```

## 四、Python 契约

### 1. `src/creo_mechdog/schema.py`（`FlangeRelief` 之后，约 L1024）

```python
class FlangeMiterCuts(StrictModel):
    # FEAT-014 / R09 第4项。折边创建时的原生 miter cuts（ProSmtFlangeWall.h
    # PRO_E_SMT_MTR_CUTS，GAP 型宽度与偏移）。附着边端部与既有折弯相邻时必须
    # 提供，才能通过 adjacent_bend_ends 保护；否则该保护照旧拒绝。
    # gap 语义（从每个链端回切多少）是实测量，不用本字段本身宣称几何结果。
    width: Annotated[float, Field(gt=0, le=100000)]
    offset: Annotated[float, Field(ge=0, le=100000)] | None = None

    @field_validator("width", "offset", mode="before")
    @classmethod
    def numeric_dimension(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("miter_cuts width and offset are numbers of model units, not booleans")
        return value

    @model_validator(mode="after")
    def miter_valid(self):
        if self.offset is None:
            self.offset = self.width
        return self
```

`SheetmetalFlangeOp`（约 L1043）加：`miter_cuts: FlangeMiterCuts | None = None`，注释说明与 guard 的关系。

### 2. 文案（三处口径一致）

- `src/creo_mechdog/capabilities.py` L645-652：改为"relief 仍是 bend-end relief；附着边端部邻接折弯的壁需 `miter_cuts`（GAP 型宽度/偏移）才能创建，四壁盒子经 miter cuts 路线支持"。
- `server.py` L1843-1865 `creo_sheetmetal_flange` 描述：同步，去掉"四壁盒子尚未支持"的绝对说法，改为"需 miter_cuts"。
- `docs/work-items/FEAT-014.md`、`docs/development/CODING_STANDARD` 无关不动；REFERENCE_SYNTAX 如有 flange relief 段一并补。

### 3. 投影白名单（实施时核对）

R04 的 compact 投影（`src/creo_mechdog/job_projection.py` / `operation_results.py`）按白名单裁字段。新增的 `miter_cuts`、`adjacent_bend_ends_allowed` 两个 extra 键要确认 compact 下可见（失败上下文/关键判据不能被静默裁掉），不在白名单就加。注意：`grep relief` 在 operation_results.py 无命中，说明它可能是按 operation 级白名单通用处理，实施时以实际代码为准。

## 五、测试

### 离线（`tests/unit/test_sheetmetal_flange.py`）

- schema：`miter_cuts` 合法（width+offset / 只 width 默认 offset=width）；bool 拒绝；width≤0 / offset<0 拒绝；与 `relief` 正交（可同时提供）。
- 契约：`test_sheetmetal_flange.py` L1368-1374 现有"不声称四壁/corner relief"的断言要改写成新口径（四壁经 miter cuts 支持，corner relief 独立特征仍不做）。
- 可选源码契约测试（仿 `test_native_stage.py`）：断言 guard 放行分支存在且仅在 `miter.requested` 时触发。

### 实机（`tools/test_sheetmetal_box_live.py` 加 case）

1. **语义探针先行**（吸取 `end_trim_mm` 教训）：自由首壁上带 `miter_cuts`（width=thickness, offset=thickness）建一堵墙，量体积/bbox 定标 GAP 语义，确认"回切量"与请求值的关系；不带 miter 的对照墙同参数。
2. **四壁主场景**：底板 → 墙1（自由）→ 墙2（自由端）→ 墙3 带 `miter_cuts`（原来被拒的位置）→ 墙4 带 `miter_cuts`；每墙独立 job、失败不重交。
3. 验收：每墙 `saved_file_reloaded_and_verified=true`；体积 oracle（四面盒子的理论体积按实测定标后比对）；`four_walls_complete=true`；回显 `miter_cuts` 与请求一致。
4. 建议起始 gap 值：width = 板厚（1 mm 案例即 1），不够再调；把实测关系写进 FEAT-014 卡，不在 schema 文档里预写未实测的几何承诺。

## 六、风险与未决

| 风险 | 处置 |
| --- | --- |
| GAP 型是否必须有 `_VAL` 元素 | 树里 TYPE+VAL 都设；create 失败看 `flange_tree_evidence` 的元素错误列表 |
| `KEEP_DEF_AREAS` 省略后 Creo 填默认 | 回显核对会暴露；必要时显式设 PRO_B_FALSE 再看 |
| miter width/offset 的实测语义未知（同 end_trim 教训） | 语义探针先行定标；回执只报请求+回显，不宣称几何 |
| 放行后 regenerate 仍失败（如第 5 副本类未知场景） | 失败照旧走回滚+`flange_failure_evidence`，不掩盖 |
| 0.15.0 已发布，本地版本号改动冲突 | **先处理第一节再动代码** |
