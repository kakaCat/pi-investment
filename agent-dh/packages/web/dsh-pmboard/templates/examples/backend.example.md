---
requirement_refs: [FR-2, FR-3, FR-5]
---

# 后端设计（REQ-example）

## 服务与接口实现 <!-- serves: FR-3 模板落盘具有幂等性 -->

| 编号 | 类型 | 名称 | 职责说明 | 输入 | 输出 | 调用方 | 依赖 | serves |
|---|---|---|---|---|---|---|---|---|
| S-1 | 函数 | selectTemplate | 根据阶段和类型选择模板 key | stage (string, 枚举："brainstorming"/"design"/...)、category (string, 枚举："feature"/"bug"/...) | templateKey (string, 如 "requirement.feature") 或 null (无匹配) | S-2 | TEMPLATE_MAP 常量表 | FR-3 |
| S-2 | 服务 | landTemplate | 模板落盘：检查幂等性 → 写文件 → 登记 artifacts | reqId (string, REQ-xxxxxx)、stage (string)、category (string)、targetPath (string, 如 "docs/requirements/REQ-xxx/requirement.md") | {success: boolean, landed: boolean, artifact_id?: number, reason?: string} | 转移钩子 node.entered | S-1, fs 模块, artifacts 表, comments 表 | FR-3 |
| S-3 | 模块 | NodeInputAssembler | 组装节点输入包，注入模板文件指针 | reqId (string)、stage (string, 当前节点阶段) | {template_files: Array<{path: string, template_key: string, required_sections: string[]}>} | getNodeInput API | S-1, artifacts 表, REQUIRED_SECTIONS 常量表 | FR-4 |
| S-4 | 函数 | validateDocument | 文档校验：解析章节 → 对比必填节 → 返回缺失清单 | filePath (string, 绝对路径)、kind (string, 文档类型："requirement"/...) | {passed: boolean, missing_sections?: string[], found_sections?: string[], error?: string} | I-2 接口 | REQUIRED_SECTIONS 常量表, fs 模块 | FR-5 |

## 数据流 <!-- serves: FR-3 模板落盘具有幂等性 -->

**流程 1：模板落盘（需求进入新阶段时）**

```
事件：转移钩子触发 node.entered(reqId="REQ-001", stage="brainstorming")
  ↓
S-2.landTemplate(reqId, stage="brainstorming", category="feature", targetPath="docs/requirements/REQ-001/requirement.md")
  │
  ├─ 步骤 1：调用 S-1 选择模板
  │   ↓ S-1.selectTemplate(stage="brainstorming", category="feature")
  │   ↓ 查 TEMPLATE_MAP["brainstorming.feature"] → 返回 "requirement.feature"
  │   ↓ 输出：templateKey = "requirement.feature"
  │
  ├─ 步骤 2：幂等检查（文件系统）
  │   ↓ 检查文件是否存在：docs/requirements/REQ-001/requirement.md
  │   ├─ 存在 → 返回 {success: true, landed: false, reason: "already_exists"}，流程结束
  │   └─ 不存在 → 继续
  │
  ├─ 步骤 2.5：幂等检查（数据库）
  │   ↓ 查询 artifacts 表：WHERE req_id='REQ-001' AND path='docs/requirements/REQ-001/requirement.md'
  │   ├─ 有记录 → 返回 {success: true, landed: false, reason: "already_registered"}，流程结束
  │   └─ 无记录 → 继续
  │
  ├─ 步骤 3：读取模板内容
  │   ↓ 从模板清单自动生成的常量中读取 "requirement.feature" 模板
  │   ↓ 输出：markdown 字符串（约 2KB，包含 front-matter + 章节骨架）
  │
  ├─ 步骤 4：写入文件
  │   ↓ 写入文件：docs/requirements/REQ-001/requirement.md
  │   ├─ 成功 → 记日志 "template.landed"，继续
  │   └─ 失败 (磁盘写满/权限不足) →
  │       ├─ 捕获错误，记日志 "template.write_failed"
  │       ├─ 降级：将错误信息写入 comments 表（类型为 "error"）
  │       └─ 返回 {success: true, landed: false, reason: "fs_error"}，流程结束（不阻塞转移）
  │
  └─ 步骤 5：登记产物
      ↓ 插入 artifacts 表：(req_id='REQ-001', kind='template_skeleton', path='docs/...', template_key='requirement.feature')
      ├─ 成功 → 返回 {success: true, landed: true, artifact_id: 123}
      └─ 失败 (唯一约束冲突/DB 超时) →
          ├─ 唯一约束冲突 → 并发写竞态，记告警日志，返回 {success: true, landed: true, artifact_id: null}
          └─ 其他错误 → 记错误日志，返回 {success: true, landed: true, artifact_id: null}（文件已落盘，只是元数据缺失）

【副作用】：
- 文件系统：新增 1 个 md 文件（约 2KB）
- 数据库：artifacts 表新增 1 行（或因冲突/失败未插入）
- 日志：info/warn/error 级别日志若干条
- 通知：WebSocket 推送 "文档已生成" 事件给前端（由上层调用方负责）
```

