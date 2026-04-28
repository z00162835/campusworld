# `space`

> **Architecture Role**: 只读**空间信息查询**（**SYSTEM** 命令）。用户或 Agent 按图节点 `id` 拉取**空间**（`trait_class: SPACE` 之 `building` / `building_floor` / `room` 等）的**分段摘要**：与 `look` 对齐的**环境描述**（无房内对象列表）、**占用者**、**设备**、**下一层/联通**空间列表。  
> **终端展示**：`CommandResult.message` 须为 **类 `look` 的多段纯文本**；**每一段**在节标题之下均须**按「对象/条目行」列表**罗列（**一行**一条可独立计数的内容；**段 2–4** 一图节点一行、**段 1** 须拆成多行不得整段无换行长文，见 **「对象行列表」**）**。**段 1** 为空间语义/出口等**对象行**；**段 2–4** 为**表格/对象行**并含 `id`。**禁止**以 **JSON 串或整块 JSON** 作成功主呈现；**机器负载**在 `CommandResult.data`（见下），与 [`protocols/CLAUDE.md`](../../../../backend/app/protocols/CLAUDE.md) 一致。  
> 实现与注册表路径见下 **Metadata**；`export_command_registry_snapshot` 与 `verify_command_spec_files` 用于对账。

## 空间关联真源（Evennia 式 `location_id` 链）

参考 Evennia 的 **单父 `location` 链**：CampusWorld 中 **空间层级（谁包含谁）** 的**契约真源**为图节点表上的 **`Node.location_id`** 指向**唯一父空间**（子查询：`WHERE location_id = :当前空间 id` 且子节点为期望的 `type_code`）。**不在此层级上用 `connects_to` 或全连接成对边**去表达「建筑/楼层/房间」的包含关系，否则会出现**边膨胀**，并与**行走邻接**语义混淆。

- **包含（`building` → `building_floor` → `room`）**：种子与运行时内容应通过 **`location_id` 链** 维护；图种子写入顺序与字段约定见 [graph_seed/pipeline](../../../../backend/app/game_engine/graph_seed/pipeline.py)（`building` 的父可为 `world` 等顶层空间节点，视包结构而定；子楼层、子房间依次指向直接父级）。
- **邻接（仅 `room` ↔ `room`）**：可通行/出口拓扑使用**稀疏**的 **`connects_to`** 边，**真源与解析**与 [`LookCommand`](../../../../backend/app/commands/game/look_command.py) 一致（实现应复用与 `look` 共用的 `connects_to` 查询，见 [`room_connects_to_query.py`](../../../../backend/app/commands/room_connects_to_query.py)）。

**反模式（SPEC 层禁止作为稳定契约）**：

- 用 **`connects_to`（或任意成对图边密铺）** 表达 **非邻接的父子包含**（建筑/楼层/房间层级）。
- 在 **`space` 中重复实现** 一套与 `look` 不一致的 **`connects_to` 方向/去重/过滤** 规则（双真源）。

### 技术债与过渡期

