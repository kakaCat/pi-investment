# 接口设计（{{REQ_ID}}）

> 每个接口/工具/API 必须标注 `serves: FR-x`（缺标注 = 孤儿接口被门禁拦）。
> **什么时候不交本份**：没有新增/修改对外接口（纯内部重构）——删本文档。

## 新增/修改的工具接口 `serves: FR-1`

### {{TOOL_NAME}} `serves: FR-1, FR-2`

**用途**：（一句话：这个工具/API 是干什么的）

**调用方**：（谁会用——Agent / 页面 / 其他工具）

**接口定义**：
```typescript
interface ToolInput {
  // 参数定义
}

interface ToolOutput {
  // 返回值定义
}
```

**参数说明**：

| 参数 | 类型 | 必填 | 说明 | 默认值 |
|---|---|---|---|---|
|  |  |  |  |  |

**返回值说明**：

| 字段 | 类型 | 说明 |
|---|---|---|
|  |  |  |

**异常情况**：

| 错误码 | 触发条件 | 返回内容 |
|---|---|---|
|  |  |  |

**使用示例**：
```typescript
const result = await tools.tool_name({
  param: 'value'
})
```

## 删除的接口 `serves: FR-1` (When Needed)

| 接口名 | 原用途 | 删除原因 | 替代方案 |
|---|---|---|---|
|  |  |  |  |

## HTTP API 变更 `serves: FR-1` (When Needed)

### POST /api/endpoint `serves: FR-1`

**请求**：
```json
{
  "field": "value"
}
```

**响应**：
```json
{
  "result": "data"
}
```

**状态码**：

| 状态码 | 含义 |
|---|---|
| 200 | 成功 |
| 400 | 参数错误 |
