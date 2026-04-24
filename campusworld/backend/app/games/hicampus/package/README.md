# HiCampus `package/` — 数据生成与校验

在 **`backend/`** 目录下执行（需已安装项目依赖）。所有模块使用默认的 `data/` 根目录：`app/games/hicampus/data/`。

## 推荐流水线（改 YAML / 模板后刷新包）

1. **`spatial_generate`**（可选）  
   从 `spatial_profiles.yaml`、空间原型等重写 `floors.yaml`、`rooms.yaml`。  
   ```bash
   python -m app.games.hicampus.package.spatial_generate --write
   ```

2. **`topology_connect_generate`**  
   生成各层交通核房间（`*_circulation_01`）、层内与竖向 `up`/`down` 的 `connects_to`；**保留**少量手工「脊线」关系 id，其余 `connects_to` 由生成器覆盖。  
   ```bash
   python -m app.games.hicampus.package.topology_connect_generate --write
   ```  
   - 保留 id 集合见 `topology_connect_generate.py` 中的 `PRESERVE_CONNECT_IDS`。  
   - 自动生成的连边带 `attributes.topology_auto: true`（便于排查；勿依赖其在内行为）。

3. **`entity_item_generate`**（可选，改了 `item_templates` / `item_placement_rules` / 房间集后）  
   ```bash
   python -m app.games.hicampus.package.entity_item_generate --write
   ```

4. **`entity_relationship_generate`**  
   合并 `located_in`（等物品/NPC 定位关系），**不**删除已有 `connects_to`。  
   ```bash
   python -m app.games.hicampus.package.entity_relationship_generate --write
   ```

5. **载入图库**  
   内（管理员）：`world reload hicampus`；首次为 `world install hicampus`。需 `manifest.yaml` 中 `graph_seed: true` 且 PostgreSQL 可用。

**顺序要点**：拓扑与物品可反复调整；若刚跑过 `topology_connect_generate`，建议再跑 `entity_relationship_generate`，保证新房间上的物品有 `located_in`。

## 其他模块

- **`validator.py`**：F02 数据包校验；由 `GameLoader` 在 load/reload 时调用。  
- **`graph_profile.py`**：F03 图种子允许的关系类型等。  
- **`content_merge` / `content_overlay`**：F07 等内容侧车合并（见 `data/content/README.md`）。

## 规格索引

- 包布局与契约：`docs/games/hicampus/SPEC/features/F02_WORLD_DATA_PACKAGE.md`  
- 图种子：`F03_GRAPH_SEED_PIPELINE.md`  
- 拓扑校验/修复：`F06_TOPOLOGY_VALIDATE_REPAIR.md`
