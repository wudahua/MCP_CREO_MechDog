# FEAT-094 向已有零件追加放样与 7 截面/导线放样能力

分类：**部分交付，剩余待规划**。功能，P2，基线为 v0.49.0 发布后回填提交 `949c7f6b`（衔接 `BUG-154` / `BUG-206`）。

来源：[0.48.3 反馈原件](../validation/feedback-0.48.3-2026-11-28/originals/recovery-and-modeling.md)（P3/P4）与 [weld-and-loft.md](../validation/feedback-0.48.3-2026-11-28/originals/weld-and-loft.md)（§3.3）。

## 交付与边界（0.50.0）

- 通过 `BUG-206` 与 `BUG-204` 明确划定 `creo_new_loft_part`（`new_part_only`、不可追加到已有零件）与已有零件 `creo_loft`（需已加载的常驻回调）两类入口边界与前置报错指引。
- 单测验证回调未就绪时 `creo_loft` 在已有零件上的零锁拒绝及提示一致。

## 剩余待验收 / 待规划

- 在交互桌面手动启动 Creo 10 回调后，实机补验同一 `model_id` 上 `creo_loft` 追加 Blend（原特征保留、`revision` 推进、保存重载与失败回滚）。
- 免回调向已有零件追加放样，以及 7 截面 / 带导线实心放样能力仍待后续独立规划与 SDK 评估。
