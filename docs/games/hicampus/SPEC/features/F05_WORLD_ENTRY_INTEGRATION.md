# F05 - World Entry Integration

## Goal

在 `SingularityRoom` 提供 `HiCampus` 世界入口对象，实现安全进入与失败回退。

## Scope

- 入口对象规范（内部实现可用 `world_portal_hicampus`，但用户可见名称为 `hicampus`）
- 进入 `hicampus_gate` 路径
- 世界内最小导航路径：`hicampus_gate --(n)--> hicampus_bridge`
- 数据缺失/加载失败 fallback

## UX Contract

- 流程：`world install hicampus` -> 奇点屋 `look` 可见 `hicampus` -> `enter hicampus` -> `look` 见 `hicampus_gate` -> `n` 到 `hicampus_bridge`
- `look hicampus` 必须展示 DB 中 `world` 本体 node 的描述（不是入口投影文案），并给出提示：`enter hicampus`
- `hicampus` 对象语义类似公告栏（可 `look`），差异是 world 额外支持 `enter`
- `world_portal_*` 仅作为内部映射机制，不在用户可见层（look/提示文案）直接出现。

## Runtime Contract

- `world install hicampus` 成功后，入口可见状态同步为启用（奇点屋内可见）。
- `world uninstall hicampus` 成功后，入口可见状态同步为禁用（奇点屋内不可见）。
- `world reload hicampus` 成功后，入口状态与世界配置重新同步。
- 失败错误码建议：
  - `WORLD_ENTRY_PORTAL_MISSING`
  - `WORLD_ENTRY_PORTAL_DISABLED`
  - `WORLD_ENTRY_FORBIDDEN`
  - `WORLD_ENTRY_GAME_UNAVAILABLE`
  - `WORLD_ENTRY_FAILED`

## Out of Scope

- 世界安装命令实现（见 `F04`）
- 拓扑修复能力（见 `F06`）

## Dependencies

- 前置：`F03`
- 可并行：与 `F04` 并行开发，后期联调

## DoD

- 用户在奇点屋 `look` 可见 `hicampus` 入口项
- 用户可从奇点屋 `enter hicampus` 进入 `hicampus_gate`
- 用户执行 `n` 可到达 `hicampus_bridge`
- 失败时返回奇点屋并给出可读提示
- 入口对象不破坏现有系统入口稳定性
