# reqboard_ask_confirm 用户反馈支持

## 问题
用户在 `reqboard_ask_confirm` 弹框中选择非肯定项（如"需要修改"）时：
- ✅ 系统不会落章、不会推进（行为正确）
- ❌ **但 Agent 不知道用户具体要改什么**
- ❌ 只能看到"用户选择了'需要修改'"，没有具体意见

## 解决方案

### 1. 用例层改进
**文件**: `packages/pages/dsh-pmboard/src/application/use-cases/AskConfirm.ts`

**改动**：
- 捕获用户的自定义输入（`answer?.custom`）作为修改意见
- 在台账评论中记录用户意见
- 在返回结果中包含 `user_choice` 和 `user_feedback` 字段

**代码示例**：
```typescript
// 非肯定项处理
if (!affirmative) {
  const userFeedback = answer?.custom?.trim() ?? ''
  const feedbackNote = userFeedback.length > 0 ? '。用户意见：' + userFeedback : ''
  
  // 记录到台账
  req.comments.push({
    id: deps.ids.comment(),
    body: '[确认弹框] 用户未确认（选择：' + picked + '）——节点未推进。问题：' + question + feedbackNote,
    createdAt: nowTs,
    createdBy: { kind: 'human', sessionId: windowKey },
  })
  
  // 返回用户选择和反馈
  return {
    success: true, 
    confirmed: false, 
    advanced: false,
    user_choice: picked || '（未选）',
    user_feedback: userFeedback.length > 0 ? userFeedback : undefined,
    note: '用户选择"' + picked + '"：未落章、未推进。' + 
          (userFeedback.length > 0 ? '用户反馈：' + userFeedback + '。' : '') +
          '按用户意见修改后可重新发起确认',
  }
}
```

### 2. 工具 Schema 更新
**文件**: `packages/pages/dsh-pmboard/src/tools/AskConfirmTool/AskConfirmTool.ts`

**改动**：
在 output schema 中添加两个新字段：

```typescript
properties: {
  // ... 其他字段 ...
  user_choice: { 
    type: 'string', 
    description: '弹框路径（非肯定项）：用户选择的选项文本' 
  },
  user_feedback: { 
    type: 'string', 
    description: '弹框路径（非肯定项）：用户输入的修改意见或反馈' 
  },
  // ...
}
```

## 使用示例

### Agent 调用
```typescript
const result = await tools.reqboard_ask_confirm({
  target: 'artifact',
  kind: 'requirement',
  question: '需求文档是否完整准确？确认后将推进到设计阶段',
  options: ['确认推进', '需要修改', '暂停']
})
```

### 用户选择"需要修改"并输入意见
假设用户选择"需要修改"，并在自定义输入框中写：
> "功能点 FR-3 的描述不够清晰，请补充具体的验收标准"

### 返回结果
```json
{
  "success": true,
  "confirmed": false,
  "advanced": false,
  "user_choice": "需要修改",
  "user_feedback": "功能点 FR-3 的描述不够清晰，请补充具体的验收标准",
  "note": "用户选择\"需要修改\"：未落章、未推进。用户反馈：功能点 FR-3 的描述不够清晰，请补充具体的验收标准。按用户意见修改后可重新发起确认"
}
```

### Agent 后续行为
现在 Agent 可以：
1. 看到 `confirmed: false` → 知道没通过
2. 读取 `user_feedback` → **知道具体要改什么**
3. 根据用户反馈修改需求文档
4. 重新调用 `reqboard_ask_confirm` 请求确认

## 台账记录

评论区会记录：
```
[确认弹框] 用户未确认（选择：需要修改）——节点未推进。
问题：需求文档是否完整准确？确认后将推进到设计阶段。
用户意见：功能点 FR-3 的描述不够清晰，请补充具体的验收标准
```

## 兼容性

### 向后兼容
- ✅ 用户选择肯定项 → 行为不变
- ✅ 用户未输入自定义意见 → `user_feedback` 为 `undefined`，不影响现有逻辑
- ✅ 旧代码不读 `user_feedback` → 仍能正常工作

### DSH 弹框能力
- DSH 的 `ask_user_question` 支持 `custom` 自定义输入
- 用户选择选项 + 输入文字 → 两者都会返回
- `answer.selected[0]` = 用户选择的选项
- `answer.custom` = 用户输入的文字

## 验证结果

✅ TypeScript 类型检查通过
✅ Schema 定义正确（`additionalProperties: false` 下新增字段）
✅ 用例逻辑完整（捕获 → 记录 → 返回）

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/application/use-cases/AskConfirm.ts` | 逻辑增强 | 捕获并返回用户反馈 |
| `src/tools/AskConfirmTool/AskConfirmTool.ts` | Schema 扩展 | 添加 user_choice 和 user_feedback 字段 |

## 后续部署

修改已完成类型检查，但需要重启服务：

```bash
cd agent-dh
./scripts/restart-with-build.sh
```

---

**实施时间**: 2026-09-19
**状态**: ✅ 已实现，待部署
**影响范围**: reqboard_ask_confirm 工具（向后兼容）
