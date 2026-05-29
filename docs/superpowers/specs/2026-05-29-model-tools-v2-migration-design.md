# Model Tools V2 迁移设计文档

**日期：** 2026-05-29  
**作者：** Claude Code  
**状态：** 设计完成

## 1. 概述

### 1.1 目标

将 TypeScript Agent 的 5 个模型工具从废弃的 v1 daemon 完全迁移到 quantsys-v2 Flask API（端口 5001），修复 `model_list` 工具报错，统一模型管理接口。

### 1.2 背景

**当前问题：**
- 用户调用 `model_list` 工具报错：`Method 'list_models' not found`
- 5 个模型工具（`list`、`predict`、`train`、`evaluate`、`monitor`）全部使用废弃的 `callQuantSysDaemon()`
- v1 daemon 已不再维护，导致工具不可用

**v2 后端现状：**
- ✅ 已有端点：`POST /api/ml/train`、`POST /api/ml/predict`、`GET /api/ml/model/info`
- ❌ 缺少端点：`GET /api/ml/models`（列表）、`GET /api/ml/model/evaluate`（评估）、`GET /api/ml/model/monitor`（监控）
- ✅ Repository 层：`MLModelRepository.list_models()` 已实现但未暴露

### 1.3 迁移策略

**方案选择：** 最小化改动（方案 1）

**实施步骤：**
1. 在 v2 后端补充 3 个缺失的 API 端点
2. 在 `QuantV2Client` 添加 5 个模型相关方法
3. 更新 5 个 TypeScript 工具，替换 v1 调用为 v2 客户端调用

**原则：**
- 复用 v2 现有的 ML 基础设施（`ml_routes.py`、`MLModelRepository`）
- 保持工具接口不变，只改内部实现
- 简化版监控功能（不做完整的 PSI/KS 检验）
- 与已迁移的数据工具模式保持一致

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────┐
│   TypeScript Agent Tools                │
│   src/infrastructure/tools/model/       │
│   - list-tool.ts                        │
│   - predict-tool.ts                     │
│   - train-tool.ts                       │
│   - evaluate-tool.ts                    │
│   - monitor-tool.ts                     │
└──────────────┬──────────────────────────┘
               │ 调用
               ▼
┌─────────────────────────────────────────┐
│   QuantV2Client                          │
│   src/infrastructure/quant/              │
│   quant-v2-client.ts                     │
│   - trainModel()         ← 新增          │
│   - predictModel()       ← 新增          │
│   - listModels()         ← 新增          │
│   - evaluateModel()      ← 新增          │
│   - monitorModel()       ← 新增          │
└──────────────┬──────────────────────────┘
               │ HTTP
               ▼
┌─────────────────────────────────────────┐
│   quantsys-v2 Flask API                  │
│   api/ml_routes.py                       │
│   - POST /api/ml/train        ✅ 已有    │
│   - POST /api/ml/predict      ✅ 已有    │
│   - GET  /api/ml/model/info   ✅ 已有    │
│   - GET  /api/ml/models       ← 新增     │
│   - GET  /api/ml/model/evaluate ← 新增   │
│   - GET  /api/ml/model/monitor  ← 新增   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   MLModelRepository                      │
│   repositories/ml_model_repository.py    │
│   - list_models()            ✅ 已有     │
│   - get_by_type_version()    ✅ 已有     │
│   - save_model()             ✅ 已有     │
└─────────────────────────────────────────┘
```

### 2.2 迁移范围

**后端新增（quantsys-v2）：**
- 3 个新 API 端点（`/api/ml/models`、`/api/ml/model/evaluate`、`/api/ml/model/monitor`）
- 简化版模型监控逻辑

**客户端新增（TypeScript）：**
- 5 个 QuantV2Client 方法
- 类型定义（`MLModel`、`ModelEvaluation`、`ModelMonitor` 等）

**工具更新（TypeScript）：**
- 5 个工具文件，替换 `callQuantSysDaemon()` 为 v2 客户端调用
- 保持工具接口不变（参数、返回格式）

## 3. API 端点设计

### 3.1 GET /api/ml/models - 列出模型

**功能：** 列出所有训练好的模型，支持按类型、状态过滤

**请求参数（Query）：**
```typescript
{
  model_type?: string;    // 过滤模型类型：xgboost/lightgbm
  status?: string;        // 过滤状态：ready/training/failed，默认 ready
  limit?: number;         // 返回数量，默认 20
}
```

**响应格式：**
```json
{
  "success": true,
  "models": [
    {
      "id": 1,
      "model_type": "xgboost",
      "version": "20260529_143022",
      "train_date": "2026-05-29T14:30:22",
      "test_accuracy": 0.68,
      "f1_score": 0.65,
      "feature_count": 42,
      "train_samples": 15000,
      "status": "ready"
    }
  ],
  "total": 1
}
```

**实现：**
```python
@app.route("/api/ml/models", methods=["GET"])
@_ml_error_handler
def ml_models_list():
    """列出所有模型"""
    model_type = request.args.get("model_type")
    status = request.args.get("status", "ready")
    limit = int(request.args.get("limit", 20))
    
    models = _model_repo.list_models(model_type, status, limit)
    
    return jsonify({
        "success": True,
        "models": _sanitize_for_json(models),
        "total": len(models)
    })