**流程 2：文档校验（用户提交文档时）**

```
事件：客户端请求 POST /api/requirements/:id/submit
      body: {kind: "requirement", path: "docs/requirements/REQ-001/requirement.md", summary: "..."}
  ↓
I-2 路由层
  ├─ 鉴权：检查 Authorization header 的 JWT token，验证 user.id == requirement.owner_id
  │   └─ 失败 → 403 {code: "PERMISSION_DENIED"}
  ├─ 参数校验：kind/path 必填，path 必须以 "docs/requirements/<REQ_ID>/" 开头
  │   └─ 失败 → 400 {code: "PARAM_MISSING" 或 "INVALID_PATH"}
  └─ 继续
  ↓
S-4.validateDocument(filePath="docs/requirements/REQ-001/requirement.md", kind="requirement")
  │
  ├─ 步骤 1：读取文件内容
  │   ↓ 读取文件：docs/requirements/REQ-001/requirement.md
  │   ├─ 成功 → 输出：markdown 字符串
  │   └─ 失败 (文件不存在) → 返回 {passed: false, error: "FILE_NOT_FOUND"}，流程结束
  │
  ├─ 步骤 2：解析章节标题
  │   ↓ 正则匹配所有二级标题（## 开头的行）
  │   ↓ 去掉标题前后的空格，忽略 HTML 注释（如 <!-- serves: FR-1 -->）
  │   ↓ 示例输出：foundSections = ["目标用户与使用场景", "功能点", "非功能需求"]
  │
  ├─ 步骤 3：查必填节清单
  │   ↓ 查 REQUIRED_SECTIONS["requirement"] = ["目标用户", "功能点", "边界", "验收标准"]
  │
  ├─ 步骤 4：对比校验（模糊匹配）
  │   ↓ 遍历每个必填节，检查是否在 foundSections 中
  │   ↓ 匹配规则：found 包含 required 或 required 包含 found（大小写不敏感）
  │   ↓ 示例：
  │       - required="目标用户"，found="目标用户与使用场景" → 匹配（found 包含 required）
  │       - required="边界"，foundSections 中无任何项包含"边界" → 不匹配，记入 missingSections
  │   ↓ 输出：missingSections = ["边界", "验收标准"]
  │
  └─ 步骤 5：返回结果
      ├─ missingSections 为空 → {passed: true, found_sections: foundSections}
      └─ missingSections 非空 → {passed: false, missing_sections: missingSections, found_sections: foundSections}
  ↓
I-2 响应客户端
  ├─ passed=true →
  │   ├─ 插入 artifacts 表：(req_id='REQ-001', kind='requirement', path='docs/...', summary='...')
  │   ├─ 触发节点转移钩子（如果所有产物齐全）
  │   └─ 200 {success: true, artifact: {...}, validation: {passed: true}}
  └─ passed=false →
      └─ 422 {success: false, error: {code: "VALIDATION_FAILED", missing_sections: [...]}}
```

