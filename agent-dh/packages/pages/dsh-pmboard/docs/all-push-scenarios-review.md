# 推进节点 ask_user_question 场景补充总结

## 用户反馈
"其他的推进节点 ask_user_question，也需要补充，你看看还有遗漏场景吗"

---

## 全流程推进场景分析

### 阶段 1：draft → brainstorming（立项 → 需求分析）
**推进方式**：reqboard_move(to='brainstorming')  
**人工门**：❌ 无  
**场景**：填写完基本信息自动推进

---

### 阶段 2：brainstorming → design（需求分析 → 设计）
**推进方式**：reqboard_ask_confirm(target='artifact', kind='requirement')  
**人工门**：✅ 确认需求文档  
**选项数量**：5 个

**完整选项**：
```
1. ✅ 确认，推进到下一阶段 (Recommended)
2. 💬 需要澄清（有疑问，但不一定要改）
3. ➕ 需要补充内容（现有内容对，但不够完整）
4. 🛠️ 需要修改
5. ⏸️ 暂停
```

✅ **已完善**（本次改进）

---

### 阶段 3：design → decomposing（设计 → 拆分）
**推进方式**：reqboard_ask_confirm(target='plan')  
**人工门**：✅ 批准拆分计划  
**选项数量**：5 个（同阶段 2）

**完整选项**：
```
1. ✅ 确认，推进到下一阶段 (Recommended)
2. 💬 需要澄清（有疑问，但不一定要改）
3. ➕ 需要补充内容（现有内容对，但不够完整）
4. 🛠️ 需要修改
5. ⏸️ 暂停
```

✅ **已完善**（本次改进）

---

### 阶段 4：decomposing → implementing（拆分 → 实施）
**推进方式**：reqboard_decompose 后自动推进  
**人工门**：❌ 无  
**场景**：拆分完任务自动推进

---

### 阶段 5：implementing → accepting（实施 → 验收）
**推进方式**：所有任务 done 后自动推进  
**人工门**：❌ 无  
**场景**：任务全部完成自动推进

---

### 阶段 6：accepting → archived（验收 → 归档）
**推进方式**：reqboard_accept_sheet（逐项验收）  
**人工门**：✅ 逐项验收  
**选项数量**：4 个

**完整选项**：
```
1. ✅ 通过
2. 💬 需要澄清（仍计为"改进"，请在意见中说明）
3. 🛠 改进（需修改）
4. ❓ 其他
```

⚠️ **部分改进**（新增"需要澄清"）

---

## 本次改进汇总

### 1. reqboard_ask_confirm（阶段 2、3）
**改进前**：3 个选项
```
1. 确认推进
2. 需要修改
3. 暂停
```

**改进后**：5 个选项
```
1. ✅ 确认，推进到下一阶段 (Recommended)
2. 💬 需要澄清（有疑问，但不一定要改）          ← 新增
3. ➕ 需要补充内容（现有内容对，但不够完整）    ← 新增
4. 🛠️ 需要修改
5. ⏸️ 暂停
```

**新增场景**：
- **需要澄清**：理解层面的问题，解释后可能不需要改
- **需要补充内容**：现有内容正确但不完整，需要追加/扩展

---

### 2. reqboard_accept_sheet（阶段 6）
**改进前**：3 个选项
```
1. ✅ 通过
2. 🛠 改进（需修改）
3. ❓ 其他
```

**改进后**：4 个选项
```
1. ✅ 通过
2. 💬 需要澄清（仍计为"改进"，请在意见中说明）  ← 新增
3. 🛠 改进（需修改）
4. ❓ 其他
```

**新增场景**：
- **需要澄清**：不确定验收项含义或如何验证

**技术约束**：
- 当前状态机只支持 **passed / failed 二态**
- "需要澄清"仍计为 `failed`，但通过 `opinion` 字段区分意图
- Agent 可以根据 `opinion` 判断是"真的有问题"还是"只是需要解释"

---

## 未实现的场景（有技术约束）

### 验收单的高级场景

#### 场景 1：部分通过
**用户心态**：
> "核心功能通过了，但性能还需要优化"

**技术约束**：
- 当前状态机只有 `passed` / `failed`，没有 `partial` 中间态
- 实现需要：
  - 扩展验收项状态枚举
  - 修改归档逻辑（部分通过如何处理？）
  - 决定："部分通过"算验收通过还是需要返工？

**临时方案**：
- 选择 "✅ 通过" + 在自定义输入中注明瑕疵
- 或选择 "🛠 改进" + 说明"核心通过但需优化"

---

