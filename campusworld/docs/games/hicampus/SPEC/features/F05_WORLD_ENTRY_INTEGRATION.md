# F05 - World Entry Integration

## Goal

在 `SingularityRoom` 提供 `HiCampus` 世界入口对象，实现安全进入与失败回退。

## Scope

- 入口对象规范（`world_portal_hicampus`）
- 进入 `hicampus_gate` 路径
- 数据缺失/加载失败 fallback

## Out of Scope

- 世界安装命令实现（见 `F04`）
- 拓扑修复能力（见 `F06`）

## Dependencies

- 前置：`F03`
- 可并行：与 `F04` 并行开发，后期联调

## DoD

- 用户可从奇点屋进入 HiCampus
- 失败时返回奇点屋并给出可读提示
- 入口对象不破坏现有系统入口稳定性