若某环境或历史包中 **子空间的 `location_id` 尚未写入**（仅 `attributes` 中 `building_id` / `floor_id` 等），实现**可**在命令层对 **段 4（`building` / `building_floor`）** 使用与包字段一致的**次选**查询作为回退，并须在代码注释中标注；**目标收束**为图种子/迁移完成后**仅依赖 `location_id`**. **弃用策略**：新装世界以种子写入 `location_id` 为准；次选路径便于过渡，不写入本 SPEC 的长期契约。包内与层级并存的 **`contains` 类关系**若与 `location_id` 并存，**展示与 `space` 以 `location_id` 为优先**（避免 `contains` 与 `location_id` 双真源；新内容不应再依赖仅存在于 `contains` 而不反映在 `location_id` 的层级）。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `space` |
| `CommandType` | `SYSTEM`（与 `find` / `describe` 同属图只读；若产品要求仅世界内可执行，可在策略层收紧，本SPEC默认 SYSTEM） |
| Class | `app.commands.space_command.SpaceCommand` |
| Primary implementation | [`backend/app/commands/space_command.py`](../../../../backend/app/commands/space_command.py)（注册见 [`init_commands.py`](../../../../backend/app/commands/init_commands.py)） |
| Locale | `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml` → `commands.space.*`（usage、四段标题、表头、空态/错误、分段标签） |
| Ontology 锚点 | [`backend/db/ontology/graph_seed_node_types.yaml`](../../../../backend/db/ontology/graph_seed_node_types.yaml) 中 `trait_class: SPACE` 与设备 `trait_class: DEVICE`、tags |
| `look` 对齐 | [`backend/app/commands/game/look_command.py`](../../../../backend/app/commands/game/look_command.py)、[`look_appearance.py`](../../../../backend/app/commands/game/look_appearance.py) |
| Anchored snapshot | 运行 `python scripts/export_command_registry_snapshot.py` 更新 [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-27 |

## Synopsis

```
space
space -t
space -i <node_id>
```

- 无参 → **usage**（`error_result(..., is_usage=True)`，与 `describe` 无参行为一致；文案走 `commands.space`）。
- `space -t` → 列出本机支持的**空间语义 `type_code`**（见下「`space -t`」）。可选表格头，风格对齐 `world list` / `agent list`（见 [`CMD_world`](CMD_world.md)、[`CMD_agent`](CMD_agent.md)）。
- `space -i <id>` → 对**空间节点**输出四段（见「`space -i` 四段输出」）。`<id>` 为**图 `nodes.id` 整数**，与 `find #<id>`、`find -t building` 等返回的 `id` 相同。

## CLI 与解析

| 形态 | 行为 |
|------|------|
| 无参 | `usage` |
| `-t` 且未与 `-i` 组合为冲突 | 仅列类型；若实现支持 `space -t -i` 的歧义，**禁止**静默丢参——应报错或在 SPEC 中禁止该组合；**本SPEC约定**：`space` **要么**只 `-t` **要么**只 `-i <id>`，二者不混用。 |
| `-i <id>` | 正整数；前后空白 trim |
| 未知 token | 与 `find`/`describe` 一样：`unknown flag: <token>`（若使用相同解析风格） |

**需 `context.db_session`**；缺失时错误文案走 `commands.space`（如 `error.no_session`），默认 en 可与 `find` 对齐为 *requires an active DB session*。

## 空间类型（`space -t`）

**语义标识**：以本体为准，[`NodeType.trait_class`](../../../../backend/app/models/graph.py) **`SPACE`** 对应**空间**语义；种子定义见 `graph_seed_node_types.yaml`（例：`building`、`building_floor`、`room`）。

**列表数据来源（实现时二选一并写入代码注释，且仅一种为真）**：

1. **推荐**：`SELECT`（或 ORM 等价）`node_types` 中 **`trait_class = 'SPACE'` 且** 参与注册表/活跃的类型（与部署种子一致）；
2. **备选白名单**：`building`, `building_floor`, `room`，并注「可扩展为读 ontology」。

输出按行或表格；**表头/分隔线/总数** 可选，须 i18n。

## `space -i <id>` 前置条件

- 节点 `id` 存在、`is_active` 符合读策略、且其 **`type_code` 所对应的 `NodeType.trait_class == 'SPACE'`**（或落在上述白名单）。
- **不可读 / 非空间 / 不存在**：**统一**错误，**不**区分「无权限」与「无节点」；与 [F05 agent list/status](../../../models/SPEC/features/F05_AGENT_COMMAND_LIST_AND_STATUS.md) 防枚举策略可对齐，**可**复用同一 i18n 常数；具体句在 `commands.space` 中定义一次。

**读可见性（F11）**：若与 `find` 一致，仅返回当前主体**允许读**的节点与关联行；在 [`F11`](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md) 未接入时，可注明退化为与 `find` 同级的「已认证会话可读」**技术债**。

## `Message` 与 `Data`（见 [`protocols/CLAUDE.md`](../../../../backend/app/protocols/CLAUDE.md)）

### 终端 `message`：类 `look` 的分段风格（**非 JSON 呈现**）

- **主输出**为自然语言/表格行的**拼接字符串**，其**结构**应对齐 [`return_appearance_room` / 房间展示模板](../../../../backend/app/commands/game/look_appearance.py) 的**体验**：多行、**段与段之间**可用空行分隔、每段前有 **i18n 节标题**（可含装饰性分隔线，实现自定，但**不得**用 JSON 花括号作视觉骨干）。

#### 对象行列表（**四段均须遵守**）

- **总规则**：在节标题之下，**每一段的具体信息**均须以 **「对象/条目行」** 的**列表**呈现——**一行**对应**一条**在语义上可独立计数的内容；**禁止**用一坨**无行界**的连续长文作为该段的唯一正文（段 1 的说明文字也须**拆成多行**，**每行**承载一条语义或一条子项）。
- **结构形态**（实现选一种或混用，但**须保持「一行一条」**）：
  - **行首列表符**：如 `look` 中 `- *{name}*` 风格、或固定前缀 `-` / `*` / `•`（i18n 不强制符号，**须**在 SPEC 外统一团队规范）。
  - **定宽/标签列**表头 + 多行 data 行；或**「标签：值」**每行一条（**一条标签一行**，长值可**折行**但**续行须有缩进或前缀**以便仍视为同一条的延续，或**强制**一句一行截断+省略，由实现择一并在代码注释中说明）。
- **与四段的对应**：
  - **段 1 空间描述**：不列人物/设备；**空间本体**的若干事实（如名称、短/长描述、氛围、**每条**出口/门户/方向性联通说明）**各占一行或占一组连续行**（**每条出口/关系一条对象行**为宜），与上「一条一目」同旨。
  - **段 2 空间人物 / 段 3 空间设备 / 段 4 空间关系**：**每个**图节点（人、设备、相邻/子空间）**必须单独占行**；有 **`id`** 时该行须含 **`id`** 列或行内 `id=…` 约定（**优先**定宽**表格**+表头，与 [`agent list`](CMD_agent.md) 一致，便于人眼与 Agent 对齐）。

- **各章呈现**（与下节「四段」一一对应；**节标题**见 **「四段节标题（产品缺省文案）」**）：
  - **段 1**：**对象行/语义行**列表，非人物设备；**不**是 JSON 键名 dump、**不**是单段无换行长文。
  - **段 2–4**：**表格式**或**对象行**列表（**每行一实体**），**必须**含可解析 **`id`**（与上表同）。
- **反模式（禁止）**：成功结果里 `message` 仅为 `json.dumps(data)` 或与 `data` 逐字同构的 JSON 文本；**整节**只输出**一段**无换行长文；段 2–4 **不按行**分解实体。调试若输出 JSON，须**明确定位**为诊断路径，**不**作为默认 `message`。

### `data`：结构化 JSON（Agent / API）

- **`data`** 承载**机读**树（下节 JSON 为**目标形状**）；**所有**列表项**必须**含**整数 `id`**。HTTP/Agent **优先**消费 `data`；SSH 对终端**只**依赖 **`message` 的上述分段风格**，不依赖用户从终端解析 JSON。

### `CommandResult.data`（目标形状，**非**终端正文）

下例仅供 API/实现字段对齐；**终端不直接打印该 JSON 块**。

```json
{
  "space_node": { "id": 0, "type_code": "room", "name": "...", "parent_id": null },
  "section1_appearance": { "message_fragment": "..." },
  "section2_occupants": [
    { "id": 0, "name": "...", "type_code": "..." }
  ],
  "section3_devices": [
    { "id": 0, "name": "...", "status": "..." }
  ],
  "section4_next_or_adjacent": [
    { "id": 0, "name": "...", "direction": "north", "description": "..." }
  ],
  "section4_mode": "children | room_links | fallback_attr",
  "section4_fallback": false
}
```

- **`space_node.parent_id`**：当前空间节点的 **`Node.location_id`**（整数或 `null`），便于 Agent 沿链向上解析。
- **`section4_mode`**：`children` 表示由 **`location_id` 子链** 得到的下层级空间；`room_links` 表示 **`room` 的 `connects_to` 对端**；`fallback_attr` 表示在缺少 `location_id` 子关系时启用了**过渡期**的 attributes 子查询（见「技术债与过渡期」）。
- **`section4_next_or_adjacent[*].direction`**：方向字段。`room_links` 时为方向字符串（来源与 `look` 一致）；`children` / `fallback_attr` 时为 `null`（层级包含关系不伪造方向）。
- **`section4_fallback`**：为 `true` 时，**段 4** 曾走次选查询路径（对测试与排障可见）。
- **`section1_appearance` / 各 `section*`**：用于程序消费与测试断言；人读 `message` 须由**同一套**查询结果**按「对象行列表」规则**独立渲染为分段文本（**每数组元素 → 至少一行**），而非仅回显该 JSON 字符串或合并为单段长文。

## 四段节标题（产品缺省文案）

`space -i` 成功时，`message` 中四段**自上而下**的**节标题**（行首独段或标题行，后接空行再写正文/表）**固定为**下列**中文缺省**；实现经 `commands.space` 做 i18n，**键名**与 **en-US 建议**如下（与缺省一致时可直用）：

| 段 | 中文缺省（zh-CN，含全角冒号） | 建议 i18n 键 | en-US 建议 |
|----|-----------------------------|-------------|------------|
| 1 | **空间描述：** | `section.title.1` | `Space description:` |
| 2 | **空间人物：** | `section.title.2` | `Space occupants:` |
| 3 | **空间设备：** | `section.title.3` | `Space devices:` |
| 4 | **空间关系：** | `section.title.4` | `Space relations:` |

- 若 locale 为 `zh-CN` 且未覆写，展示须与上表**字面一致**（含 `：`）。
- 段 4 的语义仍受下节「下一层/联通」约束，**标题**「空间关系」涵盖 **包含下一层** 与 **room 联通** 两种数据形态。

## `space -i` 四段输出

**顺序**（`message` 中**自上而下、类 `look` 分段**；`data` 中按节键**同序**）与 **`look` 的关系**：

| 段 | 节标题（见上表） | 终端 `message` 的呈现 | 与 `look` 的关系 / 数据说明 |
|----|------------------|------------------------|----------------------------|
| 1 | **空间描述：** | **按对象行/语义行**逐条列出（**一行一条**或多行一组仅表示同一条的折行，见上「对象行列表」）。内容：**仅空间本体**——`name`、短/长描述、氛围、**每条**出口/门户/方向与 `look` 同口径的边界；**不**在终端整段一坨无换行；**不**人/物/设列表；不 dump JSON。模板与 [`return_appearance_room`](../../../../backend/app/commands/game/look_appearance.py) 可对照，**呈现**须满足「行列表」。 | **不复述** 设备/人/物；`data` 为并行机读。 |
| 2 | **空间人物：** | **表格式 或 对象行**（**每人一行**）：列 `id` / `name`（+ 可选 `type_code`），表头+分隔线可选。 | `location_id` 命中；**禁止**用散文段落代替**逐人行**。 |
| 3 | **空间设备：** | **表格式 或 对象行**（**每台设备一行**）：`id` / `name` / 状态。 | 同左。 |
| 4 | **空间关系：** | **表格式 或 对象行**（**每个相邻/子空间节点一行**）：`id` / `name` / `description`；`room` 时与 `look` 对端**同集**，并展示 `direction`。 | 见下。 |

**id 为 Agent 的硬要求**：段 2、3、4 在 **`data`** 与 **`message` 的每一对象行/表格行**中**均**须带 **`id`**（与 [`agent list`](CMD_agent.md) 表头表或等价**行内** `id`），避免整段无行界散文。

## 段 4：「下一层空间 / 联通」**（`type_code` 分策略）**

**统一定义**：**不是**「任意图邻点」，而是**与当前 `type_code` 匹配的「直接下一层空间」**或 **`room` 的联通**：

| 当前 `type_code` | 段 4 含义 | 与 `look` 的关系 / 真源 |
|------------------|-----------|------------------|
| `building` | 该建筑**直接包含**的 **`building_floor`** 节点集合。 | **首选项**：`location_id` = 本建筑 `id` 的 **`building_floor`** 节点。过渡期：可回退为 `attributes.building_id` 等于本建筑 `package_node_id` 的楼层（见上「技术债与过渡期」）。**禁止**用 `connects_to` 表达本行关系。 |
| `building_floor` | 该楼层**直接包含**的 **`room`** 节点集合。 | **首选项**：`location_id` = 本楼层 `id` 的 **`room`**。过渡期：可回退为 `attributes.floor_id` 等于本楼层 `package_node_id` 的房间。**禁止**用 `connects_to` 表达本行关系。 |
| `room` | 与当前房间在 **`look` 语义**下**出口/联通**指向的**其它 `room` 节点**；**关系真源、解析须与** `look` **一致**；对端 `room` 的 **id 集合**须与**同一** `room` 上 `look` 所见**一致**；**只**是**呈现**不同（`look` 为方向+叙事 **`space` 为 id+表+desc）。 | **复用** [`room_connects_to_query`](../../../../backend/app/commands/room_connects_to_query.py) / `look` 路径，**不得**在 `space` 内**重复定义** `connects_to` 语义。仅本行使用 `connects_to`（**邻接**，非包含）。 |

## 国际化

- 键位根：`commands.space`。
- **四段节标题** 已约定键 `section.title.1` … `section.title.4` 与 **zh-CN / en-US 缺省**（见 **「四段节标题（产品缺省文案）」**）；实现须落入 [`zh-CN.yaml`](../../../../backend/app/commands/i18n/locales/zh-CN.yaml) / [`en-US.yaml`](../../../../backend/app/commands/i18n/locales/en-US.yaml)，**不得**在实现代码中硬编码四段中文标题（除 i18n 回退默认句若项目惯例允许）。
- 另含：`usage`、`error.*`（no_session, not_space, not_found, forbidden 等，按实现收敛）、`table.header.*`（`id`/`name`/`type_code`/`status`/`description` 等）、`type_list.*`（`space -t`）、`flags.bad_combo` 若需。
- 文案随 [`resolve_locale(context)`](../../../../backend/app/commands/i18n/locale_text.py)（与 [CMD_agent](CMD_agent.md) 等一致）。

## 授权与 `command_policies`

- 与 `find` / `describe` 同级**只读**；默认策略在 [`policy_bootstrap.py`](../../../../backend/app/commands/policy_bootstrap.py) 或等价处显式**一行**说明，避免空注册误解。

## Non-Goals / Roadmap

- **段 2「进入时间」**：首版**不**做；有统一 **presence/审计** 真源后**再**在 `data.occupants` 与 `message` 增列，并改本文与版本记录。
- **`cl` 知识世界**、非图 REST：不在本命令范围。
- 落地后**必须** `export_command_registry_snapshot` 与**可选** `verify_command_spec_files`。

## 相关

- 总表：[../SPEC.md](../SPEC.md)
- 图检索总述：[F01_FIND_COMMAND](F01_FIND_COMMAND.md)（`find`/`describe` 深契约占此）
- 空间类型本体：[`db/ontology/graph_seed_node_types.yaml`](../../../../db/ontology/graph_seed_node_types.yaml)
- F11 读图策略：[F11 Data Access — Graph API](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)

## Tests

- 单元：`space` 参数解析（`usage`、`-t`、`-i`、互斥/未知 flag）与**非空间/不存在**等错误路径。
- 与 `room` 的**段 4 对端 id 集** 与**同一**节点上 `look` 的 **`connects_to` 出口**一致（或与本仓库共享查询模块一致）——见 `backend/tests/commands/test_space_command.py`。
- 重集成、需 PostgreSQL 的用例按 [test 实践](../../../testing/SPEC/SPEC.md) 标记。