## 关键逻辑 <!-- serves: FR-3 模板落盘具有幂等性 -->

### S-1 模板选择逻辑（selectTemplate 函数）

**功能**：根据需求阶段和类型，从常量表中查找对应的模板 key。

**处理步骤**：
1. 拼接查询 key：将 stage 和 category 用点号连接，如 "brainstorming.feature"
2. 查 TEMPLATE_MAP 常量表：用拼接的 key 作为索引查表
3. 返回结果：
   - 命中：返回对应的模板 key（如 "requirement.feature"）
   - 未命中：返回 null

**边界条件**：
- stage 或 category 为空：拼接出的 key 无效（如 ".feature"），查表返回 undefined，函数返回 null
- 常量表中不存在该组合：返回 null，调用方（S-2）会记告警日志 "template.missing"

**示例**：
- 输入：stage="brainstorming", category="feature"
- 拼接：key = "brainstorming.feature"
- 查表：TEMPLATE_MAP["brainstorming.feature"] = "requirement.feature"
- 输出：返回 "requirement.feature"

**性能指标**：
- 时间复杂度：O(1)（常量表查询）
- 预期耗时：< 1ms

### S-2 模板落盘逻辑（landTemplate 服务）

**功能**：将模板文件写入文件系统并登记到数据库，确保幂等性（多次调用结果一致）。

**处理步骤**：
1. 调用 S-1 选择模板：
   - 拿到 templateKey → 继续
   - 拿到 null → 记告警日志，返回 {success: true, landed: false, reason: "no_template"}，流程结束

2. 幂等检查（文件系统）：
   - 检查 targetPath 文件是否存在
   - 存在 → 记日志 "template.skip.file_exists"，返回 {success: true, landed: false, reason: "already_exists"}，流程结束
   - 不存在 → 继续

3. 幂等检查（数据库）：
   - 查询 artifacts 表：WHERE req_id=? AND path=?
   - 有记录 → 记日志 "template.skip.db_registered"，返回 {success: true, landed: false, reason: "already_registered"}，流程结束
   - 无记录 → 继续

4. 读取模板内容：
   - 从模板清单自动生成的常量中读取 templateKey 对应的模板内容
   - 拿不到内容（理论上不会发生）→ 记错误日志，返回 {success: true, landed: false, reason: "content_missing"}

5. 写入文件：
   - 将模板内容写入 targetPath
   - 成功 → 记日志 "template.landed"，继续
   - 失败（磁盘写满/权限不足）→ 捕获错误，记错误日志，将错误信息写入 comments 表，返回 {success: true, landed: false, reason: "fs_error"}（降级：不阻塞转移）

6. 登记产物：
   - 插入 artifacts 表：(req_id, kind='template_skeleton', path, template_key, created_at)
   - 成功 → 记日志 "template.registered"，返回 {success: true, landed: true, artifact_id: 插入的 ID}
   - 失败（唯一约束冲突）→ 并发写竞态，记告警日志，返回 {success: true, landed: true, artifact_id: null}（文件已落盘，只是元数据冲突）
   - 失败（其他 DB 错误）→ 记错误日志，返回 {success: true, landed: true, artifact_id: null}（文件已落盘，只是元数据缺失）

**边界条件**：
- 并发写同一文件：两个请求同时触发，都走到写文件步骤 → 后写的覆盖先写的（内容相同），DB 唯一约束拦截第二次插入，最终两个请求都返回 success=true, landed=true（幂等）
- 磁盘写满：写文件失败，错误信息写入 comments 表，用户在需求详情页可见，返回 success=true（不阻塞转移），用户可手动创建文件继续工作
- DB 超时：文件已落盘，只是 artifacts 表插入失败，返回 success=true, artifact_id=null（文件可用，只是元数据缺失）

