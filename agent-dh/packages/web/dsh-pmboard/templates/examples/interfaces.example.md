---
requirement_refs: [FR-2, FR-3, FR-5]
---

# 接口设计（REQ-example）

## 接口清单 <!-- serves: FR-2 -->

| 编号 | 路径 | 方法 | 用途（谁调用+做什么） | 请求（参数完整清单） | 响应（字段完整清单） | serves |
|---|---|---|---|---|---|---|
| I-1 | /api/templates/:key | GET | 浏览器端调用，获取指定模板的完整 markdown 内容用于预览 | key(string, 路径参数): 模板 key 如 "requirement.feature" | 见下方详细 schema | FR-2 |
| I-2 | /api/requirements/:id/submit | POST | 窗口调用，提交产物并触发校验（缺必填节时拒绝） | 见下方详细 schema | 见下方详细 schema | FR-5 |
| I-3 | /api/requirements/:id/artifacts | POST | 内部调用，登记产物到 artifacts 表（供模板落盘服务使用） | 见下方详细 schema | 见下方详细 schema | FR-3 |

## 接口详细定义 <!-- serves: FR-2 -->

### I-1 获取模板内容

**请求**

- **路径参数**
  - `key` (string, 必填): 模板 key，格式为 `<filename>`，如 `requirement.feature`
    - 取值范围：`[a-z0-9.-]`，不含路径分隔符
    - 长度限制：1-100 字符
    - 错误示例：`../../../etc/passwd`（会被拒绝 400）

- **Query 参数**：无

- **Header**
  - `Authorization` (string, 可选): Bearer token
    - 未登录时部分模板不可见（如敏感配置模板）
    - 格式：`Bearer <jwt_token>`

- **Body**：无（GET 请求）

**响应**

- **成功 200**
  ```json
  {
    "success": true,
    "data": {
      "content": "---\nrequirement_refs: [FR-1]\n---\n\n# 需求说明（{{REQ_ID}}）\n\n## 目标用户与使用场景...",
      "template_key": "requirement.feature",
      "char_count": 1234,
      "sections": ["目标用户与使用场景", "功能点", "边界（不做什么）"],
      "category": "brainstorming",
      "last_updated": "2026-01-15T10:00:00Z"
    }
  }
  ```
  
  **字段说明**：
  - `content` (string, 必填): 模板完整内容，包含 front-matter
  - `template_key` (string, 必填): 回显请求的 key
  - `char_count` (number, 必填): 字符数（不含空格）
  - `sections` (string[], 可选): 章节清单（二级标题），用于前端生成目录
  - `category` (string, 可选): 模板分类（brainstorming/design/...）
  - `last_updated` (string ISO8601, 必填): 模板最后更新时间（构建时间）

- **客户端错误 400**（参数非法）
  ```json
  {
    "success": false,
    "error": {
      "code": "INVALID_KEY",
      "message": "模板 key 格式非法，不允许路径遍历字符",
      "details": {
        "key": "../../../etc/passwd",
        "reason": "contains path traversal",
        "allowed_pattern": "[a-z0-9.-]"
      }
    }
  }
  ```

- **未找到 404**（模板不存在）
  ```json
  {
    "success": false,
    "error": {
      "code": "TEMPLATE_NOT_FOUND",
      "message": "模板不存在",
      "details": {
        "key": "nonexistent.md",
        "available_keys": [
          "requirement.feature",
          "requirement.bug",
          "requirement.refactor",
          "frontend",
          "backend",
          "interfaces"
        ]
      }
    }
  }
  ```

- **服务器错误 500**（读取失败）
  ```json
  {
    "success": false,
    "error": {
      "code": "TEMPLATE_READ_ERROR",
      "message": "模板读取失败，请稍后重试",
      "details": {
        "key": "requirement.feature",
        "error_type": "INTERNAL_ERROR"
      }
    }
  }
  ```

**幂等性**：是（GET 请求，多次调用结果一致）

**缓存策略**：
- 模板内容不变（构建期生成），可缓存 1 小时
- 响应头：`Cache-Control: public, max-age=3600`
- ETag：基于 template_key + build_time 生成

**限流**：100 次/分钟/IP（nginx rate limit）

**性能指标**：P95 响应时间 < 50ms（内存读取，零磁盘 I/O）

---

### I-2 提交产物并校验

