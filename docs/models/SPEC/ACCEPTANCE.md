# 验收检查表

## 模型注册验收

- [ ] `model_factory.list_all_models()` 返回所有已注册模型
- [ ] `model_factory.register_model("test", TestModel)` 成功注册
- [ ] `model_factory.get_model("test")` 返回 TestModel 类
- [ ] 未注册的模型返回 KeyError

## 实体继承验收

- [ ] `User` 继承 `DefaultAccount`
- [ ] `Character` 继承 `DefaultObject`
- [ ] `Room` 继承 `DefaultObject`
- [ ] `World` 继承 `DefaultObject`
- [ ] `Exit` 继承 `DefaultObject`

## 图结构验收

- [ ] `Node` 表包含：id/uuid/type_code/name/description/attributes
- [ ] `Relationship` 表包含：id/source_id/target_id/type/properties
- [ ] 查询 Room 的所有出口（通过 Relationship）成功
- [ ] 查询账号/角色的当前位置（以 `Node.location_id` 为真源）成功；`LOCATED_IN` 类关系不得作为 `look` / movement 的位置真源

## Agent Runtime P0/P1 验收

- [x] mandatory tool evidence 在同一 tick 内跨 Plan / Do / retry Plan / retry Do 汇总；Do 或 retry 阶段成功 ToolObservation 可满足 mandatory。
- [x] mandatory gap 对 missing、permission denied、budget skipped、tool failure 保持可诊断；trace 包含 `checked_phases`、`observed_tools`、`observed_phases_by_tool`。
- [x] mandatory gap 允许一次 bounded repair retry；retry 后仍未满足时追加短系统提示，且不覆盖已有助手正文。
- [x] mandatory fallback 的 machine trace / log 保持结构化；完整结构化用户失败块列为 P1 后续增强。
- [x] ToolObservation 默认按 `interaction_profile` 采用 `full`（read）/ `summary`（mutate）；`system_command_ability.attributes.agent_observation_policy` 可 ops 覆盖 observation；未知命令与 `semantic_pending=true` 命令默认 `summary`。
- [x] summary 策略为确定性文本：首个非空行 + `original_chars=<n>`；默认不引入 hash。
- [x] `message_preview` 与实际注入 LLM 的 ToolObservation 使用同一观测策略，避免 trace 与 prompt 语义漂移。
- [x] AICO profile 提供专属运行时钩子；非 AICO tick 使用 no-op profile，不产生 AICO NDJSON/progress/observability 行为。
- [x] AICO informational manifest subset 只从 Worker 冻结的 `ResolvedToolSurface` 派生，不重新构造 `tool_allowlist` / 权限面。
- [x] `LlmPDCAFramework` 仅调用通用 observability adapter；AICO full-chain context 与日志实现由 profile adapter 注入。
- [x] LLM HTTP helper 不直接读取 AICO observability context；run/correlation 与 HTTP exchange 分发经通用 runtime observability context。
- [x] ToolObservation policy 在单次 gather 内按 `(command_name, tuple(args))` 缓存；重复命令与相同 args 不重复解析 ability policy。
- [x] AICO profile 不改变 F13 wire shape；当前阶段不新增真实 token streaming、全链路 cancel 或 live eval 强门禁。

## 用户生命周期验收

- [ ] 创建 User 时自动创建对应 Character
- [ ] Character 默认 spawn 到 SingularityRoom
- [ ] `User.find_by_email()` 查询成功
- [ ] `Character.find_by_user_id()` 查询成功

## 组件系统验收

- [ ] `InventoryMixin` 提供 add_item/remove_item/get_items 方法
- [ ] `StatsMixin` 提供 get_stat/set_stat/increase_stat 方法
- [ ] 模型可通过 mixin 组合获得多个组件能力
