# ADR-001: Flask 到 FastAPI 的迁移

**状态**: 已采纳 ✅  
**日期**: 2026-07-08  
**决策者**: 开发团队  
**生效日期**: 2026-08-02

---

## 背景

quantsys-v2 最初使用 Flask 作为 Web 框架。随着系统复杂度增加，遇到以下问题：

1. **异步支持不足**: Flask 原生不支持 async/await，WebSocket 实现复杂
2. **类型安全**: 缺乏请求/响应的类型验证
3. **文档生成**: 需要手动维护 API 文档
4. **性能瓶颈**: 单线程模型，难以应对高并发

---

## 决策

**迁移到 FastAPI 作为主要 Web 框架**

### 理由

1. **原生异步支持**: FastAPI 基于 Starlette，完美支持 async/await
2. **自动类型验证**: 基于 Pydantic，自动验证请求参数和响应
3. **自动文档生成**: OpenAPI (Swagger) 和 ReDoc 自动生成
4. **更高性能**: 基于 ASGI，性能接近 Go/Node.js
5. **生态成熟**: 2026 年已成为 Python Web 框架主流选择

---

## 迁移策略

### 阶段 1: 并行运行（2026-07-08 至 2026-08-01）

- Flask 继续运行在 5001 端口
- FastAPI 逐步实现新路由
- 两套系统并存，确保平滑过渡

### 阶段 2: 切换生产（2026-08-02）

- FastAPI 接管 5001 端口
- Flask 保留作为回滚备份
- 生产流量切换到 FastAPI

### 阶段 3: 清理（2026-09-01 计划）

- 验证 FastAPI 稳定运行 30 天后
- 删除 Flask 相关代码
- 清理遗留依赖

---

## 技术细节

### 路由迁移

**Flask**:
```python
@app.route('/api/pools', methods=['GET'])
def get_pools():
    pools = pool_service.list_pools()
    return jsonify({'pools': pools})
```

**FastAPI**:
```python
@router.get('/api/pools')
async def get_pools() -> PoolListResponse:
    pools = await pool_service.list_pools()
    return PoolListResponse(pools=pools)
```

### 依赖注入

**FastAPI** 使用依赖注入系统：
```python
from fastapi import Depends

def get_pool_service() -> PoolService:
    return PoolService()

@router.get('/api/pools')
async def get_pools(
    service: PoolService = Depends(get_pool_service)
):
    return await service.list_pools()
```

### ORM Session 管理

**修复连接池泄漏**（2026-08-18）:
- 问题：中间件 + endpoint 双重创建 session
- 解决：统一使用 SessionCleanupMiddleware + endpoint 包装

---

## 影响

### 正面影响 ✅

1. **性能提升**: 响应时间减少 30%
2. **开发效率**: 自动文档生成节省维护时间
3. **类型安全**: Pydantic 捕获 80% 的参数错误
4. **异步能力**: WebSocket 实现简化 50% 代码

### 负面影响 ⚠️

1. **学习曲线**: 团队需要学习 FastAPI 和 Pydantic
2. **遗留代码**: Flask 代码暂时保留，增加维护负担
3. **测试迁移**: 所有集成测试需要重写

---

## 替代方案

### 方案 A: 继续使用 Flask + 扩展

**优点**: 无需迁移，团队熟悉  
**缺点**: 异步支持差，性能瓶颈持续

**决策**: ❌ 拒绝 - 无法解决根本问题

### 方案 B: 迁移到 Django

**优点**: 功能全面，ORM 强大  
**缺点**: 过于笨重，与现有架构不符

**决策**: ❌ 拒绝 - 过度工程化

### 方案 C: 迁移到 FastAPI

**优点**: 性能好，异步原生，类型安全  
**缺点**: 需要学习新框架

**决策**: ✅ 采纳

---

## 验证

### 性能测试结果

| 指标 | Flask | FastAPI | 提升 |
|------|-------|---------|------|
| QPS | 850 | 1200 | +41% |
| P99 延迟 | 85ms | 55ms | -35% |
| 内存占用 | 320MB | 280MB | -12% |

### 稳定性验证

- **运行时长**: 30+ 天无重启
- **错误率**: < 0.01%
- **连接池泄漏**: 已修复（2026-08-18）

---

## 经验教训

### 做得好的 ✅

1. **并行运行**: 确保平滑过渡，无业务中断
2. **自动化测试**: 防止回归错误
3. **快速回滚**: 保留 Flask 备份

### 需要改进 ⚠️

1. **更早规划**: 迁移周期可以更短
2. **团队培训**: 应该提前培训 FastAPI
3. **文档同步**: API 文档更新滞后

---

## 参考资料

- FastAPI 官方文档: https://fastapi.tiangolo.com/
- 迁移指南: `docs/guides/FLASK-TO-FASTAPI-MIGRATION.md`
- 性能测试报告: `docs/work-logs/2026-07/MIGRATION_FINAL_REPORT.md`

---

**决策状态**: ✅ 已完成并验证稳定
