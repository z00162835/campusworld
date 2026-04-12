# F10 - 本体与图谱原子服务 REST API（SPEC 初稿）

> **Architecture Role**：在 **系统适配层** 提供面向 **知识本体** 的 HTTP 资源接口，与 [`docs/models/SPEC/SPEC.md`](../../../models/SPEC/SPEC.md)、[`docs/database/SPEC/SPEC.md`](../../../database/SPEC/SPEC.md) 中的 **`node_types` / `relationship_types` / `nodes` / `relationships`** 模型对齐。本文件为 **契约初稿**，实现以 OpenAPI 3.x 导出为准。

## Goal

- 为管理端、Agent、运维工具、应用端提供 **原子化**、**名词化资源** 的 CRUD 与查询能力，支撑世界语义的 **类型层（ontology）** 与 **实例层（graph）** 管理。
- API 设计与文档 **符合可引用的业界规范**（OpenAPI、HTTP 语义、RFC 9457 Problem Details 等），便于契约测试与版本演进。

## Non-Goals（v1 明确不做）

- 不替代 **世界包安装/校验/图种子流水线**（`world install|reload|validate`、[`F03_GRAPH_SEED_PIPELINE`](../../../games/hicampus/SPEC/features/F03_GRAPH_SEED_PIPELINE.md)）；本服务仅暴露 **运行时库中的类型与实例**，大规模拓扑仍以包与 seed 为主。
- 不在 v1 提供 **任意图查询语言**（Cypher/GSQL）、**跨资源长事务**、**无界深度遍历**。
- 不在本 API 内嵌 **SSH/命令行语义**；编排层可组合调用 [`/command`](../SPEC.md) 与本服务。

## 服务边界：原子类能力

| 维度 | 说明 |
|------|------|
| **有界上下文** | 仅 **ontology**（`NodeType` / `RelationshipType`）与 **graph**（`Node` / `Relationship`）的持久化读写与列表过滤。 |
| **编排外置** | 世界入口、奇点屋、游戏逻辑、Agent 策略由其他模块负责；本服务 **不** 编排 `world` 命令或批处理任务。 |
| **版本** | 挂载在现有 **`/api/v1`** 前缀下（与 [`backend/app/api/http_app.py`](../../../../backend/app/api/http_app.py) 一致）。 |
| **兼容策略** | v1 发布后，对公开字段 **_additive** 演进（新增可选字段、新 query 参数）；**破坏性变更** 需 v2 或协商弃用期（SPEC 实现阶段补充日历）。 |

## 读者与职责分界

| 消费者 | 用途 |
|--------|------|
| 管理 UI / 运维 | 类型注册表维护、实例排查、trait 过滤列表 |
| 应用 UI/ Agent / 集成系统 |实例搜索 或按world进行实例搜索 或 按 `trait_class` / `trait_mask` 检索候选节点、读本体 Schema |
| 开发者 | OpenAPI 生成客户端、契约测试 |

**与现有 API**：`/auth`、`/accounts` 面向身份与账号节点；`/command` 面向命令执行；**本服务** 面向 **通用图与本体数据面**，职责不重叠。

## 持久化与 ORM 映射

| REST 资源（逻辑） | 表 / ORM | 说明 |
|-------------------|----------|------|
| `node-types` | `node_types` / `NodeType` | `type_code` 唯一；`schema_definition`、`trait_class`、`trait_mask` 等 |
| `relationship-types` | `relationship_types` / `RelationshipType` | `type_code` 唯一 |
| `nodes` | `nodes` / `Node` | `type_id` FK；`attributes` JSONB；`trait_*` 实例副本 |
| `relationships` | `relationships` / `Relationship` | `source_id` / `target_id`；`trait_*` 实例副本 |

术语以 [`docs/database/SPEC/SPEC.md`](../../../database/SPEC/SPEC.md) 为准（**非** 历史名 `graph_nodes` / `graph_edges`）。

## 规范符合性（评审约束）

以下条款为 **v1 实现与文档评审** 的硬约束；与现有 FastAPI 默认行为冲突时，SPEC 要求 **统一错误映射**（见下节）。

### OpenAPI 3.x

- 以 **OpenAPI 3.0+** 为契约真源：paths、parameters、requestBody、responses、`components.schemas`、`components.securitySchemes`。
- 每个 operation 具备稳定 **`operationId`**（建议 `listNodeTypes`、`getNode` 等 camelCase）。
- 安全方案（**并存，单次请求二选一**）：
  - **`bearerAuth`**：`Authorization: Bearer <JWT>`，与现有 [`/auth` 登录](../SPEC.md) 一致，承载 **用户主体** 与角色/权限。
  - **`apiKeyAuth`**：见下文 **「API 授权与访问方案」**；OpenAPI 登记为 `type: apiKey`（推荐 `name: X-Api-Key`，`in: header`），并在描述中说明可与 **`Authorization: ApiKey <secret>`** 等价实现（实现任选其一或双支持，**文档只选一种 canonical** 以降低客户端分叉）。
- 实现阶段：与 FastAPI 自动文档一致，并可导出静态 **`openapi.json`** 供 CI 做 breaking-change 检测。

### HTTP 语义

