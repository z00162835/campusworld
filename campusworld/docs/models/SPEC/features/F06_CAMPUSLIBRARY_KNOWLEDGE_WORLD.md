# F06 — CampusLibrary 内置知识世界（OS 级知识库）SPEC

> **Architecture Role：** 定义内置虚拟世界 **`campuslibrary`**（`world_id=campuslibrary`）作为 CampusWorld **操作系统级全局知识库**：图结构存储、GraphRAG 式检索语义、**`cl`** 命令族（`search` / `ingest` / `del`）、**pgvector** 向量检索；奇点屋 **可见可 `look`、不可 `enter` 穿越**；**软删除**统一 **`nodes.is_active`**。人类用户与 **AICO**（经 `tool_allowlist`）共用同一命令与授权链。

**文档状态：Draft**

**交叉引用：** [`F02`](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)（Agent/LTM）、[`F02_LTM_VECTORS_AND_MEMORY_LINKS.md`](F02_LTM_VECTORS_AND_MEMORY_LINKS.md)（pgvector 实践）、[`F03`](F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)（AICO、`tool_allowlist`）、[`F04`](F04_AT_AGENT_INTERACTION_PROTOCOL.md)、[`F05`](F05_AGENT_COMMAND_LIST_AND_STATUS.md)、[`F10`](../../../api/SPEC/features/F10_ONTOLOGY_AND_GRAPH_API.md)、[`F11`](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)（读策略）、[`docs/commands/SPEC/SPEC.md`](../../../commands/SPEC/SPEC.md)。

**实现锚点（建议）：** `backend/app/games/campuslibrary/`（世界包，待建）、[`backend/app/commands/`](../../../../backend/app/commands/)（`cl` 命令族，待建）、[`backend/db/ontology/graph_seed_node_types.yaml`](../../../../backend/db/ontology/graph_seed_node_types.yaml)、[`backend/app/models/graph.py`](../../../../backend/app/models/graph.py)、[`backend/app/game_engine/world_entry_service.py`](../../../../backend/app/game_engine/world_entry_service.py)、[`backend/app/commands/game/enter_world_command.py`](../../../../backend/app/commands/game/enter_world_command.py)。

**显式非目标（本 SPEC）：** **SKY 类型智能体、SKY01 实例、自动采集/解析管线**；仅可预留「未来采集写入同一 `world_id` 图命名空间」的扩展点，不写调度与实现。

---

## 1. Goal

- 提供 **单一全局知识世界** **campuslibrary**，承载产品文档、SPEC、HELP、FAQ 等结构化或非结构化知识的 **录入、检索、逻辑删除**。
- **借鉴 GraphRAG** 的分层思想：**源文档 → 切片（chunk）→ 语义关系 → 检索路径**（关键词/问句 → 可选向量召回 → 子图扩展 → 重排 → 可引用答案）；具体阶段见 §8。
- **与 HiCampus 区分**：campuslibrary **不是**可漫游空间世界；用户 **不**通过 `enter` 进入拓扑游玩。
- **与 AICO 对齐**：AICO 通过 **`cl`**（及 `command_policies`）查询/维护知识，与 F03 工具白名单一致。

---

## 2. Non-Goals

- SKY / SKY01 及任何「自动爬取/转换」采集器实现。
- 多租户、业务分域、独立知识域隔离（见 §3）。
- 异构向量库（Milvus 等）；向量 **仅** pgvector（§5）。

---

## 3. 设计决议（已锁定）

以下条款为产品/架构已确认约束，实现与验收须一致。

| # | 决议 |
|---|------|
| 1 | **GraphRAG**：架构与检索管线借鉴业界 GraphRAG；SPEC 要求映射到 `nodes` / `relationships` 与分阶段落地（§7–§8）。 |
| 2 | **奇点屋**：campuslibrary **在奇点屋可见**，用户可 **`look` 到入口/门面**；**不可**像 HiCampus 一样 **`enter` 穿越**进入世界内漫游。 |
| 3 | **向量**：复用 **PostgreSQL `pgvector`**，与 F02 LTM 等技术栈一致。 |
| 4 | **租户与域**：**无多租户、不分域**；campuslibrary 为 **CampusWorld OS 全局知识库** 唯一命名空间（`world_id=campuslibrary`）。 |
| 5 | **软删除**：统一使用 **`nodes.is_active`** — `false` 表示逻辑删除；**默认查询**仅返回 `is_active=true`；`cl del` 仅执行软删，不物理删除行（除非另有运维工具，非本 SPEC）。 |
| 6 | **入口与进入**：采用 **「有入口节点、不可拓扑进入」** — 奇点屋存在 **世界入口类呈现**（满足列表与 `look`），**不提供**与 HiCampus 相同的 **`enter` 位置迁移**；`enter campuslibrary` **须拒绝**并提示使用 **`cl`**（见 §6）。 |
| 7 | **命令**：顶层 **`cl`**；子命令固定 **`search`**、**`ingest`**、**`del`**（§9）。 |