```

---

### 3.2 GET /api/ml/model/evaluate - 评估模型

**功能：** 获取模型的完整训练报告和性能指标

**请求参数（Query）：**
```typescript
{
  model_type?: string;    // 默认 xgboost
  version?: string;       // 默认 latest
}
```

**响应格式：**
```json
{
  "success": true,
  "evaluation": {
    "model_type": "xgboost",
    "version": "20260529_143022",
    "metrics": {
      "train_accuracy": 0.72,
      "test_accuracy": 0.68,
      "precision": 0.66,
      "recall": 0.64,
      "f1_score": 0.65,
      "roc_auc": 0.71
    },
    "training_report": {
      "cv_scores": [0.67, 0.69, 0.68, 0.70, 0.66],
      "feature_importance": {
        "rsi": 0.15,
        "macd": 0.12,
        "volume_ratio": 0.10
      },
      "confusion_matrix": [[3200, 1800], [1600, 3400]]
    }
  }
}
```

**实现：**
```python
@app.route("/api/ml/model/evaluate", methods=["GET"])
@_ml_error_handler
def ml_model_evaluate():
    """评估模型性能"""
    model_type = request.args.get("model_type", "xgboost")
    version = request.args.get("version", "latest")
    
    model = _model_repo.get_by_type_version(model_type, version)
    if not model:
        return jsonify({"success": False, "error": "模型不存在"}), 404
    
    # 解析 training_report
    report = model.get("training_report", {})
    if isinstance(report, str):
        report = _json.loads(report)
    
    return jsonify({
        "success": True,
        "evaluation": {
            "model_type": model["model_type"],
            "version": model["version"],
            "metrics": {
                "train_accuracy": model.get("train_accuracy"),
                "test_accuracy": model.get("test_accuracy"),
                "precision": model.get("precision"),
                "recall": model.get("recall"),
                "f1_score": model.get("f1_score"),
                "roc_auc": model.get("roc_auc")
            },
            "training_report": report
        }
    })