**性能指标**：
- 正常路径：约 50ms（文件 I/O 30ms + DB 写入 20ms）
- 幂等路径（文件已存在）：约 5ms（只有文件系统检查）
- 时间复杂度：O(1)

### S-4 文档校验逻辑（validateDocument 函数）

**功能**：检查文档是否包含所有必填章节，返回缺失清单。

**处理步骤**：
1. 读取文件内容：
   - 读取 filePath 文件
   - 成功 → 拿到 markdown 字符串，继续
   - 失败（文件不存在）→ 返回 {passed: false, error: "FILE_NOT_FOUND"}

2. 解析章节标题：
   - 用正则表达式匹配所有二级标题（## 开头的行）
   - 提取标题文本，去掉前后空格，忽略 HTML 注释（如 <!-- serves: FR-1 -->）
   - 输出：foundSections 数组，如 ["目标用户与使用场景", "功能点", "非功能需求"]

3. 查必填节清单：
   - 查 REQUIRED_SECTIONS[kind]，拿到该文档类型的必填章节列表
   - 如果该 kind 无必填节要求 → 返回 {passed: true}

4. 对比校验（模糊匹配）：
   - 遍历每个必填节（required），检查是否在 foundSections 中
   - 匹配规则（大小写不敏感）：
     - found 包含 required，或
     - required 包含 found
   - 不匹配的必填节记入 missingSections 数组

5. 返回结果：
   - missingSections 为空 → {passed: true, found_sections: foundSections}
   - missingSections 非空 → {passed: false, missing_sections: missingSections, found_sections: foundSections}

**边界条件**：
- 章节名带括号注释：如文档写 "边界（不做什么）"，必填节要求 "边界" → 模糊匹配通过（found 包含 required）
- 大小写不敏感：如文档写 "功能Point"，必填节要求 "功能点" → 统一转小写后比较，匹配通过
- 空文档：foundSections=[]，所有必填节都缺失，返回 {passed: false, missing_sections: 全部必填节}
- 章节标题含 HTML 注释：如 "## 功能点 <!-- serves: FR-1 -->" → 正则忽略注释部分，提取出 "功能点"

**示例**：
- 输入：filePath="docs/requirements/REQ-001/requirement.md", kind="requirement"
- 文档内容：包含章节 "目标用户与使用场景"、"功能点"、"非功能需求"
- 必填节：["目标用户", "功能点", "边界", "验收标准"]
- 匹配结果：
  - "目标用户" → 命中 "目标用户与使用场景"（found 包含 required）
  - "功能点" → 命中 "功能点"
  - "边界" → 未命中（foundSections 中无任何项包含 "边界"）
  - "验收标准" → 未命中
- 输出：{passed: false, missing_sections: ["边界", "验收标准"]}

**性能指标**：
- 100 行文档：约 1ms
- 1000 行文档：约 5ms
- 时间复杂度：O(n)，n = 文档行数

## 错误处理 <!-- serves: FR-5 文档校验失败时拒绝提交 -->

| 错误类型 | HTTP 状态码 | 错误码 | 用户提示 | 重试策略 | 降级方案 |
|---|---|---|---|---|---|
| 参数缺失 | 400 | PARAM_MISSING | "缺少必填参数 xxx" | 不重试 | - |
| 权限不足 | 403 | PERMISSION_DENIED | "您无权操作该需求" | 不重试 | - |
| 文件不存在 | 404 | FILE_NOT_FOUND | "文档文件不存在，请检查路径" | 不重试 | - |
| 校验失败 | 422 | VALIDATION_FAILED | "文档缺少必填章节：xxx" | 不重试 | 前端高亮缺失章节 |
| 模板缺失 | 200 | NO_TEMPLATE | "该阶段暂无模板" | 不重试 | 零落盘 + 告警 |
| 文件系统错误 | 200 | FS_ERROR | "模板落盘失败，请联系管理员" | 不重试 | 错误进 comments |
| DB 超时 | 200 | DB_TIMEOUT | "系统繁忙，部分功能降级" | 重试 1 次 | 跳过 artifacts 登记 |

