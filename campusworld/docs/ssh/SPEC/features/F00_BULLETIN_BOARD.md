# Feature TODO - SingularityRoom 公告栏（公共栏）

> 本文件是公告栏特性的工程化 TODO 设计，作为 SSH 模块的特性规范唯一来源。  
> 核心约束：先定义“公告栏类型（BulletinBoard）”，并在奇点屋放置“系统唯一单例公告栏对象”；通知内容由新增管理模块维护。  
> 设计原则：参考 Evennia 的“对象化公告栏 + 消息列表/详情”模式，且**不修改 `backend/app/models/graph.py`**。

## 验收追踪

- 统一验收文档（系统入口/会话稳定性）：`docs/ssh/SPEC/ACCEPTANCE.md`
- 特性规范位置：`docs/ssh/SPEC/features/F00_BULLETIN_BOARD.md`

### 场景映射（最小集）

| 场景 | 触发 | 期望 | 映射 |
|---|---|---|---|
| 列表浏览（成功） | `look board` | 返回第 1 页标题列表（10 条/页） | SPEC: Interaction 1 |
| 分页越界（降级） | `look board next` 超过末页 | 停留末页并提示 | SPEC: Pagination |
| 详情渲染失败（降级） | Markdown 渲染异常 | 退化为纯文本 | SPEC: Failure/Degradation |
| 空公告栏（成功但为空） | 无 published 通知 | 返回“暂无系统通知”+ 操作提示 | SPEC: Failure/Degradation |

## 架构定位（先决约束）

- [ ] **公告栏类型（BulletinBoard Type）**
  - 在模型层新增公告栏对象类型（例如 `app/models/system/bulletin_board.py`），继承现有基础对象体系（`DefaultObject`）。
  - 该类型负责“公告栏对象语义”和对 Service 的调用，不直接承载复杂查询逻辑。

- [ ] **奇点屋唯一单例对象（Singleton Object）**
  - 通过 `RootNodeManager` 启动流程确保奇点屋中仅存在一个系统公告栏对象。
  - 采用稳定标识（如固定 `key/tag` 或固定 `uuid`）实现“幂等查找 -> 不存在则创建”。
  - 禁止每次登录重复生成公告栏对象。

- [ ] **不改 graph.py**
  - 不在 `graph.py` 增减字段/类型定义代码。
  - 公告栏业务字段与通知条目内容由新增“公告栏管理模块”在现有 `Node.attributes` 体系内组织与查询。

- [ ] **统一 look 交互（无公告栏特判分支）**
  - `look bulletin_board` 与 `look <other_object>` 复用同一命令分发与对象描述流程。
  - 公告栏仅作为对象类型差异（`system_bulletin_board`），不作为命令类型差异。
  - 参考 Evennia：对象通过自身外观方法返回描述，命令层不承担业务拼接。

## 里程碑（建议）

- **M1（读路径）**：`look bulletin_board` 列表 + `look bulletin_board <index>` 详情跑通，具备基础测试。
- **M2（体验增强）**：分页上下文（next/prev/page）、长文本分段与输出稳定性。
- **M3（写路径）**：管理员发布/编辑/归档（命令 + 权限 + 审计）。

---

## A. DataModel（图节点 + 公告栏对象语义）

### A1. 定义公告栏类型与系统单例对象

- [ ] **新增 BulletinBoard 对象类型（不改 `graph.py`）**
  - **修改点（建议）**：
    - 新增：`backend/app/models/system/bulletin_board.py`
    - 更新：`backend/app/models/root_manager.py`（确保奇点屋中的公告栏单例对象）
  - **对象语义字段（公告栏对象自身）**：
    - `board_key`: 固定值（如 `system_bulletin_board`）
    - `desc`: `这是系统公告栏，提供系统通知`
    - `entry_room`: `singularity_room`
    - `display_name`: `公共栏`
  - **DoD**：
    - 系统初始化后奇点屋内始终只有 1 个公告栏对象。
    - 重复初始化不产生重复对象（幂等）。

### A2. 定义系统通知对象类型（`system_notice`）

- [ ] **定义 `system_notice` 作为独立对象类型（通过管理模块写入/读取）**
  - **修改点（建议）**：
    - 新增：`backend/app/services/system_bulletin_manager.py`
    - 更新：`backend/db/seed_data.py`（可选，补充默认通知数据）
  - **字段规范（写入 `Node.attributes`）**：
    - `title`（必填，1-120）
    - `content_md`（必填，Markdown）
    - `status`：`draft|published|archived`
    - `is_active`：bool（逻辑下线）
    - `published_at`：ISO8601（`status=published` 必须存在）
    - `author_id`：账号节点 ID（或 uuid，需统一）
    - `tags`：string[]
    - `priority`：`low|normal|high`
    - `updated_at`：ISO8601
  - **DoD**：
    - 图数据库可查询到 `type_code="system_notice"` 的通知节点。
    - 具备至少 1 条可被普通用户读取的 `published + active` 通知。