```

---

### 3.3 GET /api/ml/model/monitor - 监控模型漂移

**功能：** 检测模型特征是否发生漂移（简化版）

**请求参数（Query）：**
```typescript
{
  model_type?: string;    // 默认 xgboost
  version?: string;       // 默认 latest
  days?: number;          // 对比最近N天数据，默认 30
}
```

**响应格式：**
```json
{
  "success": true,
  "monitor": {
    "model_type": "xgboost",
    "version": "20260529_143022",
    "drift_detected": false,
    "drift_score": 0.12,
    "threshold": 0.3,
    "recommendation": "模型表现稳定，无需重训练",
    "top_drift_features": [
      {"feature": "volume_ratio", "drift": 0.08},
      {"feature": "rsi", "drift": 0.05}
    ],
    "checked_at": "2026-05-29T15:00:00"
  }
}
```

**实现（简化版）：**
```python
@app.route("/api/ml/model/monitor", methods=["GET"])
@_ml_error_handler
def ml_model_monitor():
    """监控模型漂移（简化版）"""
    model_type = request.args.get("model_type", "xgboost")
    version = request.args.get("version", "latest")
    days = int(request.args.get("days", 30))
    
    model = _model_repo.get_by_type_version(model_type, version)
    if not model:
        return jsonify({"success": False, "error": "模型不存在"}), 404
    
    # 简化实现：返回固定的监控结果
    # 实际生产环境可以对比训练数据与最近数据的特征分布
    return jsonify({
        "success": True,
        "monitor": {
            "model_type": model["model_type"],
            "version": model["version"],
            "drift_detected": False,
            "drift_score": 0.0,
            "threshold": 0.3,
            "recommendation": "模型监控功能简化版，建议使用 web-frontend 查看详细指标",
            "top_drift_features": [],
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
    })
```

**简化说明：**
- 当前版本返回固定的监控结果（无漂移）
- 未来可扩展：对比训练数据与最近数据的特征分布，计算 PSI/KS 统计量
- 漂移检测逻辑可后续增强，不影响 API 接口

## 4. TypeScript 客户端设计

### 4.1 类型定义

在 `src/infrastructure/quant/types.ts` 添加：

```typescript
// ─── 模型列表 ────────────────────────────────────────────

export interface MLModel {
  id: number;
  model_type: string;
  version: string;
  train_date: string;
  test_accuracy: number;
  f1_score?: number;
  feature_count: number;
  train_samples: number;
  status: string;
}

export interface ListModelsResponse {
  success: boolean;
  models: MLModel[];
  total: number;
  error?: string;
}

// ─── 模型评估 ────────────────────────────────────────────

export interface ModelMetrics {
  train_accuracy: number;
  test_accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  roc_auc: number;
}

export interface ModelEvaluation {
  model_type: string;
  version: string;
  metrics: ModelMetrics;
  training_report: {
    cv_scores?: number[];
    feature_importance?: Record<string, number>;
    confusion_matrix?: number[][];
  };
}

export interface EvaluateModelResponse {
  success: boolean;
  evaluation?: ModelEvaluation;
  error?: string;
}

// ─── 模型监控 ────────────────────────────────────────────

export interface DriftFeature {
  feature: string;
  drift: number;
}

export interface ModelMonitor {
  model_type: string;
  version: string;
  drift_detected: boolean;
  drift_score: number;
  threshold: number;
  recommendation: string;
  top_drift_features: DriftFeature[];
  checked_at: string;
}

export interface MonitorModelResponse {
  success: boolean;
  monitor?: ModelMonitor;
  error?: string;
}
```

### 4.2 QuantV2Client 方法

在 `src/infrastructure/quant/quant-v2-client.ts` 添加：

```typescript
/**
 * 列出模型
 */
export async function listModels(
  modelType?: string,
  status?: string,
  limit?: number
): Promise<ListModelsResponse> {
  const params = new URLSearchParams();
  if (modelType) params.append("model_type", modelType);
  if (status) params.append("status", status);
  if (limit) params.append("limit", limit.toString());
  
  const url = `/api/ml/models${params.toString() ? `?${params.toString()}` : ""}`;
  return fetchV2<ListModelsResponse>(url, { method: "GET" });
}

/**
 * 评估模型
 */
export async function evaluateModel(
  modelType: string = "xgboost",
  version: string = "latest"
): Promise<EvaluateModelResponse> {
  const params = new URLSearchParams({ model_type: modelType, version });
  
  return fetchV2<EvaluateModelResponse>(
    `/api/ml/model/evaluate?${params.toString()}`,
    { method: "GET" }
  );
}

/**
 * 监控模型漂移
 */
export async function monitorModel(
  modelType: string = "xgboost",
  version: string = "latest",
  days: number = 30
): Promise<MonitorModelResponse> {
  const params = new URLSearchParams({
    model_type: modelType,
    version,
    days: days.toString()
  });
  
  return fetchV2<MonitorModelResponse>(
    `/api/ml/model/monitor?${params.toString()}`,
    { method: "GET" }
  );
}

/**
 * 训练模型（复用现有端点）
 */
export async function trainModel(params: {
  model_type?: string;
  start_date?: string;
  end_date?: string;
  test_size?: number;
  symbols?: string[];
  params?: Record<string, any>;
}): Promise<any> {
  return fetchV2("/api/ml/train", {
    method: "POST",
    body: JSON.stringify(params)
  });
}

/**
 * 模型预测（复用现有端点）
 */
export async function predictModel(params: {
  model_type?: string;
  version?: string;
  symbols: string[];
  date?: string;
}): Promise<any> {
  return fetchV2("/api/ml/predict", {
    method: "POST",
    body: JSON.stringify(params)
  });
}
```

### 4.3 工具更新模式

以 `model_list` 为例，从：

```typescript
// 旧代码（v1 daemon）
const result = await callQuantSysDaemon("list_models", { status });
```

改为：

```typescript
// 新代码（v2 API）
import { listModels } from "../../quant/quant-v2-client.js";

const response = await listModels(undefined, status);
if (!response.success) {
  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({
        success: false,
        error: response.error || "获取模型列表失败"
      }, null, 2)
    }],
    details: undefined
  };
}

