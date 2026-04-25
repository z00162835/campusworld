# 命令展示文案（集中配置）

- 每语言一个文件：[`zh-CN.yaml`](zh-CN.yaml)、[`en-US.yaml`](en-US.yaml)。
- 键路径：`commands.<command_name>.description`（与注册命令 `name` 一致，含方向命令 `north` 等）。
- **修改流程**：只改本目录 YAML，保存后进程内缓存由 `get_bundle_by_tag` 管理；热重载需重启服务或调用 `command_resource.get_bundle_by_tag.cache_clear()`（调试用）。

优先从资源读取；若某命令在 YAML 中无条目，才回退到代码里的 `BaseCommand.description` 或已废弃的 `description_i18n`。

AICO/图节点 `llm_hint*` 与 `app.default_locale` 对齐，详情见 `docs/command/SPEC/features/F02_DESIGN_DECISIONS.md`。
