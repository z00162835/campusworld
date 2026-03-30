# 命令系统验收检查表

## 基础功能验收

- [ ] `BaseCommand.execute()` 返回 `CommandResult`（非 None）
- [ ] `CommandRegistry.get_command("look")` 能找到 look 命令
- [ ] `CommandRegistry.get_command("l")` 能找到 look 命令（别名）
- [ ] `CommandRegistry.execute("look", context, [])` 正常执行
- [ ] 未知命令 `CommandRegistry.execute("foo", ...)` 返回错误

## 权限验收

- [ ] SYSTEM 命令对所有用户开放
- [ ] GAME 命令需要对应 `game.[name]` 权限
- [ ] ADMIN 命令需要 `admin` 权限
- [ ] 权限不足时返回 `CommandResult.success=False`

## 状态机验收

```
输入 "look"
    ↓ 解析
找到 LookCommand
    ↓ 检查权限
通过
    ↓ 执行
返回房间描述
    ↓ 验证
CommandResult.success == True
```

## SSH 集成验收

- [ ] SSH 终端输入 `look` 返回房间描述
- [ ] SSH 终端输入 `help` 返回命令列表
- [ ] SSH 终端输入 `who` 返回在线用户

## 性能验收

- [ ] 命令解析 + 执行总耗时 < 50ms
- [ ] 命令注册表初始化 < 100ms