// 格式化输出
const formatted = {
  success: true,
  total: response.total,
  models: response.models.map(m => ({
    model_type: m.model_type,
    version: m.version,
    train_date: m.train_date,
    accuracy: m.test_accuracy,
    features: m.feature_count,
    samples: m.train_samples,
    status: m.status
  }))
};

return {
  content: [{
    type: "text" as const,
    text: JSON.stringify(formatted, null, 2)
  }],
  details: undefined
};
```

**其他 4 个工具采用类似模式：**
- `model_predict` → `predictModel()`
- `model_train` → `trainModel()`
- `model_evaluate` → `evaluateModel()`
- `model_monitor` → `monitorModel()`

## 5. 错误处理

### 5.1 统一错误格式

```typescript
{
  success: false,
  error: string;
  error_code?: string;  // "MODEL_NOT_FOUND" | "INVALID_PARAMS" | "SERVER_ERROR"
}
```

### 5.2 TypeScript 工具错误处理

```typescript
try {
  const response = await listModels();
  
  if (!response.success) {
    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify({
          success: false,
          error: response.error || "未知错误"
        }, null, 2)
      }],
      details: undefined
    };
  }
  
  // 正常处理...
  
} catch (error: any) {
  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({
        success: false,
        error: `API 调用失败: ${error.message}`
      }, null, 2)
    }],
    details: undefined
  };
}
```

### 5.3 后端错误处理

使用现有的 `@_ml_error_handler` 装饰器：

```python
@_ml_error_handler
def ml_models_list():
    # 自动捕获 ValueError, KeyError, FileNotFoundError, Exception
    # 返回统一的错误响应格式
    pass
```

## 6. 向后兼容

### 6.1 废弃标记

保留 `callQuantSysDaemon` 函数定义，但添加 deprecated 注释：

```typescript
/**
 * @deprecated 使用 QuantV2Client 方法替代
 * 该函数仅用于向后兼容，将在未来版本移除
 */
export async function callQuantSysDaemon(command: string, params: any): Promise<string> {
  throw new Error("v1 daemon 已废弃，请使用 v2 API");
}
```

### 6.2 工具接口保持不变

- 工具名称不变（`model_list`、`model_predict` 等）
- 参数结构不变
- 返回格式保持兼容（JSON 字符串）

### 6.3 降级策略

如果 v2 API 不可用，返回友好错误提示：

```typescript
if (error.code === "ECONNREFUSED") {
  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({
        success: false,
        error: "quantsys-v2 服务未启动，请运行: cd quantsys-v2 && python start_all.py"
      }, null, 2)
    }]
  };
}
```

## 7. 测试策略

### 7.1 单元测试

**后端测试（pytest）：**
```python
# tests/api/test_ml_routes.py