### A3. 查询过滤/排序/分页约束

- [ ] **实现统一查询约束（published + active + 倒序 + 分页）**
  - **规则**：
    - 过滤：`attributes.status == "published"` 且 `is_active == True`
    - 排序：`attributes.published_at DESC`（缺失时按 `created_at DESC` 降级）
    - 分页：`page_size = 10`，offset/limit
  - **DoD**：
    - 列表接口返回 `total/total_pages/items`，items 仅包含发布且有效的通知。

---

## B. Service 层（`BulletinBoardService` + `SystemBulletinManager`）

### B1. 服务模块与接口契约

- [ ] **新增服务模块：`backend/app/services/bulletin_board.py`**
  - **对外接口（建议）**：
    - `list_notices(page: int, page_size: int = 10) -> {items,total,total_pages,page,page_size}`
    - `get_notice_by_page_index(page: int, index: int, page_size: int = 10) -> notice|None`
    - `get_notice_by_id(notice_id: int|str) -> notice|None`
    - `render_notice_md_to_terminal(content_md: str) -> str`
  - **依赖**：
    - 调用 `SystemBulletinManager` 统一访问公告条目，避免命令层直连 ORM。
  - **错误处理**：
    - DB 异常：抛出可识别错误或返回空并记录日志（但不让 SSH 会话崩溃）
    - 渲染异常：降级为纯文本
  - **DoD**：
    - Service 单元测试可覆盖分页、排序与异常降级。

### B2. 通知管理模块（Evennia 风格抽象）

- [ ] **新增通知管理模块：`backend/app/services/system_bulletin_manager.py`**
  - **职责**：
    - 管理通知条目 CRUD（至少 read + publish/update/archive 契约）
    - 封装 `system_notice` 查询规则与写入校验
    - 向上提供稳定 DTO，向下屏蔽 `Node` 细节
  - **DoD**：
    - `BulletinBoardService` 不直接拼装底层筛选条件。
    - 后续管理员命令可直接复用该模块。

### B3. 数据访问与 Session 管理

- [ ] **统一使用 `db_session_context()`**
  - **修改点（建议）**：服务层内部禁止裸用 `SessionLocal()`，全部走 `app.core.database.db_session_context()`。
  - **DoD**：
    - 不引入新的 session 泄漏与事务悬挂风险。

---

## C. Commands & UX（`look 公共栏`）

> 交互入口以 `look` 为主，保持 Evennia 风格“对象化入口”；命名统一采用英文对象名。

### C1. 命令解析：公共栏入口与别名

- [ ] **扩展 `look` 命令识别公共栏目标**
  - **修改点（建议）**：`backend/app/commands/game/look_command.py`
  - **支持输入**：
    - `look bulletin_board`别名
    - `look bulletin`别名
    - `look board`
  - **DoD**：
    - 识别目标后，进入统一对象描述流程；公告栏对象返回列表视图（第 1 页）。

### C0. 统一命令/对象描述链路（先于 C1）

- [ ] **建立统一 look -> object description 调用路径**
  - **修改点（建议）**：
    - `backend/app/commands/game/look_command.py`：只做目标解析与调用
    - 新增或扩展对象方法：`backend/app/models/system/bulletin_board.py`
  - **对象方法建议**：
    - `get_display_name()`
    - `get_appearance(context)`（或项目现有等价接口）
  - **DoD**：
    - 命令层不直接拼公告栏列表文本。
    - 公告栏与其他对象在命令层无分支差异。

### C2. 命令解析：分页

- [ ] **支持分页操作（会话级上下文）**
  - **支持输入**：
    - `look board next`
    - `look board prev`
    - `look board page <n>`
  - **输出规范（必须包含）**：
    - 页信息：`第 {page}/{total_pages} 页`
    - 操作提示：详情/next/prev/page
  - **DoD**：
    - 越界行为：停留边界页并给出提示。

### C3. 命令解析：详情查看

- [ ] **支持按页内序号查看详情**
  - **支持输入**：`look bulletin_board <index>`
  - **规则**：
    - 序号指当前页 1..N
    - 非法序号返回错误提示（不抛异常）
  - **DoD**：
    - 详情输出包含 title/published_at/author + Markdown 渲染正文。