---

## 4. 术语

| 术语 | 含义 |
|------|------|
| **Knowledge world** | 逻辑世界 `campuslibrary`；数据上仍用 `nodes.attributes.world_id`（或等价）与包图种子对齐。 |
| **Source / Document** | 知识库中的逻辑文档节点（建议 `type_code` 如 `kb_document`，实现待定）。 |
| **Chunk** | 检索与向量挂载的文本切片节点（建议 `kb_chunk`），与文档 `PART_OF` 或等价边相连。 |
| **GraphRAG（狭义）** | 本项目：向量召回 + 图关系扩展 + 重排的产品语义，分 M1/M2 实现（§8）。 |

---

## 5. 数据模型要点（图 + pgvector）

- **存储**：统一 **`nodes`** / **`relationships`**；在 **`node_types`** 中注册知识库相关 `type_code`（具体名称由实现命名，SPEC 建议区分 **document / chunk /（可选）topic**）。
- **`world_id`**：知识节点 **`attributes.world_id` = `campuslibrary`**（或与包 manifest 一致），保证与全局图查询、种子幂等一致。
- **pgvector**：切片节点（或实现选定载体）上 **`embedding`** 列 + 索引策略与 [`F02_LTM_VECTORS_AND_MEMORY_LINKS.md`](F02_LTM_VECTORS_AND_MEMORY_LINKS.md) 对齐（维度、模型元数据字段等由实现参照 LTM 惯例）。
- **软删除**：凡参与「对外可见知识」的节点，**`is_active=false`** 表示删除；**关系**是否级联隐藏由实现定义，SPEC 要求 **`search` 不返回** `is_active=false` 的节点（管理员审计命令可另议，非 M1 必做）。

---

## 6. 奇点屋呈现与 `enter` 拒绝

- **可见性**：安装/种子后，通过 **`world_entrance`**（或等价）在 **奇点屋根房间** 列出 **campuslibrary**，使用户 **`look`** 时能看到「Campus Library / 知识库」类描述，并提示 **使用 `cl search|ingest|del`** 访问。
- **不可进入**：**不**对用户账号执行 **`enter campuslibrary` 的位置跳转**；实现二选一或组合（由实现选型，SPEC 固定对外行为）：
  - **A.** `world_entrance` 元数据 **`enterable: false`**（或等价），`enter` 命令解析后 **拒绝**；或
  - **B.** `enter` 内对 `world_id=campuslibrary` **硬编码/配置表拒绝**。
- **错误文案**：须引导 **`cl`**，避免与 HiCampus「可进入」混淆。

**实现锚点：** [`world_entry_service.py`](../../../../backend/app/game_engine/world_entry_service.py)、[`enter_world_command.py`](../../../../backend/app/commands/game/enter_world_command.py)。

---

## 7. GraphRAG 检索语义（产品层）

建议管线（与业界 GraphRAG 对齐，分阶段）：

1. **查询理解**：用户或 AICO 传入自然语言或关键词（经 `cl search`）。
2. **召回**：**M1** 可仅结构化过滤 + 全文/属性匹配；**M2** 加入 **pgvector** 相似片段召回。
3. **图扩展**：从命中 chunk 沿 **`relationships`** 扩展有限跳（类型与深度由策略限制）。
4. **重排与合成**：返回带 **引用（chunk id / document id）** 的 JSON，供终端或 AICO 组装回复。

**边界：** 若仅有向量无图边，**v1** 允许退化为「纯向量 + 元数据」；SPEC 鼓励逐步补齐图边以便可解释引用。

---

## 8. 实现阶段（建议）

