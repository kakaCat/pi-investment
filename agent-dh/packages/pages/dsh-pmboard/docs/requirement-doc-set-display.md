# 设计阶段文档集展示功能实施总结

## 需求
在会话流程节点框（reqboard stage detail panel）的 **design（设计）** 阶段展示：
- 该分类需要的根文档必填节（BASE + DELTA）
- 该分类需要的设计文档（design/*.md）

## 实施内容

### 1. 类型定义更新
**文件**: `packages/pages/dsh-pmboard/src/shared/protocol.ts`

```typescript
// 修改前
export interface DesignStageBody { plan?: PlanRecord }

// 修改后
export interface DesignStageBody { 
  plan?: PlanRecord; 
  category?: RequirementCategory  // ✨ 新增
}
```

### 2. 后端装配器更新
**文件**: `packages/pages/dsh-pmboard/src/application/query/QueryStageDetail.ts`

```typescript
class DesignStageAssembler extends StageDetailAssembler {
  readonly stage = 'design' as const
  protected buildBody(req: RequirementRecord): DesignStageBody {
    return {
      ...(req.plan !== undefined ? { plan: req.plan } : {}),
      ...(req.category !== undefined ? { category: req.category } : {}),  // ✨ 新增
    }
  }
}
```

### 3. 前端渲染器更新
**文件**: `packages/pages/dsh-pmboard/src/client/stage-panel.ts`

#### 3.1 新增导入
```typescript
import { CATEGORY_DELTAS, COMMON_ROOT_SECTIONS } from '../application/internal/category-doc-sets.js'
```

#### 3.2 更新 renderDesignBody
展示逻辑：
1. 根据 `body.category` 查找对应的 `CATEGORY_DELTAS` 配置
2. 展示根文档必填节 = `COMMON_ROOT_SECTIONS`（BASE：边界）+ `delta.rootSectionsDelta`（类型专属）
3. 展示设计文档清单 = `delta.requiredDesignDocs`
4. 无设计文档时显示"无（本类型跳过设计文档）"

## 展示效果示例

### Feature 类型
```
📋 本类型需要的文档
根文档必填节：边界、产品定义、用户与角色、功能点
设计文档：design/architecture.md、design/data-model.md、design/interfaces.md、design/test-cases.md
```

### Bug 类型
```
📋 本类型需要的文档
根文档必填节：边界、复现步骤、根因、回归
设计文档：无（本类型跳过设计文档）
```

### Refactor 类型
```
📋 本类型需要的文档
根文档必填节：边界、现状、目标结构、行为不变式
设计文档：design/architecture.md、design/migration.md
```

## 验证结果

✅ TypeScript 类型检查通过
✅ 客户端 bundle 构建成功（228,821 bytes）
✅ 符号验证通过
✅ 括号配对检查通过

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/shared/protocol.ts` | 类型扩展 | DesignStageBody 添加 category 字段 |
| `src/application/query/QueryStageDetail.ts` | 数据装配 | DesignStageAssembler 输出 category |
| `src/client/stage-panel.ts` | UI 渲染 | renderDesignBody 展示文档集要求 |

## 设计原则遵循

✅ **系统负责格式，人负责内容**  
   - 文档集规范由系统展示，Agent 按清单交付

✅ **单一事实源**  
   - 文档集定义来自 `category-doc-sets.ts` 的 CATEGORY_DELTAS
   - 不重复定义，保证一致性

✅ **纯文字监控视角**  
   - 使用 📋 emoji + 灰色辅助文字
   - 无装饰元素（pill/徽章/进度条）
   - 符合 stage-panel v4 设计规范

## 2026-09-17 扩展（REQ-81aabd）：设计文档逐份交付状态

**问题**：上文只展示"本类型**要求**哪些设计文档"这个静态清单，与需求目录里**实际交了什么**脱节——
`design/*.md` 被自动发现成 `kind=notes`，面板上根本不列已提交的设计文档；用户看到的永远是模板名，
看不出哪份交了、哪份没交。

**做法**（选项 A：只加呈现，不动门禁）：

| 层 | 变更 |
|----|------|
| domain | `ArtifactKind` 增 `design`；`kindForRelPath` 增 `^design/.+\.md$` → `design`（非 .md 仍 `notes`） |
| adapters | `stageForKind('design')` → `design`；`syncReqArtifacts` 回填 `autoDiscovered` 旧条目的 kind（规则升级后旧文件不再停在 notes） |
| application | 新增 `internal/design-docs.ts`：`designDocStatus(req, category)` → `{name, path, submitted}[]`；`DesignStageAssembler` 输出 `body.designDocs` |
| protocol | `DesignDocStatus` + `DesignStageBody.designDocs?` |
| client | `renderDesignBody` 逐份渲染 `✅ 已交 / ⬜ 未交`（`data-design-doc`/`data-submitted` 属性便于测试）；`ARTIFACT_KIND_LABELS` 增「设计文档」；追溯链插入 `design` |

**不做**：不改 `STAGE_ARTIFACT_REQUIREMENTS`、`ARTIFACT_CONFIRM_GATES` 或任何推进条件——
提交时的 `missingCategoryDocs()` 闸门保持不变，设计文档**不成为新的卡点**。

## 后续部署

需要重启 Agent-DH 服务以加载新构建的 client bundle：

```bash
cd agent-dh
./scripts/restart-with-build.sh
```

或者（如果已经构建好）：

```bash
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh
```

---

**实施时间**: 2026-09-19
**验证状态**: ✅ 全部通过
