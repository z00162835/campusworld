# F02 设计闸门：已决方案（对齐全文交付计划 §1.4）

> 本文件在实现阶段前锁定**默认路径**，与 [F02_COMMAND_SYSTEM_I18N_AND_AGENT_FRIENDLY_DESCRIPTIONS.md](F02_COMMAND_SYSTEM_I18N_AND_AGENT_FRIENDLY_DESCRIPTIONS.md) 及交付计划中的 Design gate 一致。若变更某条，应更新本表并视情况补 ADR。

| ID | 决策点 | 已选方案 | 说明 |
|----|--------|----------|------|
| D1 | Locale 归一化 | **A：BCP 47 + 别名表** | 见 `app/commands/i18n/locale_text.py` 的 `normalize_locale` |
| D2 | manifest × 每用户语言 × worker | **A：v1 仅系统默认 locale 进 manifest** | `build_llm_tool_manifest` 使用 `app.default_locale`（`settings.yaml` → `AppConfig.default_locale`），**不**随 `resolve_locale`（用户 `help` 语言可与之不一致）；Worker 在创建时按该默认生成 manifest 文本，与现「worker 内缓存一份 manifest」一致。**AICO 侧**：仅 `build_llm_tool_manifest` 产出面向 LLM 的 manifest 文本与最终 `ToolSchema.description`；`tool_schemas_from_surface` 只作中间列表，描述在 manifest 内按 `tool_manifest_locale()` 重写，无第二条 per-user 路径 |
| D3 | locale 注入 manifest | **A：显式参数** | `build_llm_tool_manifest(..., locale: Optional[str] = None)`；`None` → `tool_manifest_locale(None)`（即 `app.default_locale`） |
| D4 | help 外壳 | **A 方向：集中 shell 文案** | `help_shell_for_locale` + `BaseCommand.get_detailed_help_for_locale`；全量多语可随迁移渐进 |
| D5 | search_commands | **C：只搜当前上下文的展示语言** | 有 `context` 时用 `resolve_locale(context)`，仅匹配 `get_localized_description(loc)` + 命令名/别名；无 `context` 时用 `DEFAULT_LOCALE`（与默认 help 一致） |
| D6 | CI 门禁 | **C 起步**：以测试与规范约束为主，全仓硬扫描另立里程碑 | 与 F02 §5.5 不冲突时可加 warn |
| D7 | 发布顺序 | **A** | 对账/健康可与文案迁移分 PR |
| D8 | 人类文案权威 | **A** | 注册表/代码为默认；`system_command_ability.llm_hint*` 为 Agent 覆盖与发现 |

**修订日期**：以 Git 历史为准；首版对齐全文计划中的 Design gate 验收项。
