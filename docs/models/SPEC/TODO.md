# TODO - 数据模型开发任务

## 验收追踪

- 统一验收文档：`docs/ssh/SPEC/ACCEPTANCE.md`
- 入口语义约束：`SingularityRoom` 是系统全局入口，不是每用户独有空间。

## Agent Runtime P0/P1 优化

- [x] **P0 mandatory evidence tick-wide**
  - 同一 tick 内 Plan / Do / retry Plan / retry Do 任一允许工具阶段的成功 ToolObservation 均可满足 mandatory。
  - mandatory gap trace 保留缺口、权限、预算信息，并补充 observed tools / phases。
- [x] **P0 ToolObservation policy**
  - 语义真源为命令类 `tool_semantics`（registry SSOT）；`resolve_command_tool_semantics(name, args=...)` 支持子命令 profile 分流。
  - `system_command_ability.attributes.agent_observation_policy` 可 ops 覆盖 observation；profile / guard 由 ability sync 自 registry 强制镜像。
  - `full` / `summary` / `blocked` 三态稳定；summary 使用首个非空行与 `original_chars=<n>`，默认不使用 hash。
  - read 默认 `full`；mutate 默认 `summary`；未知命令与 `semantic_pending=true` 命令默认 `summary`。
  - trace `message_preview` 与实际注入 LLM 的 ToolObservation 使用同一策略；gather 内 policy 缓存键为 `(command_name, tuple(args))`。
- [x] **P0 mandatory repair 与 fallback**
  - mandatory 缺口允许一次 bounded repair retry；retry 后仍缺失/失败才进入兜底。
  - P0 用户侧兜底为短系统提示追加；结构化用户失败块留作 P1 后续增强。
- [x] **P1 minimal AgentRuntimeProfile**
  - AICO 专属 informational manifest subset、NDJSON lifecycle、REPL progress、observability hooks、full-chain debug 开关收敛到 `AicoRuntimeProfile`。
  - informational manifest subset 基于 Worker 创建时冻结的 `ResolvedToolSurface` 派生，不在 profile 层重建工具面。
  - 通用 `LlmPDCAFramework` / `ToolGather` / `ResolvedToolSurface` 不依赖 AICO profile。
- [x] **P1.5 runtime/profile 解耦补强**
  - `LlmPDCAFramework` 仅依赖通用 observability adapter，不直接 import AICO observability。
  - full-chain tick scope 由 profile 进入/退出；通用 `npc_agent_nlp` 不直接调用 AICO 全局开关。
  - LLM HTTP helper 从通用 runtime context 读取 run/correlation，并通过当前 observability adapter 分发 HTTP exchange 日志。
  - profile registry 采用注册表工厂，避免继续追加 service_id if 分支。
  - ToolObservation policy 在单次 gather 内按 `(command_name, tuple(args))` 缓存，避免同 tick 重复解析 ability policy。
- [ ] **P1 后续观测项**
  - 真实 token streaming、跨 phase cancel 与 live eval 暂不进入本轮强门禁；如产品继续推进，需单独 SPEC/ADR 与端到端验收。

## 实体扩展

### 高优先级

- [ ] **Room 类型完善**
  - 定义预定义空间：library/campus/canteen/dormitory
  - 空间属性：capacity（容量）/is_public（是否公开）
  - 空间坐标：x/y/z（可选，用于空间布局可视化）

- [ ] **Exit 类型完善**
  - 定义空间之间的连接关系
  - 属性：locked（是否锁定）/key_id（钥匙对象）
  - 方向：north/south/east/west 或自定义方向

- [ ] **SingularityRoom 完善**
  - 系统级全局单例入口空间（非每用户独有）
  - 创建用户后默认可进入系统入口 `SingularityRoom`
  - 与世界入口策略联动（进入世界后再落到世界内默认出生点）
  - 验收映射：`ACCEPTANCE 场景 A/B/C/D`

### 中优先级

- [ ] **Building 模型实现**
  - 包含多个 Room
  - 属性：floors（楼层数）/name/description

- [ ] **Character 模型完善**
  - 与 User 一对一关联
  - 属性：location_id（当前位置）/inventory（物品列表）
  - stats：energy/hunger/knowledge/social

- [ ] **Campus 模型实现**
  - 包含多个 World
  - 属性：name/location/owner

- [ ] **World 模型完善**
  - 包含多个 Building 和 Room
  - 属性：name/is_public/owner

### 低优先级

- [ ] **Item 模型**: 可交互的物品（书桌/食物等）
- [ ] **Equipment 模型**: 可穿戴/使用的设备
- [ ] **Event 模型**: 园区事件记录

## 语义边扩展

- [ ] 定义标准语义边类型枚举：LOCATED_IN/CONNECTED/OWNS/CONTAINS/HAS
- [ ] Exit 模型与语义边统一（Exit 即语义边的具象化）
- [ ] 支持语义边属性（如关系创建时间）

## 模型工厂扩展

- [ ] 自动发现机制：扫描 models/ 目录自动注册所有模型类
- [ ] 模型验证：注册时检查模型是否实现必要的接口
- [ ] 模型关系注册：声明模型间的关系（而非硬编码）

## 验收检查清单

- [ ] `model_factory.get_model("user")` 返回 User 类
- [ ] `model_factory.get_model("room")` 返回 Room 类
- [ ] `User` 继承 `DefaultAccount`
- [ ] `Room` 继承 `DefaultObject`
- [ ] 新建用户后可通过入口策略进入 `SingularityRoom`
- [ ] `SingularityRoom` 语义为系统全局入口（非每用户单例）
