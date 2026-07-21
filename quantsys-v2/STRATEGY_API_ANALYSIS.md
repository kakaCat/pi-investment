# 策略API分析报告

## 当前状态

### 数据库统计
- **总策略数**: 50个
- **策略类型分布**:
  - `code_type='indicator'`: 50个
  - `code_type='strategy'`: 0个
  - `code_type='script'`: 0个

### API端点测试结果

#### 1. 获取所有策略
```bash
GET /api/strategies/list?pageSize=100
```
✅ **正常** - 返回50个策略

#### 2. 按类型筛选
```bash
GET /api/strategies/list?codeType=indicator&pageSize=100
```
✅ **正常** - 返回50个indicator策略

```bash
GET /api/strategies/list?codeType=strategy
```
✅ **正常** - 返回0个（数据库中确实没有strategy类型）

```bash
GET /api/strategies/list?codeType=script
```
✅ **正常** - 返回0个（数据库中确实没有script类型）

#### 3. 内置策略
```bash
GET /api/strategies/list?source=builtin
```
✅ **正常** - 返回19个内置策略

### 策略字段映射

#### 数据库字段 → API返回字段
- `code_type` (indicator/strategy/script) → `type` (momentum/trend/arbitrage)
- `strategy_type` → `strategyType` (保持原值)
- `strategy_name` → `name`
- `code_content` → `code`
- `parsed_params` → `params`

### 示例策略数据

```json
{
  "id": "430",
  "name": "DISCOVERY-RSI均值回归-600519.SH",
  "strategyType": "indicator",
  "type": "momentum",
  "status": "stopped",
  "description": "[自动发现] RSI超卖买入，超买卖出",
  "code": "...",
  "params": [...],
  "isActive": true
}
```

## 结论

✅ **策略API工作正常**
- 所有50个策略都能正常获取
- 筛选功能正常工作
- 内置策略正常返回

## 可能的问题

如果前端显示"很多策略不显示"，可能原因：

1. **分页问题**: 默认每页只显示20个策略
   - 解决方案：增加`pageSize`参数或实现分页导航

2. **前端筛选**: 前端可能在按某个字段筛选时出错
   - 检查前端是否正确使用`codeType`参数
   - 检查前端是否正确处理`strategyType`字段

3. **字段映射**: 前端期望的字段名与API返回不一致
   - 数据库的`code_type`在API中变成了`type`
   - 需要确认前端使用的是哪个字段

4. **数据确实缺失**: 
   - 数据库中只有`indicator`类型策略
   - 如果用户期望看到`strategy`或`script`类型，需要创建这些类型的策略

## 建议

1. 检查前端代码中的策略列表渲染逻辑
2. 确认前端使用的筛选条件
3. 如需要其他类型策略，需要在数据库中创建