### C4. 命令解析：按稳定 ID 查看（管理员/脚本友好）

- [ ] **支持 `look 公共栏 id <notice_id>`**
  - **支持输入**：`look bulletin_board id <notice_id>`
  - **DoD**：
    - 可直接定位并展示指定通知详情（同样按权限过滤：普通用户不可看 draft/archived）。

### C5. 输出稳定性（终端渲染/换行）

- [ ] **保证输出长度与换行不破坏 SSH 交互**
  - **修改点（可能）**：`backend/app/ssh/console.py` 的输出逻辑（仅在必要时调整）。
  - **DoD**：
    - 长详情不会导致提示符错位、乱码或会话中断。

### C6. 对象描述模板统一

- [ ] **统一对象描述模板（公告栏与普通对象一致）**
  - **规则**：
    - 第一行显示对象显示名（如 `bulletin_board` / `stone`）
    - 后续为对象描述正文（公告栏对象正文为动态列表或详情）
    - 末尾可选操作提示（仅公告栏对象追加分页/详情提示）
  - **DoD**：
    - 用户感知为“同一种 look，不同对象不同内容”，而非“特殊命令”。

---

## D. 会话分页上下文（不跨会话）

### D1. 上下文存放位置选择

- [ ] **确定并实现“当前页”存放点**
  - **方案 A（优先）**：`backend/app/ssh/session.py` 为 `SSHSession` 增加 `bulletin_page` 字段
  - **方案 B**：`CommandContext.metadata` 中维护（需确保每次命令创建 context 时可读写回 session）
  - **DoD**：
    - 同一会话多次 `look bulletin_board next` 能正确累计页码。
    - 断开重连后页码重置（符合“不跨会话”约束）。

---

## E. Markdown 渲染（安全子集 + 降级）

### E1. 安全子集渲染器

- [ ] **实现 Markdown -> 终端文本渲染（安全子集）**
  - **实现位置**：`BulletinBoardService.render_notice_md_to_terminal` 或独立模块 `backend/app/utils/markdown_terminal.py`
  - **支持**：标题/列表/引用/代码块/粗体斜体/链接文本
  - **禁止**：HTML/脚本/远程资源自动加载
  - **链接规则**：`[text](url)` -> `text (url)`
  - **DoD**：
    - 渲染失败时返回纯文本（记录 `bulletin_render_degraded`）。

### E2. 长文本分段输出

- [ ] **实现“渲染后分段”策略**
  - **规则**：超过阈值按段落或按行切分输出（避免单次写入过大）。
  - **DoD**：
    - 详情超长时仍能完整阅读，不破坏提示符。

---

## F. Admin 写路径（契约先行，后续实现）

### F1. 命令契约（可先只写 TODO，不强制实现）

- [ ] **定义管理员命令集合**
  - **建议命令**：
    - `notice publish <title>`（多行正文输入，或读取文件）
    - `notice edit <id>`
    - `notice archive <id>`
  - **权限**：`admin.system_notice`
  - **审计**：记录操作者、时间、notice_id、摘要（title、status 变化）
  - **DoD**：
    - 写路径不阻塞 M1/M2；但契约清晰可实现。

---

## G. Observability（日志与审计）

- [ ] **定义并实现日志事件名与字段**
  - `bulletin_list_view`：user_id/page/page_size/total
  - `bulletin_detail_view`：user_id/notice_id
  - `bulletin_render_degraded`：notice_id/error_type
  - **DoD**：
    - 关键路径日志可追踪“用户看过什么/系统是否降级”。

---

## H. Tests（单元/集成）

### H1. 单元测试

- [ ] `BulletinBoardService.list_notices`：过滤/排序/分页
- [ ] `render_notice_md_to_terminal`：渲染规则与降级
- [ ] `look` 解析：公共栏/分页/详情/id

### H2. 集成测试（最小）

- [ ] 通过测试 DB/事务回滚，插入 15 条通知，验证：
  - 第 1 页 10 条
  - next 后第 2 页 5 条
  - 详情输出包含 title + 正文

---

## I. 最小回归清单（实现完成后）

- [ ] `look bulletin_board`：显示标题列表（最新到最旧，10 条/页）
- [ ] `look bulletin_board` 与 `look <other_object>` 使用同一命令分发与对象描述链路
- [ ] `look bulletin_board next/prev/page <n>`：分页正确且越界提示
- [ ] `look bulletin_board <index>`：详情可读，Markdown 渲染正确
- [ ] 奇点屋仅存在一个公告栏系统对象（单例约束）
- [ ] 通知为空时返回“暂无系统通知”
- [ ] Markdown 渲染失败时降级为纯文本且记录日志
