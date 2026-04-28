# F01–F03 缺口与风险 — 修复计划（含 Evennia 设计参照）

> **目的**：将此前代码审查中识别的 F01（世界包运行时）/ F02（数据包）/ F03（图种子）**断裂点**与**静默语义丢失**纳入可执行、可验收的修复序列。  
> **Evennia 参照**：在「内容装配时机、错误 surfaced、typeclass 可解析、批量实例化」四处对齐 [Evennia](https://www.evennia.com/) 的工程习惯（非逐 API 拷贝）。

## 1. Evennia 概念 ↔ CampusWorld 落点

| Evennia 思路 | 说明 | CampusWorld 对应 | 当前缺口 |
|--------------|------|------------------|----------|
| **Typeclass 必须可 import** | 未加载模块中的 typeclass 不会被发现 | `node_types.typeclass` / `app.models.things.*` 显式 import | 已由 typeclass 工作计划覆盖；种子失败时需稳定错误码 |
| **create_object / 批量建对象** | 创建路径明确、失败可记录 | `run_graph_seed` 批量 upsert 节点与边 | 未挂入 `load_game`；错误码枚举不完整 |
| **Server 启动 vs 世界内容** | 系统先起，再装/载数据 | F01 加载 ≠ F03 落库 | 端到端断裂 |
| **Command 路径不吞异常** | 返回可诊断结果 | `WorldErrorCode` + `OperationResult.details` | `GRAPH_SEED_*` 未入枚举 |
| **Exit 有向、双向通行两条** | 拓扑显式 | `connects_to` 反向补齐 | 已实现；F02 扩展关系与 F03 白名单不一致 |
| **Prototypes / 批量脚本** | 可重复、幂等执行 | F02 snapshot → F03 pipeline | 需 manifest 开关与可观测性 |

参考文档（外部）：[Typeclasses](https://www.evennia.com/docs/latest/Components/Typeclasses.html)、[Objects](https://www.evennia.com/docs/latest/Components/Objects.html)。

## 2. 缺口登记（与审查结论对齐）

| ID | 描述 | 严重度 | 关联特性 |
|----|------|--------|----------|
| G-01 | `WorldErrorCode` 缺少 `GRAPH_SEED_REFERENCE_BROKEN`、`GRAPH_SEED_TYPE_UNKNOWN`，与 `pipeline`/`graph_profile`/测试引用不一致 | **P0** | F01 / F03 |
| G-02 | `GameLoader.load_game`（及 reload 成功路径）未调用 `run_graph_seed`，F02 校验通过但图可能未实例化 | **P0** | F01 ↔ F03 |
| G-03 | F02 validator 允许的 `rel_type_code` 超集于 F03 `allowed_relationship_type_codes`，pipeline **静默跳过**未支持类型 | **P1** | F02 ↔ F03 |
| G-04 | F02 ConceptModel 无对应图节点策略；读者假设「校验通过即全量进图」 | **P1** | F02 / F03 / 文档 |
| G-05 | F03 SPEC 过简，未描述错误码、profile 契约、关系子集与观测字段 | **P2** | 治理 |
| G-06 | HiCampus L4 基线写死在 validator（已知债） | **P2** | F02 多世界 |

## 3. 修复阶段总览

```mermaid
flowchart LR
  P0A[P0-A 错误码契约]
  P0B[P0-B Loader 挂接种子]
  P1A[P1-A 关系可见性]
  P1B[P1-B 概念层策略]
  P2[P2 文档与基线配置化]
  P0A --> P0B
  P0B --> P1A
  P1A --> P1B
  P1B --> P2
```

建议 **P0-A 与 P0-B 不同 PR**：先合并枚举与单测，再合并 loader 行为，便于回滚。

---

## 阶段 P0-A：图种子错误码与契约（Evennia：失败可诊断）

**目标**：所有 `GraphSeedError` / profile 抛错使用的字符串与 `WorldErrorCode` 枚举成员一致，避免运行时 `AttributeError` 与 F01 结果中 `error_code` 无法归类。

**任务**

1. 在 `app/game_engine/runtime_store.py` 的 `WorldErrorCode` 中增加：
   - `GRAPH_SEED_REFERENCE_BROKEN`
   - `GRAPH_SEED_TYPE_UNKNOWN`
   - （可选预留）`GRAPH_SEED_FAILED` — 仅当需区分「引用/类型」与「通用种子失败」时引入，避免码表膨胀。
2. 更新 F01 SPEC（`F01_WORLD_PACKAGE_RUNTIME.md`）错误码表最小集，注明「图种子失败可映射为 `GRAPH_SEED_*` 或 `WORLD_LOAD_FAILED`」的**选用规则**。
3. 单测：`tests/game_engine/test_world_error_codes.py`（或等价）断言上述成员存在，且与 `graph_profile` / `pipeline` 引用一致（可维护 frozenset 或扫描 AST 的轻量检查，二选一）。

**验收**

- `from app.game_engine.runtime_store import WorldErrorCode` 后 `GRAPH_SEED_TYPE_UNKNOWN.value` 等可用。
- 现有 `test_graph_seed_pipeline` / `test_hicampus_profile_unknown_type_raises` 不依赖「未定义枚举成员」的侥幸路径。

**回滚**：仅回退枚举与文档；不影响行为。

**Evennia 对齐**：类比命令与创建对象失败时返回明确错误，而非未定义符号。

---

## 阶段 P0-B：`GameLoader` 挂接 F03 种子（Evennia：装配时机显式）

**目标**：在「世界已成功校验并持有 snapshot」的前提下，**可选地**在同一业务事务边界内执行图种子，使 M1 端到端「F02 → F03」在默认或显式开启时成立。

**任务**

1. **Manifest 契约**（`manifest.yaml`）：增加可选键，例如：
   - `graph_seed: true | false`（默认建议 `false` 至下一主版本，或 `true` 仅对 HiCampus 开启，由团队定）。
   - 或 `features.graph_seed.enabled`（更利于扩展）。
2. **`GameLoader`**：在 `load_game` / `reload_game` 成功路径中，当 `graph_seed` 为真且存在 `load_package_snapshot` 与 `HICAMPUS_GRAPH_PROFILE`（或通用 `get_graph_profile(world_id)` 协议）时：
   - `ensure_graph_seed_ontology(engine)`（或等价幂等）在种子前执行；
   - `with db_session_context()` 内：`run_graph_seed(session, world_id, snapshot, profile)`；
   - 捕获 `GraphSeedError`，映射为 `WorldErrorCode` 对应成员，**失败时**将 `status_after` 置为 `failed`/`broken`（与 F01 现有失败路径一致），`details` 附 `graph_seed` 摘要。
3. **不得**在 F02 YAML 解析层写 DML（遵守架构 C-04）。

**验收**

- `graph_seed: false` 时行为与当前一致。
- `graph_seed: true` + PostgreSQL + 已迁移本体时，`load_game("hicampus")` 后图中存在预期节点（可与现有 integration 测试共用环境）。
- SSH/入口在种子失败时不崩溃，返回结构化 `error_code`。

**回滚**：manifest 默认 false；或回退 loader 分支。

**Evennia 对齐**：类似「装完数据再开服」或「延迟到首次需要时」——本计划采用 **manifest 显式开关**，避免隐式魔法；后续可演进为 Evennia 式 `@tick_handler` 延迟 provisioning（非本阶段必选）。

---

## 阶段 P1-A：F02 关系超集 vs F03 白名单 — 可观测与可选严格模式

**目标**：消除「校验通过但边未落库」的**静默**；行为与 Evennia「只实例化脚本声明的关系类型」一致，但需对调用方可见。

**任务**

1. **`run_graph_seed` 返回值** `details` 增加：
   - `relationships_ignored_count` 或按 `rel_type_code` 分桶计数；
   - 可选 `relationships_ignored_sample`（上限 N 条 id），防日志爆炸。
2. **`WorldGraphProfile`**（或 pipeline 参数）：`strict_relationships: bool`：
   - `false`（默认）：当前行为 + 计数；
   - `true`：若 snapshot 中存在不在 `allowed_relationship_type_codes` 的关系，**抛 `GraphSeedError`**（如 `GRAPH_SEED_REFERENCE_BROKEN` 或专用码），强制 F02 与 profile 对齐。
3. 文档：在 `F02_WORLD_DATA_PACKAGE.md` 与 `F03_GRAPH_SEED_PIPELINE.md` 各增一小节「关系类型：校验全集 vs 种子子集」。

**验收**

- 默认模式下 HiCampus 现有数据包跑种子后 `details` 含非零忽略计数时，集成测试或手工可断言。
- `strict_relationships=true` 时，含未支持 `rel_type` 的 snapshot 失败且错误码稳定。

**Evennia 对齐**：类似只迁移脚本声明的 link 类型；超出部分要么扩展类型注册表，要么显式报错。

---

## 阶段 P1-B：ConceptModel 图实例化策略（文档优先，实现可选）

**目标**：明确 F02 概念层是否、如何进 `nodes`（与 Evennia「非空间对象 / Script」类比：可暂不进主 ObjectDB，但须在 SPEC 写明）。

**任务**（按优先级选一或组合）

1. **文档决策**（必选）：在 `F03_GRAPH_SEED_PIPELINE.md` 写明：
   - **当前**：概念仅存在于 snapshot，**不**生成 `Node`；
   - **未来**：可选 `concept` 节点类型 + `node_types` 行 + typeclass（引用 [TYPECLASS_ONTOLOGY_EXEC_PLAN.md](TYPECLASS_ONTOLOGY_EXEC_PLAN.md)）。
2. **实现（可选）**：新增 `concept_*` 的 `type_code` 与白名单关系 `applies_to` / `governs` 等渐进落地（独立 PR，依赖 P1-A strict 策略）。

**验收**：新同学只读 F02+F03 SPEC 能回答「概念进不进图」。

---

## 阶段 P2：SPEC 扩写与 L4 基线配置化

**任务**

1. 扩写 `F03_GRAPH_SEED_PIPELINE.md`：输入/输出、`WorldGraphProfile`、`错误码表`、`details` 字段、与 `F02_ENTITY_TYPE_REGISTRY` 的链接。
2. HiCampus L4：将楼层/必现房间从 validator 硬编码迁到 `package/baseline_profile.yaml`（或同级），validator 读取——多世界时复制修改配置而非复制代码。

**验收**：F03 SPEC 与 `pipeline` 行为 diff 可评审；HiCampus 校验行为不变（回归测试）。

---

## 4. 与既有文档的关系

| 文档 | 关系 |
|------|------|
| [TYPECLASS_ONTOLOGY_EXEC_PLAN.md](TYPECLASS_ONTOLOGY_EXEC_PLAN.md) | typeclass / `node_types` 与种子节点 `type_code` 一致；P0-B 种子失败时需记录 type 解析问题 |
| [TYPECLASS_ONTOLOGY_PR_WORK_PLAN.md](TYPECLASS_ONTOLOGY_PR_WORK_PLAN.md) | typeclass PR 序列可与 P0-B 并行，但 loader 合入前应保证本体行存在 |
| `F01_WORLD_PACKAGE_RUNTIME.md` / `F02_*` / `F03_*` | 各阶段同步最小增量，避免全文重复 |

## 5. 完成定义（DoD）摘要

- [x] P0-A：`WorldErrorCode` 含 `GRAPH_SEED_*`，单测防回归。
- [x] P0-B：manifest 控制下 `load_game` / `reload_game` 可执行 `run_graph_seed`，失败结构化、不拖垮入口。
- [x] P1-A：关系忽略可观测；可选 strict 与文档一致。
- [x] P1-B：概念层进图策略在 F03 SPEC 中**唯一表述**。
- [x] P2：F03 SPEC 与实现字段对齐；L4 `baseline_profile.yaml` 可配置。

---

**维护**：本计划随缺口关闭逐项勾选；重大行为变更（如默认 `graph_seed: true`）需单独 RFC 或版本说明。
