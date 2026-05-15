# CampusWorld 术语表（中英）

供 SPEC、实现与 **日志文案** 引用。用户可见 UI、API `detail`、docstring 的中文不改；本表侧重 **运维日志英文** 与 **代码内日志字符串** 的一致性。

## 规范决策（摘要）

| ID | 决策 |
|----|------|
| D1 | 中文「园区世界」在日志中等价为产品名 **CampusWorld**（非 “Campus Life”）。 |
| D2 | 不扩大范围：除日志外，其它中文文案暂不批量改写。 |
| D3 | 允许工具重写带来的大范围格式 diff（如 AST unparse）。 |
| D4 | 后端应用日志一律英文；规范见根目录与各子包 `AGENTS.md`。 |
| D5 | 非日志实现细节暂不处理。 |
| D6 | 前端 `console.*` 等与调试输出相关的文案一律英文。 |
| D7 | 日志里「场景」统一用 **world**（如 `world '{id}'`），不用 game/scene。 |
| D8 | 日志里「场景引擎」统一为 **World Engine**（与代码目录 `game_engine` 并存；日志用语以本表为准）。 |
| D9 | 「场景世界」在日志中用 **worlds**（如 `Failed to initialize worlds`）；仅为日志表达，不要求写入其它 SPEC。 |
| D10 | **singularity room** 统一覆盖奇点屋/奇点房间，不使用 singularity hub。 |
| D11 | 日志中称参与者一律 **user**（非 player）；项目借鉴 MUD，不作为游戏系统表述。 |

## 已定术语（日志 / SPEC 引用）

以下英文用于后端 `logger` / `logging` 及前端 `console.*` 等 **调试与运维输出**，除非 SPEC 另有约定。

| 中文（语境） | 英文 | 说明 |
|--------------|------|------|
| 园区世界 | **CampusWorld** | 与产品名一致；世界包日志中表示该运行时整体。 |
| CampusWorld 系统 | **CampusWorld system** | 进程/服务级启停。 |
| 场景引擎 | **World Engine** | 日志用语；代码包名仍为 `game_engine`。 |
| 场景（命令/模块/状态等日志前缀） | **world** | 例：`world '{name}'`、`Register world`、`World initialized`。 |
| 场景世界（聚合/初始化失败等） | **worlds** | 例：`Failed to initialize worlds`、`Failed to get state for all worlds`。 |
| 奇点屋 / 奇点房间 | **singularity room** | 同一英文；降级路由日志：`falling back to singularity room`。 |
| 玩家 | **user** | 日志统一；代码字段名 `player_id` 等可保留，仅消息模板用 user。 |
| 命令 | **command** | |
| 钩子 | **hook** | |
| 对象（图/同步） | **object** | |
| 内容引擎 | **content engine** | 与 World Engine 分层并存（内容装载 vs 运行时宿主）。 |
| 图数据库 / 图节点 / 图数据 | **graph database** / **graph node** / **graph data** | |
| 根节点 | **root node** | |
| 节点类型 / 关系类型 | **node type** / **relation type** | |
| 公告栏（系统公告） | **bulletin board** | |
| 认证 / 登录 / 权限 | **authentication** / **login** / **permission** | |
| 会话 | **session** | |
| 通道 | **channel** | |
| 传输层 | **transport** | |
| 数据库（操作/会话） | **database** | |

## 待复核项（语境敏感）

下列条目与实现/合规相关，与「场景/worlds」正交；若 SPEC 或合规策略变更，更新本表并必要时批量替换日志。

| 概念 | 当前日志英文 | 可选表述 | 备注 |
|------|----------------|----------|------|
| campus（园区） | **campus** | site / estate | |
| builder（建造命令） | **builder** | construction | |
| rate limiter | **rate limiter** | throttling | |
| whitelist | **whitelist** | allowlist | |

## 维护

- 新增中文日志前：先在本表增加一行 **已定术语**，再写英文日志文案。
- 批量迁移脚本：`backend/scripts/rewrite_logger_zh_messages.py`，映射数据：`backend/scripts/logger_fragment_en.json`（由 `compose_logger_fragment_en_json.py` 生成）。