**请求**

- **路径参数**
  - `id` (string, 必填): 需求 ID，格式 `REQ-xxxxxx`
    - 正则：`/^REQ-[0-9a-f]{6}$/`

- **Query 参数**：无

- **Header**
  - `Authorization` (string, 必填): Bearer token
  - `Content-Type` (string, 必填): `application/json`

- **Body**
  ```json
  {
    "kind": "requirement",
    "path": "docs/requirements/REQ-xxx/requirement.md",
    "summary": "需求说明已完成，包含目标用户、功能点、边界三个章节",
    "change_note": "新增边界章节，补充不做什么的说明"
  }
  ```
  
  **字段说明**：
  - `kind` (string, 必填): 产物类型，枚举值 `requirement | plan | design | verification | archive`
  - `path` (string, 必填): 文件路径（工作区相对路径），必须以 `docs/requirements/<REQ_ID>/` 开头
  - `summary` (string, 必填): 一句话摘要，长度 10-2000 字符
  - `change_note` (string, 可选): 变更原因（重交时必填），长度 10-1000 字符

**响应**

- **成功 200**
  ```json
  {
    "success": true,
    "data": {
      "artifact": {
        "id": 123,
        "kind": "requirement",
        "path": "docs/requirements/REQ-xxx/requirement.md",
        "stage": "brainstorming",
        "registered_at": "2026-01-15T10:30:00Z",
        "revision": 1
      },
      "validation": {
        "passed": true,
        "checked_sections": [
          "目标用户与使用场景",
          "功能点",
          "边界（不做什么）"
        ],
        "missing_sections": []
      },
      "next_action": {
        "type": "node_transition",
        "to_stage": "design",
        "message": "需求分析完成，已自动进入设计阶段"
      }
    }
  }
  ```
  
  **字段说明**：
  - `artifact.id` (number): 产物 ID（artifacts 表主键）
  - `artifact.revision` (number): 版本号（同一 path 每次重交 +1）
  - `validation.passed` (boolean): 校验是否通过
  - `validation.checked_sections` (string[]): 实际找到的章节列表
  - `next_action` (object, 可选): 提交后的自动动作（如节点转移）

- **校验失败 422**（缺必填节）
  ```json
  {
    "success": false,
    "error": {
      "code": "VALIDATION_FAILED",
      "message": "文档缺少必填章节",
      "details": {
        "missing_sections": [
          "边界（不做什么）",
          "验收标准（整体）"
        ],
        "file_path": "docs/requirements/REQ-xxx/requirement.md",
        "found_sections": [
          "目标用户与使用场景",
          "功能点"
        ],
        "help_url": "https://docs.example.com/requirement-template"
      }
    }
  }
  ```

- **权限错误 403**（无编辑权限）
  ```json
  {
    "success": false,
    "error": {
      "code": "PERMISSION_DENIED",
      "message": "您无权操作该需求",
      "details": {
        "req_id": "REQ-xxx",
        "user_id": "user-123",
        "owner_id": "user-456",
        "required_permission": "edit"
      }
    }
  }
  ```

- **文件不存在 404**
  ```json
  {
    "success": false,
    "error": {
      "code": "FILE_NOT_FOUND",
      "message": "文档文件不存在，请检查路径",
      "details": {
        "path": "docs/requirements/REQ-xxx/requirement.md",
        "expected_location": "工作区根目录下的相对路径"
      }
    }
  }
  ```

**幂等性**：是（重复提交返回已存在的 artifact_id，revision 不变）

**副作用**：
- 登记到 artifacts 表（kind / path / summary）
- 触发节点转移钩子（如果所有产物齐全）
- 发送 WebSocket 通知给需求负责人
- 记录审计日志（用户 ID + 操作时间 + 文件路径）

**限流**：10 次/分钟/用户

**性能指标**：P95 响应时间 < 200ms（含文件读取 + 正则匹配 + DB 写入）

---

### I-3 登记产物（内部接口）

**请求**

- **路径参数**
  - `id` (string, 必填): 需求 ID

- **Header**
  - `X-Internal-Token` (string, 必填): 内部服务认证 token（不对外暴露）

- **Body**
  ```json
  {
    "kind": "template_skeleton",
    "path": "docs/requirements/REQ-xxx/requirement.md",
    "template_key": "requirement.feature",
    "metadata": {
      "char_count": 1234,
      "sections": ["目标用户", "功能点"]
    }
  }
  ```