| 阶段 | 内容 |
|------|------|
| **M1** | 世界包骨架 + 图类型种子；`cl search|ingest|del` 最小闭环；**无向量或仅预留列**；奇点屋入口可见 + `enter` 拒绝。 |
| **M2** | **pgvector** 索引与 **`search` 混合检索**；GraphRAG 扩展与重排增强。 |

---

## 9. 命令族：`cl`

### 9.1 形态

- 注册名：**`cl`**；子命令由 **`args[0]`** 解析（与 `world`、`agent` 子命令模式一致）。
- 子命令：
  - **`search`** — 检索知识（参数：查询串、可选过滤；输出 JSON 于 `CommandResult.message`，与 F05 JSON 习惯对齐）。
  - **`ingest`** — 录入或更新知识（参数：由实现定义：文件路径、粘贴块、或结构化字段；须写入 `campuslibrary` 图命名空间）。
  - **`del`** — **软删除**：将目标节点 **`is_active` 置为 `false`**（须校验目标属于 campuslibrary 知识实体，防误删其他图数据）。

### 9.2 数据库与会话

- 与现有系统命令一致：需要 **`context.db_session`**；缺失时返回明确错误。

### 9.3 权限（默认矩阵，可与 F11 演进）

| 角色/能力 | `cl search` | `cl ingest` | `cl del` |
|-----------|-------------|-------------|----------|
| 普通登录用户 | 允许（只读） | 按部署策略（默认可拒绝） | 默认拒绝 |
| 运维/管理员 | 允许 | 允许 | 允许 |

具体 **`command_policies`** 权限串由实现命名（如 `cl.search`、`cl.ingest`、`cl.delete`），本 SPEC 要求 **默认可读、写删收敛到管理角色**。AICO **`tool_allowlist`** 至少包含 **`cl`**（及策略允许的子行为）；是否允许 AICO 调用 **`ingest`/`del`** 由产品与策略决定。

---

## 10. 授权与策略

- **`authorize_command`**：与 HTTP/SSH 同源（F02 命令不变式）。
- **F11**：全局知识库的 **图读范围** 与 **命令授权** 叠加；**无多租户** 不表示 **无 ACL** —— 写删仍须高权限。

---

## 11. 安全与审计

- **`del`** 仅软删，保留审计与恢复可能性；如需 **`deleted_by` / `deleted_at`**，可放在 **`attributes`**，**不作为**软删主键（主键仍为 **`is_active`**）。
- **`ingest`** 须防注入与越权写入（路径遍历、写入非 `campuslibrary` 节点等），由实现做校验。
- **`search`** 防泄露：返回字段避免无关敏感图数据（最小必要原则）。

---

## 12. 与既有世界包的关系

- 可参考 [`games/hicampus/manifest.yaml`](../../../../backend/app/games/hicampus/manifest.yaml) 增加 **`world_id: campuslibrary`** 包；**manifest** 或运行时元数据标注 **`world_kind: knowledge`**、**`enterable: false`**，供入口同步与 `enter` 拒绝逻辑消费。

---

## 13. 验收标准（建议）

- [ ] 奇点屋 **`look`** 可见 campuslibrary 入口描述；**`enter campuslibrary`** 被拒绝且提示使用 **`cl`**。
- [ ] **`cl search|ingest|del`** 在 **有 db_session** 且策略允许时行为符合 §9；**`del`** 仅将目标知识实体 **`is_active=false`**。
- [ ] **`cl search`** 默认不返回 **`is_active=false`** 节点。
- [ ] **M2**：**pgvector** 参与 **`search`** 召回（验收用例可标记 `postgres_integration`）。
- [ ] **F03**：AICO 在 **`tool_allowlist`** 含 **`cl`** 时可调用（以策略为准）。

---

## 14. 附录 — 与 F03 AICO

- 默认助手通过 **`cl search`** 查询 OS 知识库；**`ingest`/`del`** 是否开放给 AICO 由 **`tool_allowlist` + `command_policies`** 决定。

---

## 15. 开放问题（非阻塞 v1）

- **`search` / `ingest` / `del` 的参数形状**（CLI 参数、JSON 负载）— 实现阶段在命令 help 与本文档增补一节即可。
- **M1 是否完全省略向量** — 建议 M1 预留列与空检索路径，M2 一次性启用索引（见 §8）。
