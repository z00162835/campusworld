# `primer`

> **Architecture Role**: 长文系统导读（SYSTEM）；从包内/仓库约定路径装载 primer 文本，与 `CAMPUSWORLD_SYSTEM_PRIMER.md` 同体系；子 flag 与权限间关系以实码为准。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `primer` |
| `CommandType` | SYSTEM |
| Class | `app.commands.system_primer_command.PrimerCommand` |
| Primary implementation | [`backend/app/commands/system_primer_command.py`](../../../../backend/app/commands/system_primer_command.py) |
| Locale | `commands.primer`（正文来自 `build_ontology_primer`） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases（registry）**: `manual` 等，见快照。

## Synopsis

```
primer
primer <section>
primer --toc
primer --raw
primer --for <service_id>
```

- 来源：`get_usage()` → `primer [<section> | --toc | --raw | --for <service_id>]  (prefer <section> over full doc)`。
- `<section>` 取 `primer_toc()` 列出的键（identity/structure/ontology/world/actions/interaction/memory/invariants/examples）。
- `--raw` 需 `admin.doc.read`；`--for <id>` 需 `admin.agent.read`。

## Implementation contract

- `_parse_args`：`--toc` 仅节标题列表；`--raw` 需 `admin.doc.read` 否则 `primer --raw requires permission 'admin.doc.read'`；`--for <id>` 需 `admin.agent.read` 否则对应错误；其余未知 flag 报错；重复 section 也报错。
- 否则 `build_ontology_primer(section=?, for_agent, raw, session, primer_command_context=...)`；`ValueError` / `FileNotFoundError` 为 `error_result(str(e))`；成功为纯长文本 `message`。

**参考文档路径**：`docs/models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md`（在 `build_ontology_primer` 中解析，非本文件重述）。