- 资源路径：**复数名词**，kebab-case（例：`/ontology/node-types`，实现可选用 `_` 与网关统一，但 **文档与 OpenAPI 唯一真源** 固定一种）。
- `GET`：**安全**（无副作用）、**幂等**；列表响应可带缓存控制头（`Cache-Control` 策略实现阶段定义）。
- `POST` 创建：成功返回 **201 Created**，响应头 **`Location: /api/v1/graph/nodes/{id}`**（`id` 为整数主键；或等价绝对 URL）；正文返回完整或精简资源表示（实现二选一并写入 OpenAPI）。
- `DELETE`：v1 约定为 **软删除**（`is_active=false`）或 **硬删除** 二选其一；**须在 OpenAPI 固定**，禁止混用无文档。
- **部分更新**：v1 采用 **`PATCH`**（JSON Merge Patch 子集或显式字段列表）；**不使用 `PUT` 全量替换** 作为 v1 默认，以降低客户端负担（若未来需要 `PUT`，在 v2 或扩展 operation 中引入）。

### 错误报告（RFC 9457）

- 错误响应 **`Content-Type: application/problem+json`**。
- 正文字段（最小集）：`type`（URI 引用，可指向本仓库文档锚点或 `about:blank`）、`title`、`status`、`detail`；可选 `instance`（请求唯一 id）。
- **过渡期**：若全局中间件尚未统一，允许 4xx/5xx 仍返回 FastAPI 默认 `{"detail": ...}`，但 **OpenAPI 同时声明** `application/problem+json` 为推荐消费格式，并在里程碑 Mx 前完成统一映射（实现 issue 跟踪）。

### 日期与标识

- 时间：**RFC 3339** / **ISO 8601**（含时区，建议 `Z` 或 `+00:00`）。
- 对外标识：响应体中 **同时暴露** 整数 **`id`**（与现有 DB 一致）与 **`uuid`**（`nodes` / `relationships` 的 UUID）。**路径参数**：`/graph/nodes/{id}`、`/graph/relationships/{id}` 等 **仅使用整数 `id`** 作为主键；`uuid` 不用于 v1 路径定位。新建资源客户端可选用 **`Idempotency-Key`**（Phase 2，见下文）。

### 分页与过滤

