# Generated registry snapshot

- **`registry_snapshot.json`**: 由 `backend/scripts/export_command_registry_snapshot.py` 生成，记录 `initialize_commands()` 后注册表中的每个命令主名、类型、别名、实现类与源文件路径。
- **用途**: 与 `docs/command/SPEC/features/CMD_*.md` 对账、在 SPEC 元数据中锚定「当时」的实现位置。

重新生成（在 `backend` 目录、使用项目 Conda 环境）:

```bash
cd backend
conda run -n campusworld python scripts/export_command_registry_snapshot.py
```

无 PostgreSQL 时，建造子命令 `create` / `create_info` 可能未注册；快照中会有 `warning`，SPEC 仍应以能成功跑通初始化环境为准。
