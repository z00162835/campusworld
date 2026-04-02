# HiCampus 内容资产说明（F07）

## 主包 YAML

`../buildings.yaml`、`../floors.yaml`、`../rooms.yaml` 已包含空间叙事 **P0** 字段（与 `Room` / `Building` / `BuildingFloor` 模型键对齐）。图种子会把除 `id`、`type_code`、`display_name`、`tags` 外的键写入节点 `attributes`。

## 可选侧车 `descriptions/`

目录：`content/descriptions/`（与本 README 同级下的 `descriptions` 子目录）。

- `buildings.yaml` → 根键 `buildings:`，每行至少含 `id`，其余键合并进对应建筑行。
- `floors.yaml` → `floors:`
- `rooms.yaml` → `rooms:`

侧车 **id 必须已存在于主包**，用于在不改动结构的前提下迭代长文案。校验在合并后执行 **P0 门禁**。

## 版本

`package_meta.yaml` 中 `content_revision` 为内容修订号，与 Git 标签或 CHANGELOG 对齐；回滚流程见 `F07_SPATIAL_DESCRIPTION_CONTENT_PACK.md`。

## 楼层索引

主包可使用 `floor_no`；校验前会归一并写入 **`floor_number`**。建筑的 `floors_total` 会同步为属性 **`building_floors`**（若未显式写出）。
