# TODO - 命令系统开发任务

## 待实现命令

### 高优先级

- [ ] **方向移动命令** `go [方向]`
  - 解析方向（north/south/east/west/n/s/e/w）
  - 查找当前房间的 Exit
  - 移动到目标房间
  - 返回新房间信息
  - 权限：GAME

- [ ] **say 命令** `say [内容]`
  - 在当前房间广播消息
  - 格式：`[username] 说："内容"`
  - 权限：GAME

- [ ] **whisper 命令** `whisper [玩家] [内容]`
  - 私聊其他玩家
  - 权限：GAME

- [ ] **help 命令增强**
  - `help` — 列出所有可用命令
  - `help [命令]` — 特定命令详细帮助
  - 权限：SYSTEM

### 中优先级

- [ ] **inventory 命令** `inventory` / `i`
  - 查看角色背包
  - 权限：GAME

- [ ] **take 命令** `take [物品]`
  - 从当前房间拾取物品到背包
  - 权限：GAME

- [ ] **drop 命令** `drop [物品]`
  - 从背包丢弃物品到当前房间
  - 权限：GAME

- [ ] **stats 命令** `stats`
  - 查看角色状态（能量/饱食度/知识/社交）
  - 权限：GAME

- [ ] **who 命令增强**
  - 显示在线用户列表
  - 显示每个用户的当前位置
  - 权限：SYSTEM

### 低优先级

- [ ] **emote 命令** `emote [动作]`
  - 角色动作表达（`*动作*` 格式）
  - 权限：GAME

- [ ] **tell 命令** `tell [玩家] [内容]`（与 whisper 合并）

- [ ] **follow 命令** `follow [玩家]`
  - 跟随其他玩家移动
  - 权限：GAME

- [ ] **pose 命令** — 同 emote

## 命令注册检查清单

- [ ] 所有命令继承 `BaseCommand`（或其子类）
- [ ] 所有命令在 `init_commands.py` 中导入或通过自动发现注册
- [ ] 命令名和别名不冲突
- [ ] 每个命令有 `description` 和 `aliases`

## 命令执行测试检查清单

- [ ] `look` 返回房间名称 + 描述 + 出口列表
- [ ] `go north` 移动成功并返回新房间信息
- [ ] `go north` 当前房间无北出口时返回错误
- [ ] `say hello` 在房间广播消息
- [ ] 无权限用户执行 ADMIN 命令返回权限不足
- [ ] `help` 列出所有可用命令