def test_ml_models_list(client):
    """测试模型列表端点"""
    response = client.get("/api/ml/models?status=ready&limit=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "models" in data
    assert "total" in data

def test_ml_model_evaluate(client):
    """测试模型评估端点"""
    response = client.get("/api/ml/model/evaluate?model_type=xgboost&version=latest")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "evaluation" in data
    assert "metrics" in data["evaluation"]

def test_ml_model_monitor(client):
    """测试模型监控端点"""
    response = client.get("/api/ml/model/monitor?model_type=xgboost&days=30")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "monitor" in data
```

**客户端测试（Jest）：**
```typescript
// src/infrastructure/quant/quant-v2-client.test.ts

describe("QuantV2Client - Model Methods", () => {
  it("should list models", async () => {
    const response = await listModels("xgboost", "ready", 10);
    expect(response.success).toBe(true);
    expect(response.models).toBeInstanceOf(Array);
  });

  it("should evaluate model", async () => {
    const response = await evaluateModel("xgboost", "latest");
    expect(response.success).toBe(true);
    expect(response.evaluation).toBeDefined();
  });

  it("should monitor model", async () => {
    const response = await monitorModel("xgboost", "latest", 30);
    expect(response.success).toBe(true);
    expect(response.monitor).toBeDefined();
  });
});
```

### 7.2 集成测试

**端到端测试：**
1. 启动 quantsys-v2 服务
2. 调用 Agent 工具
3. 验证返回结果格式和内容

**测试用例：**
- ✅ 正常流程：列出模型、评估模型、监控模型
- ✅ 模型不存在：返回 404 错误
- ✅ 参数错误：返回 400 错误
- ✅ 服务不可用：返回友好错误提示

### 7.3 手动测试清单

```bash
# 1. 启动 v2 服务
cd quantsys-v2 && python start_all.py

# 2. 测试 API 端点
curl "http://127.0.0.1:5001/api/ml/models?status=ready"
curl "http://127.0.0.1:5001/api/ml/model/evaluate?model_type=xgboost&version=latest"
curl "http://127.0.0.1:5001/api/ml/model/monitor?model_type=xgboost&days=30"

# 3. 测试 Agent 工具
cd .. && npm run dev
# 在 Agent 中调用：
# model_list({ status: "all" })
# model_evaluate({ model_id: "latest" })
# model_monitor({ model_id: "latest" })
```

## 8. 实施计划

### 8.1 实施顺序

**阶段 1：后端 API 端点（quantsys-v2）**
1. 在 `ml_routes.py` 添加 3 个新端点
2. 编写单元测试
3. 手动测试 API 响应

**阶段 2：TypeScript 客户端**
1. 在 `types.ts` 添加类型定义
2. 在 `quant-v2-client.ts` 添加 5 个方法
3. 编写客户端单元测试

**阶段 3：工具迁移**
1. 更新 5 个工具文件
2. 测试每个工具的调用
3. 验证返回格式兼容性

**阶段 4：清理与文档**
1. 标记 `callQuantSysDaemon` 为 deprecated
2. 更新 CLAUDE.md 迁移状态
3. 提交代码并创建 PR

### 8.2 预估工作量

- 后端 API 端点：1 小时
- TypeScript 客户端：1 小时
- 工具迁移：1.5 小时
- 测试与验证：0.5 小时
- **总计：4 小时**

### 8.3 验收标准

- ✅ 3 个新 API 端点正常工作
- ✅ 5 个工具全部迁移到 v2
- ✅ `model_list` 工具报错已修复
- ✅ 单元测试覆盖率 > 80%
- ✅ 集成测试通过
- ✅ CLAUDE.md 更新迁移状态

## 9. 风险与缓解

### 9.1 风险识别

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| v2 API 响应格式与 v1 不兼容 | 高 | 中 | 在工具层做格式转换，保持输出一致 |
| 模型监控简化版功能不足 | 中 | 低 | 文档说明简化版限制，引导用户使用 web-frontend |
| v2 服务不稳定 | 高 | 低 | 添加降级策略，返回友好错误提示 |
| 测试覆盖不足 | 中 | 中 | 编写完整的单元测试和集成测试 |

### 9.2 回滚计划

如果迁移后出现严重问题：
1. 恢复 `callQuantSysDaemon` 函数实现
2. 回滚工具文件到迁移前版本
3. 保留 v2 API 端点（不影响其他功能）

## 10. 后续优化

### 10.1 短期优化（1-2 周）

- 增强模型监控功能：实现真实的特征漂移检测（PSI、KS 检验）
- 添加模型版本对比功能
- 优化错误提示信息

### 10.2 长期优化（1-3 月）

- 实现自动重训练触发机制
- 添加模型 A/B 测试功能
- 集成模型性能监控到 web-frontend

## 11. 参考资料

- 已完成的数据工具迁移：`docs/superpowers/specs/2026-05-25-agent-v2-migration-design.md`
- quantsys-v2 架构文档：`quantsys-v2/CLAUDE.md`
- MLModelRepository 实现：`quantsys-v2/repositories/ml_model_repository.py`
- 现有 ML 端点：`quantsys-v2/api/ml_routes.py`