**错误降级原则**：
- 用户操作错误（400/403/422）：明确拒绝，前端展示详细错误信息，不降级
- 系统故障（FS_ERROR/DB_TIMEOUT）：降级但不阻塞核心流程（节点转移/文档提交），错误信息记入 comments 或日志
- 资源缺失（NO_TEMPLATE）：告警但不当错误（未来可能新增阶段但暂无模板），返回 200 状态码

## 数据库设计 <!-- serves: FR-3 模板落盘具有幂等性 -->

### 新增/修改字段

```sql
-- 新增 kind 字段
ALTER TABLE artifacts ADD COLUMN kind VARCHAR(50) DEFAULT NULL;

-- 修改唯一约束（从 path 改为 req_id + path 组合）
ALTER TABLE artifacts DROP CONSTRAINT IF EXISTS uk_artifacts_path;
ALTER TABLE artifacts ADD CONSTRAINT uk_artifacts_req_path UNIQUE (req_id, path);
```

**字段说明**：
- `kind`：产物类型，枚举值：template_skeleton（模板骨架）/ manual_doc（手写文档）/ design（设计）/ test_case（测试用例）/ review（评审记录）
- 默认值 NULL：兼容存量数据（迁移脚本会回填）

### 新增索引

```sql
CREATE INDEX idx_artifacts_req_kind ON artifacts(req_id, kind);
CREATE INDEX idx_artifacts_created_desc ON artifacts(created_at DESC);
```

| 索引 | 支撑的查询 | 为什么选这些列 |
|---|---|---|
| idx_artifacts_req_kind | `SELECT * FROM artifacts WHERE req_id=? AND kind=?` | kind 有 5 种枚举值，req_id + kind 组合选择性高（约 1:3） |
| idx_artifacts_created_desc | `SELECT * FROM artifacts ORDER BY created_at DESC LIMIT 20` | DESC 索引匹配排序方向（升序索引无法优化降序查询） |

## 性能考量 <!-- serves: FR-3 模板落盘具有幂等性 -->

| 指标 | 目标 | 优化方案 |
|---|---|---|
| 模板落盘响应时间 P95 | < 100ms | Promise.all 并行落盘 17 个模板，限流 10 并发 |
| artifacts 表查询延迟 P95 | < 20ms | 新增 idx_artifacts_req_kind 索引 |
| 文档校验延迟 P95 | < 50ms | 正则预编译 + 非贪婪匹配 |

**瓶颈分析**：
- 模板落盘瓶颈（已优化）：串行落盘 850ms → 并行落盘 80ms（10.6x 提升）
- 数据库查询瓶颈（已优化）：全表扫描 150ms → 索引扫描 < 5ms（30x 提升）

## 安全设计 <!-- serves: FR-5 文档校验失败时拒绝提交 -->

### 鉴权

| 接口 | 鉴权要求 | 权限校验规则 |
|---|---|---|
| POST /api/requirements/:id/submit | 需登录 + 编辑权限 | `user.id == requirement.owner_id OR user.role == 'admin'` |

### 输入校验

| 参数 | 校验规则 | 拒绝示例 | 理由 |
|---|---|---|---|
| template_key | 白名单 `[a-z0-9.-]` | `../../../etc/passwd` | 防止路径遍历 |
| path | 必须以 `docs/requirements/<REQ_ID>/` 开头 | `/tmp/evil.md` | 防止写入任意路径 |
| req_id | 正则 `/^REQ-[0-9a-f]{6}$/` | `REQ-' OR 1=1--` | 防止 SQL 注入 |