**响应**

- **成功 200**
  ```json
  {
    "success": true,
    "data": {
      "artifact_id": 123,
      "req_id": "REQ-xxx",
      "registered_at": "2026-01-15T10:30:00Z"
    }
  }
  ```

- **冲突 409**（重复登记）
  ```json
  {
    "success": false,
    "error": {
      "code": "ARTIFACT_ALREADY_EXISTS",
      "message": "该产物已登记",
      "details": {
        "existing_artifact_id": 120,
        "req_id": "REQ-xxx",
        "path": "docs/requirements/REQ-xxx/requirement.md"
      }
    }
  }
  ```

**幂等性**：是（重复登记返回 409，不创建重复记录）

**限流**：100 次/分钟（内部接口，高频调用）

## 鉴权策略 <!-- serves: FR-2 -->

| 接口 | 鉴权要求 | 权限校验规则 | Token 格式 |
|---|---|---|---|
| I-1 GET /api/templates/:key | 需登录（部分模板公开） | 所有已登录用户可访问 | JWT Bearer |
| I-2 POST /api/requirements/:id/submit | 需登录 + 该需求的编辑权限 | `user.id == requirement.owner_id OR user.role == 'admin'` | JWT Bearer |
| I-3 POST /api/requirements/:id/artifacts | 内部服务认证 | 验证 X-Internal-Token（HMAC-SHA256 签名） | Internal Token |

**Token 格式**：
- JWT：`Authorization: Bearer <token>`
- 过期时间：7 天
- 刷新机制：滑动窗口（最后活跃时间 + 7 天）
- Payload：`{user_id, role, iat, exp}`

**权限层级**：
- `admin`：全部需求可编辑
- `owner`：自己创建的需求可编辑
- `viewer`：只读（查看需求和模板）

## 错误码规范 <!-- serves: FR-2 -->

| 错误码 | HTTP 状态码 | 含义 | 用户提示 | 前端处理建议 |
|---|---|---|---|---|
| INVALID_KEY | 400 | 模板 key 格式非法 | "模板标识不合法，请检查输入" | 提示用户重新选择，展示可用模板列表 |
| TEMPLATE_NOT_FOUND | 404 | 模板不存在 | "模板不存在，请选择其他模板" | 展示 available_keys 列表供用户选择 |
| VALIDATION_FAILED | 422 | 文档校验失败（缺必填节） | "文档缺少必填章节：xxx" | 高亮缺失章节，显示帮助链接，引导补充 |
| PERMISSION_DENIED | 403 | 无权限操作该需求 | "您无权操作该需求，请联系需求负责人" | 跳转到无权限提示页，显示 owner 信息 |
| TEMPLATE_READ_ERROR | 500 | 服务器内部错误（模板读取失败） | "系统繁忙，请稍后重试" | 显示重试按钮，3 次失败后引导联系技术支持 |
| FILE_NOT_FOUND | 404 | 文档文件不存在 | "文档文件不存在，请检查路径" | 提示用户先保存文件再提交 |
| ARTIFACT_ALREADY_EXISTS | 409 | 产物重复登记 | "该文档已提交，无需重复操作" | 显示已登记的产物信息（时间/版本） |

**错误响应统一格式**：
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "用户可读的错误信息",
    "details": {
      // 错误详情（可选，用于调试）
    }
  }
}
```

## 接口版本管理 <!-- serves: FR-2 -->

**版本策略**：URL 路径版本化

- 当前版本：`/api/v1/templates/:key`
- 未来版本：`/api/v2/templates/:key`（保留 v1，双版本并存）

**向后兼容原则**：
- **新增字段**：标记 optional，旧客户端忽略
- **废弃字段**：保留 6 个月，响应中仍返回但标记 deprecated
  - 响应 Header：`X-Deprecated-Fields: field1,field2`
- **Breaking Change**：发布 v2，v1 保留 12 个月后下线

**废弃通知**：
- 响应 Header：
  - `Deprecation: true`
  - `Sunset: 2026-07-01`（v1 下线日期）
  - `Link: </docs/migration-guide>; rel="deprecation"`
- 官网公告（提前 3 个月）
- 邮件通知接入方（提前 1 个月）

**当前版本**：v1（2026-01-15 发布）