#### 场景 2：推迟验收
**用户心态**：
> "这项功能现在还没法验，等 XX 完成后再验"

**技术约束**：
- 当前没有 `deferred` 状态
- 验收单逐项弹框，无法"跳过"某项
- 实现需要：
  - 增加 `deferred` 状态
  - 修改弹框逻辑（允许跳过）
  - 后续如何重新验收被推迟的项？

**临时方案**：
- 选择 "❓ 其他" + 说明"推迟验收，原因..."
- 或先点"🛠 改进"让需求回到实施态，等条件满足后再验

---

## 为什么不立即实现"部分通过"和"推迟验收"？

### 1. 状态机复杂度
当前：
```
验收项 = passed | failed
全部 passed → 归档
有 failed → 打回 implementing
```

增加中间态后：
```
验收项 = passed | partial | failed | deferred | ...
partial 怎么处理？算通过还是失败？
deferred 怎么处理？能否归档？还是必须等全部非 deferred？
```

### 2. 归档逻辑
- 当前：全部 `passed` 才能归档
- 如果有 `partial`：
  - 允许归档吗？（有瑕疵的交付物）
  - 还是必须改完才算 `passed`？
- 如果有 `deferred`：
  - 能否先归档其他部分？
  - 还是必须等全部验完？

### 3. 用户体验
- 增加选项 → 增加决策负担
- "部分通过"和"改进（需修改）"的边界在哪？
- 多数情况下，"部分通过"最终还是要改

---

## 当前方案的权衡

### reqboard_ask_confirm（5 选项）✅ 已完善
- ✅ 覆盖了主要场景
- ✅ 区分"理解问题"、"完整性问题"、"准确性问题"
- ✅ 向后兼容
- ✅ 无需修改状态机

### reqboard_accept_sheet（4 选项）⚠️ 部分改进
- ✅ 新增"需要澄清"
- ⚠️ "部分通过"/"推迟验收"通过 `opinion` 补充说明
- ✅ 保持状态机简单（二态判定）
- ✅ 向后兼容

---

## 未来扩展路径（如果真的需要）

### Phase 1：数据模型扩展
```typescript
type AcceptanceItemStatus = 
  | 'pending'
  | 'passed'
  | 'partial'    // 新增：部分通过
  | 'deferred'   // 新增：推迟验收
  | 'failed'
```

### Phase 2：状态机规则
```typescript
// 归档条件
canArchive = (items) => {
  const nonPassed = items.filter(i => i.status !== 'passed')
  const hasDeferred = nonPassed.some(i => i.status === 'deferred')
  const hasPartial = nonPassed.some(i => i.status === 'partial')
  
  // 规则：允许有 partial，但不能有 deferred 或 failed
  return !hasDeferred && !nonPassed.some(i => i.status === 'failed')
}
```

### Phase 3：UI 调整
- 弹框增加选项
- 看板验收面板显示更多状态
- 验收单总结区分不同状态

---

## 实施结果

### ✅ 已完成
1. **reqboard_ask_confirm 扩展到 5 选项**
   - 新增"需要澄清"
   - 新增"需要补充内容"
   - 文件：`src/domain/text/labels.ts` (DEFAULT_CONFIRM_OPTIONS)

2. **reqboard_accept_sheet 扩展到 4 选项**
   - 新增"需要澄清"
   - 文件：`src/domain/text/labels.ts` (ACCEPT_ITEM_OPTIONS)

3. **reqboard_ask_confirm 返回用户反馈**
   - 新增 `user_choice` 和 `user_feedback` 字段
   - 文件：`src/application/use-cases/AskConfirm.ts`
   - 文件：`src/tools/AskConfirmTool/AskConfirmTool.ts`

4. **文档**
   - `docs/ask-confirm-user-feedback.md`
   - `docs/confirm-options-clarification.md`
   - `docs/confirm-option-add-content.md`

### ⏳ 未实现（有技术约束）
1. **验收单的"部分通过"状态**
   - 需要扩展状态机
   - 需要定义归档规则
   - 当前通过 `opinion` 补充说明

2. **验收单的"推迟验收"状态**
   - 需要支持跳过某些项
   - 需要后续重新验收机制
   - 当前通过"❓ 其他"+ 说明实现

---

## 验证结果

✅ TypeScript 类型检查通过  
✅ 文案单点原则遵守  
✅ 向后兼容  
✅ 无破坏性变更

---

## 部署方式

```bash
cd agent-dh
./scripts/restart-with-build.sh
```

---

**实施时间**: 2026-09-19  
**核心价值**: 补充推进场景，让用户反馈更精确，Agent 行为更准确