- 列表：**`offset` + `limit`** 参数名与 [`GET /accounts`](../../../../backend/app/api/v1/accounts.py) 对齐（可选用 `skip` 别名之一，**OpenAPI 只登记一种**）。
- **`limit` 上限**：默认上限 **100**，最大 **500**（实现可配置，SPEC 固定默认文档值）。
- 过滤：**可组合** 的简单子集——`type_code`、`is_active`、`is_public`、`trait_class`、`required_any_mask`、`required_all_mask`、`name_eq`、`name_like`、`tags_any`（语义见 F01）；**不** 实现完整 OData。**`trait_mask` 查询语义**：与 F01 一致，**`0` 表示不按位过滤**。
- `name_eq`：名称精确匹配；`nodes` 上匹配 `nodes.name`，`node_types/relationship_types` 上匹配 `type_name`。
- `name_like`：统一使用**小写参数名** `name_like`；`nodes` 上匹配 `nodes.name`，`node_types/relationship_types` 上匹配 `type_name`，并**统一按 `ILIKE` 实现**（大小写不敏感）。
- `tags_any`：统一使用逗号分隔字符串（例如 `tags_any=a,b,c`）表示任一标签命中；v1 不使用重复参数语法。
- Phase 2：cursor 分页、[**RFC 8288**](https://datatracker.ietf.org/doc/html/rfc8288) `Link` 头。

### 幂等与并发

- **v1**：不强制 **`Idempotency-Key`**；实现可在 `POST` 创建上预留头字段并 no-op。
- **v1**：**不** 要求 **`If-Match` / ETag** 乐观锁；并发更新以「后写覆盖」+ 审计日志为准；若产品要求锁，在 **v1.1** 引入 `version` 整型字段 + `If-Match`。

### 权限与审计

- **`graph.read` / `ontology.read` 不隐含全库或全类型可见**：在账号节点上另有 **数据范围**（`attributes.data_access`），与 RBAC **组合**（能力 ∧ 数据）。详见 **`F11`**：[`F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md`](F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)。

- 装饰器风格与 [`require_permission`](../../../../backend/app/core/authorization.py) 一致；建议权限前缀：

| 权限 | 用途 |
|------|------|
| `ontology.read` | `GET` node-types / relationship-types |
| `ontology.manage` | `POST`/`PATCH`/`DELETE` 类型资源 |
| `graph.read` | `GET` nodes / relationships |
| `graph.write` | `POST`/`PATCH`/`DELETE` 图实例 |
| `graph.admin` | 预留权限位；v1 不定义独立 `/admin/*` API |

- 响应可预留 **`X-Request-Id`** 或 Problem Details `instance`，便于与审计日志关联（实现占位）。

### 内容协商

- **Accept / Content-Type**：默认 **`application/json`**；v1 **不要求** 自定义 vendor MIME。

## API 授权与访问方案

本服务与现有 CampusWorld HTTP 栈一致：**先认证（谁）**，再 **鉴权（能否做）**。F10 端点在 OpenAPI 层使用 **`security: [bearerAuth]`、`security: [apiKeyAuth]`** 或 **`security: [{ bearerAuth: [] }, { apiKeyAuth: [] }]`**（OR 语义：任选一种凭据）。

### 方案总览

| 方案 | 典型场景 | 凭据位置 | 主体 |
|------|----------|----------|------|
| **JWT（Bearer）** | 管理端 UI、人机交互、复用账号权限 | `Authorization: Bearer <access_token>` | 登录用户（账号节点 + `User` JWT） |
| **API Key** | Agent、运维脚本、CI、服务间调用 | 见下节 | 服务主体（映射到内置或虚拟账号 + **受限 scope**） |

单次 HTTP 请求 **只使用一种** 凭据；若同时携带多种，返回 **400** 或 **401**（实现固定其一，并写入 OpenAPI）。

### JWT（Bearer）

- 流程：客户端 `POST /auth/login` 获取 `access_token`，后续请求带 **`Authorization: Bearer …`**。
- 权限解析：与现有 API 相同，从 token 载荷或会话解析 **角色 / permission 列表**，再与 `ontology.*`、`graph.*` 比对（见 [`require_permission`](../../../../backend/app/core/authorization.py) 及 HTTP 依赖链）。
- 过期与刷新：遵循全局认证 SPEC；F10 **不** 单独定义 token 格式。

### API Key

- **目的**：为 **非浏览器、长期运行、自动化** 的调用方提供凭据，避免嵌入用户密码；权限通过 **预绑定 scope** 收紧（最小权限）。
- **传输**：
  - **仅 HTTPS**；禁止在 URL query、referrer、日志明文规则外泄。
  - **推荐请求头**（OpenAPI `apiKey`）：**`X-Api-Key: <secret>`**。
  - **可选等价形式**：**`Authorization: ApiKey <secret>`**（与 `Bearer` 通过 scheme 前缀区分）；若实现只支持一种，须在文档与 `openapi.json` 中唯一标明。
- **密钥形态**：高熵随机串（例如 ≥32 byte 十六进制或 base64url）；服务端 **只存哈希**（如 HMAC-SHA256 或 Argon2id，含 pepper/盐策略由实现定）；**创建响应中仅一次返回明文**，之后不可回显。
- **数据模型（建议）**：`key_id`（公开标识）、`fingerprint`（截断哈希便于运维辨认）、`scopes[]`（permission 字符串子集）、`expires_at`、`revoked_at`、`last_used_at`、`created_by`；审计日志记录 `key_id`，**不**记录 secret。
- **鉴权失败**：**401** + RFC 9457；`detail` 泛化（如 “invalid credentials”），**避免**泄露「密钥不存在 / 已吊销 / 已过期」的细微差别，除非内网管理 API 单独策略。
- **与代码库关系**：[`backend/app/core/security.py`](../../../../backend/app/core/security.py) 中已有 `generate_api_key` / `verify_api_key` **占位**；F10 实现应落地 **持久化表 + 哈希校验 + scope 映射**，与本节对齐。

### 权限映射（两种凭据共用）

无论 JWT 还是 API Key，最终都归一为 **同一套 permission 字符串**（与上表 `ontology.read` 等一致）。API Key 的 `scopes` **不得** 超出创建者（或系统策略）允许的上限。

| F10 操作族 | 建议 permission |
|-----------|-----------------|
| 读类型表 | `ontology.read` |
| 写类型表 | `ontology.manage` |
| 读图实例 | `graph.read` |
| 写图实例 | `graph.write` |
| 危险管理动作（可选） | `graph.admin`（仅保留为预留权限位） |

### 网关与零信任（可选）

- **mTLS**、**WAF**、**每租户速率限制** 由部署架构处理；F10 在应用层仍必须做 **认证 + 权限检查**。
- **`X-Request-Id`**：入口生成并透传，便于与 API Key / 用户 id 一起写入审计。

<a id="tooling-http-clients"></a>

## 业界工具调用样例（HTTP 客户端）

本节说明如何用常见工具调用 **同一套** F10 与既有 `/api/v1` 接口；凭据与错误语义仍遵循上文 **JWT / API Key** 与 **RFC 9457**。

### 环境与 OpenAPI 入口

| 项 | 说明 |
|----|------|
| **Base URL** | 部署根地址，例如 `https://api.example.com`；本地开发多为 `http://127.0.0.1:8000`（端口以后端实际监听为准）。 |
| **API 前缀** | 业务路由统一在 **`/api/v1`** 下（如 `GET /api/v1/graph/nodes`）。 |
| **OpenAPI JSON** | FastAPI 默认 **`GET /openapi.json`**（与 `/api/v1` 并列，**无** `/api/v1` 前缀）。 |
| **交互文档** | **`GET /docs`**（Swagger UI）、**`GET /redoc`**（ReDoc）。 |

导入契约到 GUI 客户端时，通常填写：`{BASE_URL}/openapi.json`。

### curl

**OAuth2 密码模式登录**（与 `POST /api/v1/auth/login` 的 `OAuth2PasswordRequestForm` 一致；`username` 为校园账号名）：

```bash
BASE="http://127.0.0.1:8000"
TOKEN="$(curl -sS -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your_password" \
  | jq -r '.access_token')"
```

**Bearer 调用 F10 列表接口**：

```bash
curl -sS -G "$BASE/api/v1/graph/nodes" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "limit=50" \
  --data-urlencode "offset=0" \
  --data-urlencode "name_like=room"
```

**API Key**（推荐头 **`X-Api-Key`**；实现若支持 **`Authorization: ApiKey <secret>`** 亦可二选一，勿与 `Bearer` 同请求混用）：

```bash
curl -sS -G "$BASE/api/v1/ontology/node-types" \
  -H "X-Api-Key: cwk_<kid>_<secret>" \
  --data-urlencode "limit=20"
```

**查看 Problem Details**（4xx/5xx 时关注 `Content-Type` 与 JSON 体）：

```bash
curl -sS -D - -o /tmp/body.json "$BASE/api/v1/graph/nodes?name_like=%20" \
  -H "Authorization: Bearer $TOKEN" | head
cat /tmp/body.json
```

### HTTPie（httpie）

安装见 [HTTPie 文档](https://httpie.io/docs)；适合命令行可读输出。

```bash
export BASE=http://127.0.0.1:8000
http --form POST "$BASE/api/v1/auth/login" username=admin password=your_password
http GET "$BASE/api/v1/graph/nodes" "Authorization:Bearer $TOKEN" limit==50 offset==0
http GET "$BASE/api/v1/ontology/node-types" "X-Api-Key:cwk_<kid>_<secret>"
```

### Postman / Insomnia / Bruno（GUI）

共性步骤：

1. **Import OpenAPI**：从 URL 导入 `{BASE_URL}/openapi.json`，或下载 JSON 后本地导入。
2. **环境变量**：定义 `baseUrl`（如 `http://127.0.0.1:8000`）、`token`、`apiKey`。
3. **认证**：
   - **Bearer**：在 Collection / Request 的 **Auth** 中选 *Bearer Token*，填 `{{token}}`；或在 Header 中写 `Authorization: Bearer {{token}}`。
   - **API Key**：在 **Auth** 中选 *API Key*，`Key`=`X-Api-Key`，`Value`=`{{apiKey}}`，`Add to`=header。
4. **登录换 token**：对 `POST /api/v1/auth/login` 使用 **x-www-form-urlencoded**，字段 `username`、`password`；从响应复制 `access_token` 写入环境变量。

首次联调可用 **`/docs`** 中 “Try it out” 校验路径与参数是否与 OpenAPI 一致。

### OpenAPI Generator（生成强类型客户端）

适合在 CI 或仓库内固定契约版本后生成 Java / TypeScript / Python 等客户端（[OpenAPI Generator](https://openapi-generator.tech/)）。

```bash
# 示例：生成 Python 客户端到 ./out/cw-client（需本地已安装 openapi-generator-cli）
openapi-generator-cli generate \
  -i http://127.0.0.1:8000/openapi.json \
  -g python \
  -o ./out/cw-client \
  --additional-properties=packageName=campusworld_client
```

生成代码中通常可配置 `host`、默认 Header 中的 `Authorization` 或 `X-Api-Key`，与上文语义一致。

### Python（httpx / requests）

```python
import httpx

base = "http://127.0.0.1:8000"
with httpx.Client(base_url=base, timeout=30.0) as client:
    r = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "your_password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    token = r.json()["access_token"]

    nodes = client.get(
        "/api/v1/graph/nodes",
        params={"limit": 50, "offset": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    nodes.raise_for_status()
    print(nodes.json())
```

使用 API Key 时将 `headers` 改为 `{"X-Api-Key": "cwk_<kid>_<secret>"}` 即可。

### 浏览器与 CORS

浏览器发起的跨域请求若需携带 **`X-Api-Key`**，服务端 CORS 的 **`allow_headers`** 须包含该头（与 `Authorization` 并列）；纯服务端脚本不受此限制。

## Trait 与类型变更语义（F01）

- **实例 `nodes` / `relationships`**：写入请求体中若包含 `trait_class` / `trait_mask`，数据库层触发器将 **按 `type_code` 覆盖为类型表当前值**（见 [`F01`](../../../database/SPEC/features/F01_TRAIT_CLASS_MASK_FOR_AGENT.md)）。OpenAPI 应在 schema 上将二者标为 **readOnly** 或 **文档说明「写入忽略」**，避免调用方误解。
- **类型表 `trait_*` 变更**：产生 **最终一致性** 同步（`trait_sync_jobs` + worker）；API 可在响应中返回 **202** + 任务引用（可选），或 **200** + 说明「实例异步对齐」——实现阶段二选一并写入 SPEC 子节。
- **位语义常量**：客户端推荐使用 [`backend/app/constants/trait_mask.py`](../../../../backend/app/constants/trait_mask.py) 与 F01 表一致。

## 资源与操作（v1 草案表）

基路径：**`/api/v1`**。下列路径为逻辑名；实现时可挂载为 `ontology` / `graph` 子路由。

### Ontology

| Method | Path | 说明 | 建议权限 |
|--------|------|------|----------|
| GET | `/ontology/node-types` | 分页列表；支持 `type_code`、`parent_type_code`、`is_active`、`name_eq`、`name_like`、`tags_any` 过滤 | `ontology.read` |
| GET | `/ontology/node-types/{type_code}` | 详情（`type_code` 为 path 主键） | `ontology.read` |
| POST | `/ontology/node-types` | 创建类型 | `ontology.manage` |
| PATCH | `/ontology/node-types/{type_code}` | 部分更新（含 `schema_definition`、`trait_*` 等） | `ontology.manage` |
| DELETE | `/ontology/node-types/{type_code}` | 删除或停用（策略实现定稿；图种子类型应 **409** 或 **403**） | `ontology.manage` |
| GET | `/ontology/relationship-types` | 列表；支持 `type_code`、`is_active`、`name_eq`、`name_like`、`tags_any` 过滤 | `ontology.read` |
| GET | `/ontology/relationship-types/{type_code}` | 详情 | `ontology.read` |
| POST | `/ontology/relationship-types` | 创建 | `ontology.manage` |
| PATCH | `/ontology/relationship-types/{type_code}` | 部分更新 | `ontology.manage` |
| DELETE | `/ontology/relationship-types/{type_code}` | 删除/停用 | `ontology.manage` |

**图种子锁定（策略占位）**：若 `node_types.tags`（或约定字段）包含 `graph_seed`，则 **禁止** 修改 `trait_class` / `trait_mask` 或 **禁止** `DELETE`，返回 **409** + Problem Details `type` 说明冲突原因；只读扩展 `schema_definition` 是否允许由产品定稿。
**Ontology 名称过滤字段约定（v1 固化）**：`node_types` 与 `relationship_types` 的 `name_eq/name_like` 一律作用于 `type_name` 字段（不作用于 `type_code`）。

### Graph

| Method | Path | 说明 | 建议权限 |
|--------|------|------|----------|
| GET | `/graph/nodes` | 分页列表；过滤：`type_code`、`is_active`、`is_public`、`trait_class`、`required_any_mask`、`required_all_mask`、`name_like`、`tags_any` | `graph.read` |
| GET | `/graph/nodes/{id}` | **`id` 为整数主键**（`nodes.id`）；v1 **仅** 此路径定位节点详情，**不** 提供 `by-uuid` 并列端点；`uuid` 仅在响应体中供客户端缓存与关联 | `graph.read` |
| POST | `/graph/nodes` | 创建；body 含 `type_code`、`name`、`attributes` 等 | `graph.write` |
| PATCH | `/graph/nodes/{id}` | 部分更新 `name`、`description`、`attributes`、`location_id` 等 | `graph.write` |
| DELETE | `/graph/nodes/{id}` | 软删除（若 v1 定软删） | `graph.write` |
| GET | `/graph/relationships` | 列表；过滤：`source_id`、`target_id`、`type_code`、`is_active`、`name_eq`、`name_like`、`tags_any` | `graph.read` |
| GET | `/graph/relationships/{id}` | 详情 | `graph.read` |
| POST | `/graph/relationships` | 创建边；body：`source_id`/`target_id`/`type_code`/`attributes` | `graph.write` |
| PATCH | `/graph/relationships/{id}` | 更新属性等 | `graph.write` |
| DELETE | `/graph/relationships/{id}` | 停用边 | `graph.write` |

### World 范围（特定 world 的 Node/Relationship CRUD）

> 用于“仅在某个 world 作用域内操作图实例”。路径中的 `world_id` 作为**作用域约束**，实例主键仍使用整数 `id`。

| Method | Path | 说明 | 建议权限 |
|--------|------|------|----------|
| GET | `/worlds/{world_id}/nodes` | 列出某 world 下节点；支持 `type_code`、`is_active`、`is_public`、`trait_class`、`required_any_mask`、`required_all_mask`、`name_like`、`tags_any` 等过滤 | `graph.read` |
| GET | `/worlds/{world_id}/nodes/{id}` | 节点详情（要求节点属于该 world，否则 404） | `graph.read` |
| POST | `/worlds/{world_id}/nodes` | 在指定 world 创建节点；服务端强制写入/校验 `attributes.world_id = {world_id}` | `graph.write` |
| PATCH | `/worlds/{world_id}/nodes/{id}` | 更新节点（需属于该 world） | `graph.write` |
| DELETE | `/worlds/{world_id}/nodes/{id}` | 删除/停用节点（需属于该 world） | `graph.write` |
| GET | `/worlds/{world_id}/relationships` | 列出某 world 内关系；支持 `source_id`、`target_id`、`type_code`、`name_eq`、`name_like`、`tags_any` 过滤 | `graph.read` |
| GET | `/worlds/{world_id}/relationships/{id}` | 关系详情（要求关系两端节点都在该 world） | `graph.read` |
| POST | `/worlds/{world_id}/relationships` | 在指定 world 创建关系；要求 source/target 都属于该 world | `graph.write` |
| PATCH | `/worlds/{world_id}/relationships/{id}` | 更新关系属性（需属于该 world） | `graph.write` |
| DELETE | `/worlds/{world_id}/relationships/{id}` | 删除/停用关系（需属于该 world） | `graph.write` |

**与 `/graph` 下嵌套的 world 路径（双路径）**：实现中另登记 **`/graph/worlds/{world_id}/nodes`**、**`/graph/worlds/{world_id}/relationships`**（及带 `{id}` 的详情/变更操作），与上表 **`/worlds/{world_id}/...`** **语义一致**（同一服务、同一 F11 数据策略与 world 归属校验）。**文档、示例与集成测试优先使用 `/worlds/{world_id}/...`**，以避免与「全库」路径 `/graph/nodes` 混淆；客户端任选其一即可，OpenAPI 中会同时出现两组 path。

**作用域判定规则（v1 建议）**：
- 节点属于 world：`nodes.attributes.world_id == {world_id}`（与 graph seed 现有字段约定一致）。
- 关系属于 world：`source_node.world_id == {world_id}` 且 `target_node.world_id == {world_id}`。
- 当路径 `world_id` 与请求体中 `attributes.world_id` 冲突时，返回 **409**（或 400，二选一并在 OpenAPI 固定）；推荐以路径为准并拒绝冲突写入。
- 关系 `name_eq/name_like` 语义：映射到关系类型展示名 `relationship_types.type_name`（通过 `type_code` join）进行过滤。
- `tags_any` 语义：统一按逗号分隔参数解析（示例：`tags_any=graph_seed,hicampus`）。

**参数边界与解析规则（v1 固化）**：
- `name_like`：空字符串或仅空白视为无效参数，返回 **400**（`application/problem+json`）。
- `tags_any`：按逗号拆分后执行 `trim`，移除空项并去重；若最终集合为空，返回 **400**。
- `offset`：`>= 0`；`limit`：`1..500`（默认 100）。
- `name_eq`：默认大小写敏感精确匹配；`name_like`：`ILIKE`（大小写不敏感）。
- `tags_any` URL 编码示例：`tags_any=graph_seed,%20hicampus` 解析为 `["graph_seed","hicampus"]`。

### 查询参数规范表（v1）

| 参数 | 类型 | 适用端点 | 默认值 | 非法值处理 | 说明 |
|------|------|----------|--------|------------|------|
| `offset` | integer | 所有列表 | `0` | `<0` 返回 400 | 分页偏移量 |
| `limit` | integer | 所有列表 | `100` | `<=0` 或 `>500` 返回 400 | 分页大小 |
| `name_eq` | string | `node-types` / `relationship-types` / `relationships` | 无 | 空串返回 400 | 精确匹配；type 表作用于 `type_name` |
| `name_like` | string | `nodes` / `node-types` / `relationship-types` / `relationships` | 无 | 空白返回 400 | `ILIKE` 模糊匹配 |
| `tags_any` | string | 支持 tags 的列表端点 | 无 | 解析后空集返回 400 | 逗号分隔，任一命中 |
| `is_public` | boolean | `nodes` / `worlds/{world_id}/nodes` | 不过滤 | 非法布尔（见下「422」说明） | 可见性过滤 |
| `parent_type_code` | string | `node-types` | 不过滤 | - | 父类型过滤 |
| `is_active` | boolean |  ontology / graph 各列表 | 不过滤 | 非法布尔（见下「422」说明） | 是否启用过滤 |

**实现注记（ontology 列表）**：OpenAPI 中另登记 **`type_name_eq`**，与 **`name_eq`** 同义（均作用于 `type_name`）；文档与集成测试以 **`name_eq`** 为准，新客户端优先只用 `name_eq`。

### 列表接口无参与 GUI 客户端（RapidAPI / Postman）

- **可以不传任何 query**：例如 `GET /api/v1/ontology/node-types` 在携带有效 **`Authorization: Bearer`** 或 **`X-API-Key`** 时即可；服务端使用 **`offset=0`、`limit=100`**（与上表一致）。**不要求**客户端填写全部过滤字段。
- **`is_active` / `is_public`（boolean）**：须为 **`true` / `false`**（大小写不敏感，具体以 OpenAPI 为准）。若工具把未使用的参数绑成 **JavaScript 对象**，可能被序列化为字面量 **`[object Object]`**，Pydantic 无法解析为布尔，报错 **`Input should be a valid boolean, unable to interpret input`**。
- **`limit`**：须满足 **`1 <= limit <= 500`**。传 **`limit=0`** 或超出上限会报错 **`greater than or equal to 1`** / 类似校验信息。需要默认分页大小时，**直接省略 `limit` 参数**即可。
- **排查建议**：在 GUI 中 **清空或删除** 未使用的 Query 行，避免占位对象；最小化复现为「仅 Method + URL + 鉴权头、无 Query」。

### 422 与 `application/problem+json`（实现差异）

- 路由**业务规则**（如空白 `name_like`、空集 `tags_any`）由应用返回 **`400`** + **`application/problem+json`**（RFC 9457 形态）。
- **FastAPI / Pydantic** 对 Query 的**类型、范围**（如 `limit` 下界、`bool` 解析）校验失败时，默认返回 **`422 Unprocessable Entity`** + **`application/json`**，`detail` 为验证错误列表；**与**上表「非法值返回 400」在**形态上不完全一致**（框架层先于路由执行）。若产品要求全域统一 Problem Details，需在 HTTP 层增加 **`RequestValidationError` → problem+json** 的映射（可选后续工作）。

## 响应体形状（草案）

- **列表**：`{ "items": [...], "total": number, "offset": number, "limit": number }`（字段名实现可与现有 `accounts` 对齐为 `skip`，但 **全 API 新资源建议统一 `offset`**）。
- **节点项（摘要）**：至少 `id`、`uuid`、`type_code`、`name`、`is_active`、`trait_class`、`trait_mask`、`updated_at`。
- **节点项（详情）**：叠加 `description`、`attributes`、`location_id`、`home_id`、`tags`、`created_at` 等（与 ORM 对齐，**不** 默认返回大字段如 embedding，除非 `?expand=` 显式要求）。

## 错误码-场景矩阵（v1）

| HTTP 状态码 | 典型场景 | 端点示例 |
|------------|----------|----------|
| `400` | 参数格式/边界非法（空白 `name_like`、空集 `tags_any`、越界分页） | `GET /graph/nodes`、`GET /ontology/node-types` |
| `401` | 缺失或无效凭据（JWT/API Key） | 任意受保护端点 |
| `403` | 凭据有效但权限不足 | `PATCH /ontology/node-types/{type_code}` |
| `404` | 资源不存在，或 world scope 下对象不属于该 world | `GET /graph/nodes/{id}`、`GET /worlds/{world_id}/nodes/{id}` |
| `409` | 业务冲突（graph_seed 锁定类型、`world_id` 路径与 body 冲突） | `PATCH /ontology/node-types/room`、`POST /worlds/{world_id}/nodes` |

## 参考样例

下列样例基址为 **`https://api.example.com/api/v1`**；`Authorization` 可替换为 **`X-Api-Key: cw_live_xxx`**（若实现采用 API Key 头）。JSON 为说明性草稿，字段以 OpenAPI schema 为准。

### Ontology：`node-types`

**列出（分页 + 过滤）**

```http
GET /ontology/node-types?offset=0&limit=20&is_active=true&parent_type_code=default_object&name_like=房间&tags_any=graph_seed,hicampus HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
```

```json
{
  "items": [
    {
      "type_code": "room",
      "type_name": "房间",
      "parent_type_code": "default_object",
      "trait_class": "SPACE",
      "trait_mask": 516,
      "is_active": true,
      "updated_at": "2026-04-09T12:00:00Z"
    }
  ],
  "total": 42,
  "offset": 0,
  "limit": 20
}
```

**详情**

```http
GET /ontology/node-types/room HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
```

```json
{
  "type_code": "room",
  "type_name": "房间",
  "trait_class": "SPACE",
  "trait_mask": 516,
  "schema_definition": { "type": "object", "properties": {} },
  "tags": ["graph_seed", "hicampus"],
  "is_active": true
}
```

**创建**

```http
POST /ontology/node-types HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
Content-Type: application/json

{
  "type_code": "custom_sensor",
  "parent_type_code": "world_thing",
  "type_name": "自定义传感器",
  "typeclass": "app.models.things.devices.Sensor",
  "classname": "Sensor",
  "module_path": "app.models.things.devices",
  "trait_class": "DEVICE",
  "trait_mask": 58,
  "schema_definition": { "type": "object", "properties": {} }
}
```

**响应** `201 Created`，`Location: /api/v1/ontology/node-types/custom_sensor`，正文为创建后的资源对象。

**部分更新**

```http
PATCH /ontology/node-types/custom_sensor HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
Content-Type: application/json

{
  "description": "园区实验传感器类型",
  "schema_definition": { "type": "object", "properties": { "vendor": { "type": "string" } } }
}
```

**图种子类型禁止改 trait（冲突）**

```http
PATCH /ontology/node-types/room HTTP/1.1
Host: api.example.com
Content-Type: application/json

{ "trait_mask": 0 }
```

```http
HTTP/1.1 409 Conflict
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/ontology-seed-locked",
  "title": "Conflict",
  "status": 409,
  "detail": "graph_seed node type cannot change trait_mask"
}
```

### Ontology：`relationship-types`

**列表**

```http
GET /ontology/relationship-types?offset=0&limit=50&name_like=连接&tags_any=graph_seed HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
```

**创建边类型（示例）**

```http
POST /ontology/relationship-types HTTP/1.1
Host: api.example.com
Content-Type: application/json

{
  "type_code": "powers",
  "type_name": "供电",
  "typeclass": "app.models.relationships.LocationRelationship",
  "trait_class": "RULE",
  "trait_mask": 0
}
```

### Graph：`nodes`

**按类型与 trait 过滤列表**

```http
GET /graph/nodes?type_code=lighting_fixture&trait_class=DEVICE&is_public=true&name_like=light&tags_any=graph_seed,hicampus&required_any_mask=32&offset=0&limit=10 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
```

说明：`required_any_mask=32` 表示「任一带 `Controllable` 位」；`required_any_mask=0` 表示不按位过滤（F01）。`tags_any=graph_seed,hicampus` 表示命中任一标签。

**详情（整数 id）**

```http
GET /graph/nodes/1001 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
```

**创建节点**

```http
POST /graph/nodes HTTP/1.1
Host: api.example.com
Content-Type: application/json

{
  "type_code": "room",
  "name": "会议室 A",
  "attributes": { "room_code": "R-A-01" }
}
```

响应示例（注意：`trait_class` / `trait_mask` 与类型表一致，即使请求未传或传错也会被触发器覆盖）：

```json
{
  "id": 1002,
  "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "type_code": "room",
  "name": "会议室 A",
  "trait_class": "SPACE",
  "trait_mask": 516,
  "is_active": true,
  "attributes": { "room_code": "R-A-01", "world_id": "hicampus" }
}
```

**部分更新**

```http
PATCH /graph/nodes/1002 HTTP/1.1
Host: api.example.com
Content-Type: application/json

{ "description": "可预约", "attributes": { "room_code": "R-A-01", "capacity": 12 } }
```

**软删除**

```http
DELETE /graph/nodes/1002 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
```

响应可为 **200** + 更新后资源，或 **204** No Content（实现二选一并写入 OpenAPI）。

### Graph：`relationships`

**列表（按端点过滤）**

```http
GET /graph/relationships?source_id=100&target_id=200&type_code=located_in&name_like=位于&tags_any=graph_seed HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
```

**创建边**

```http
POST /graph/relationships HTTP/1.1
Host: api.example.com
Content-Type: application/json

{
  "source_id": 100,
  "target_id": 200,
  "type_code": "located_in",
  "attributes": {}
}
```

```http
HTTP/1.1 201 Created
Location: /api/v1/graph/relationships/5001
Content-Type: application/json

{
  "id": 5001,
  "uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "type_code": "located_in",
  "source_id": 100,
  "target_id": 200,
  "trait_class": "SPACE",
  "trait_mask": 5,
  "is_active": true
}
```

### World 范围：`nodes` / `relationships`

**列出某 world 下节点**

```http
GET /worlds/hicampus/nodes?type_code=room&offset=0&limit=20 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
```

```json
{
  "items": [
    {
      "id": 1002,
      "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "type_code": "room",
      "name": "会议室 A",
      "attributes": { "world_id": "hicampus", "room_code": "R-A-01" },
      "trait_class": "SPACE",
      "trait_mask": 516
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 20
}
```

**按 world + 可见性/名称/标签过滤**

```http
GET /worlds/hicampus/nodes?is_public=true&name_like=会议&tags_any=hicampus,room&offset=0&limit=20 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbG...
```

**在某 world 下创建节点**

```http
POST /worlds/hicampus/nodes HTTP/1.1
Host: api.example.com
Content-Type: application/json

{
  "type_code": "room",
  "name": "实验舱 B",
  "attributes": { "room_code": "LAB-B-01" }
}
```

说明：服务端应补齐 `attributes.world_id = "hicampus"`（或校验已传值一致）。

**在某 world 下创建关系**

```http
POST /worlds/hicampus/relationships HTTP/1.1
Host: api.example.com
Content-Type: application/json

{
  "source_id": 1002,
  "target_id": 1010,
  "type_code": "connects_to",
  "attributes": {}
}
```

若 `source_id` 或 `target_id` 不在 `hicampus`，返回：

```http
HTTP/1.1 404 Not Found
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/world-scope-not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "node is not in world scope: hicampus"
}
```

### 鉴权失败（通用）

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/problem+json

{
  "type": "about:blank",
  "title": "Unauthorized",
  "status": 401,
  "detail": "invalid credentials"
}
```

## 安全

- **禁止** 通过 query 传递任意 SQL 或原始图遍历表达式。
- **`attributes` JSONB**：可能含 PII；列表接口默认 **截断或省略** 深层键的策略由实现定义；详情接口受权限约束。
- **速率限制**：由网关/中间件处理（本 SPEC 仅要求 **429** 时返回 Problem Details）。

## 架构关系（示意）

```mermaid
flowchart LR
  Client[AdminOrAgent]
  API[REST_v1]
  Ontology[node_types_relationship_types]
  Graph[nodes_relationships]
  Triggers[DB_triggers_trait_sync]
  Client --> API
  API --> Ontology
  API --> Graph
  Ontology --> Triggers
  Triggers --> Graph
```

## Phase 2（开放问题）

- [ ] `GET /graph/nodes/by-uuid/{uuid}`：按 UUID 查详情（若产品需要与外部系统对齐）；v1 以整数 `id` 为唯一路径主键。
- [ ] `GET /graph/nodes/{id}/neighbors`：有界深度、`type_code` 过滤、方向（出/入/双向）。
- [ ] 批量创建/边：`POST /graph/batch` 或 JSON Patch 子集。
- [ ] **`Idempotency-Key`** 于 `POST` 创建。
- [ ] **ETag** + `If-Match` 乐观锁。
- [ ] Cursor 分页 + `Link` 头。
- [ ] 与 **Neo4j/其他图引擎** 的只读联邦查询（若产品需要）。

## SPEC 内验收检查清单（初稿）

- [ ] OpenAPI 文档含全部 v1 路径与 `application/problem+json` 响应 schema。
- [ ] **`bearerAuth` + `apiKeyAuth`**（或文档约定的单一 API Key 传递方式）与 **互斥规则** 已登记。
- [ ] 实例创建/更新文档标明 `trait_*` 由类型表强制，与 F01 一致。
- [ ] 列表 `limit` 上限与 `trait_mask=0` 语义在描述中显式写出。
- [ ] 图种子类型锁定策略有明确 HTTP 状态码与 `type` URI。
- [ ] **参考样例** 与最终实现的路径、字段名一致（或从 OpenAPI 示例自动生成）。
- [ ] 与 [`docs/api/SPEC/ACCEPTANCE.md`](../ACCEPTANCE.md) F10 节交叉通过。

## References

- [`F01_TRAIT_CLASS_MASK_FOR_AGENT.md`](../../../database/SPEC/features/F01_TRAIT_CLASS_MASK_FOR_AGENT.md)
- [`RFC 9457` Problem Details](https://datatracker.ietf.org/doc/html/rfc9457)
- [`OpenAPI Specification`](https://spec.openapis.org/oas/latest.html)
- [`backend/app/models/graph.py`](../../../../backend/app/models/graph.py)
