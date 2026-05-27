# 部署前检查清单

**项目**: pi-investment  
**模块**: web-frontend 风控检查页面修复  
**版本**: v1.0.0  
**日期**: 2026-05-24

---

## ✅ 代码审查检查

### 后端代码 (quantsys-v2)

- [ ] **语法检查**: Python 语法无错误
  ```bash
  cd quantsys-v2
  python -m py_compile api/server.py
  ```

- [ ] **导入检查**: 所有依赖模块可正常导入
  ```bash
  python -c "from api.server import app; print('OK')"
  ```

- [ ] **端点验证**: 所有修改的端点存在
  - [ ] `POST /api/risk/check`
  - [ ] `GET /api/risk/stop-loss/rules`
  - [ ] `POST /api/risk/stop-loss/rules`
  - [ ] `POST /api/risk/stop-loss/rules/batch`
  - [ ] `PUT /api/risk/stop-loss/rules/:id`
  - [ ] `DELETE /api/risk/stop-loss/rules/:id`

- [ ] **辅助函数**: 新增函数正确定义
  - [ ] `_normalize_stop_loss_type()`
  - [ ] `_read_stop_loss()`
  - [ ] `_write_stop_loss()`

### 前端代码 (web-frontend)

- [ ] **TypeScript 编译**: 无类型错误
  ```bash
  cd web-frontend
  npm run build
  ```

- [ ] **组件检查**: RiskCheck 组件无语法错误
  ```bash
  # 检查 Vue 文件
  cat src/views/RiskCheck/index.vue | grep -E "var:|volatility:|maxDrawdown:"
  ```

- [ ] **类型定义**: API 类型定义完整
  - [ ] `RiskCheckRequest`
  - [ ] `RiskCheckResponse`
  - [ ] `RiskCheckPosition`
  - [ ] `RiskCheckItem`

---

## 🧪 功能测试检查

### 自动化测试

- [ ] **后端 API 测试**: 运行测试脚本
  ```bash
  ./test-risk-check-api.sh
  ```
  
  预期输出:
  - ✅ 后端服务运行正常
  - ✅ 风险检查接口响应成功
  - ✅ 新增字段验证通过
  - ✅ 止损规则创建成功
  - ✅ 字段映射正确
  - ✅ 类型映射正确

### 手动测试

- [ ] **风险检查功能**
  - [ ] 输入账户总值，点击"执行检查"
  - [ ] 风险概览卡片显示正确
  - [ ] 风险指标不全为 0
  - [ ] 持仓风险明细显示真实数据
  - [ ] VaR、波动率、最大回撤显示非零值

- [ ] **行业集中度预警**
  - [ ] 如果有行业 > 50%，显示预警
  - [ ] 预警类型显示"行业集中度"
  - [ ] 预警消息格式正确

- [ ] **止损规则创建**
  - [ ] 点击"设置止损"，当前价格显示正确
  - [ ] 选择"百分比"类型，输入 5%
  - [ ] 保存成功，规则列表显示
  - [ ] 验证 JSON 文件中字段正确

- [ ] **批量设置止损**
  - [ ] 选择多个股票
  - [ ] 设置止损比例
  - [ ] 批量创建成功

- [ ] **止损规则管理**
  - [ ] 编辑规则功能正常
  - [ ] 删除规则功能正常
  - [ ] 规则列表显示正确

---

## 🔍 边界情况检查

- [ ] **无持仓数据**: 不报错，显示空表格
- [ ] **账户总值为 0**: 不报错，占比计算正确
- [ ] **无 K线数据**: 不报错，当前价格显示 0
- [ ] **无风险指标**: 不报错，指标显示 0
- [ ] **大量持仓 (20+)**: 响应时间 < 3秒

---

## 📊 数据验证检查

### 后端响应数据

- [ ] **风险检查响应结构**
  ```json
  {
    "total_holdings": number,
    "checks": [
      {
        "symbol": string,
        "position_value": number,
        "current_price": number,      // ✅ 必须存在
        "var_95": number,              // ✅ 必须存在
        "volatility": number,          // ✅ 必须存在
        "max_drawdown": number,        // ✅ 必须存在
        "checks": [
          {
            "type": "concentration" | "sector_concentration" | "var",
            "level": "high" | "medium" | "low",
            "message": string,
            "suggestion": string
          }
        ]
      }
    ],
    "risk_level": "high" | "medium" | "low"
  }
  ```

- [ ] **止损规则响应结构**
  ```json
  {
    "success": true,
    "rule": {
      "id": string,
      "symbol": string,
      "type": "fixed_percent" | "fixed_price" | "trailing_stop",
      "stopLossPercent": number,     // ✅ 必须存在
      "triggerPercent": number,      // ✅ 必须存在
      "status": "active",
      "createdAt": string,
      "updatedAt": string
    }
  }
  ```

### 前端数据映射

- [ ] **positionRisks 数据**
  - [ ] `var` 字段使用 `c.var_95`
  - [ ] `volatility` 字段使用 `c.volatility`
  - [ ] `maxDrawdown` 字段使用 `c.max_drawdown`
  - [ ] `currentPrice` 字段使用 `c.current_price`

- [ ] **warnings 数据**
  - [ ] 支持 `sector_concentration` 类型
  - [ ] 类型映射正确显示中文

---

## 🔐 安全检查

- [ ] **输入验证**: 后端验证用户输入
  - [ ] `accountValue` 为正数
  - [ ] `triggerPercent` 在 0-100 范围内
  - [ ] `symbol` 格式正确

- [ ] **SQL 注入**: 使用参数化查询
- [ ] **XSS 防护**: 前端正确转义用户输入
- [ ] **CORS 配置**: 后端 CORS 设置正确

---

## 📈 性能检查

- [ ] **响应时间**
  - [ ] 5 个持仓: < 1s
  - [ ] 10 个持仓: < 2s
  - [ ] 20 个持仓: < 3s

- [ ] **数据库查询**
  - [ ] 使用索引查询
  - [ ] 避免 N+1 查询
  - [ ] 查询结果合理

- [ ] **前端渲染**
  - [ ] 表格渲染流畅
  - [ ] 无明显卡顿
  - [ ] 内存使用正常

---

## 🔄 向后兼容性检查

- [ ] **旧版本 API 调用**: 仍然支持
  - [ ] 发送 `stopLossPercent` 仍然工作
  - [ ] 发送 `type: "fixed_percent"` 仍然工作

- [ ] **现有数据**: 不受影响
  - [ ] 现有止损规则仍然可读
  - [ ] 现有持仓数据正常显示

- [ ] **其他页面**: 功能正常
  - [ ] 首页正常
  - [ ] 持仓管理正常
  - [ ] 交易记录正常

---

## 📝 文档检查

- [ ] **代码注释**: 关键逻辑有注释
- [ ] **API 文档**: 接口文档更新
- [ ] **修复文档**: 完整且准确
  - [ ] 审查报告
  - [ ] 修复详情
  - [ ] 测试指南
  - [ ] 部署清单

- [ ] **CHANGELOG**: 记录修复内容
- [ ] **README**: 更新功能说明

---

## 🚀 部署准备

### 环境检查

- [ ] **Python 版本**: >= 3.9
- [ ] **Node.js 版本**: >= 22.0.0
- [ ] **数据库连接**: PostgreSQL 可访问
- [ ] **Redis 连接**: Redis 可访问（如果使用）

### 依赖检查

- [ ] **Python 依赖**: requirements.txt 完整
  ```bash
  cd quantsys-v2
  pip install -r requirements.txt
  ```

- [ ] **Node.js 依赖**: package.json 完整
  ```bash
  cd web-frontend
  npm install
  ```

### 配置检查

- [ ] **环境变量**: .env 文件配置正确
  - [ ] `QUANTSYS_API_HOST=127.0.0.1`
  - [ ] `QUANTSYS_API_PORT=5001`
  - [ ] `PGHOST=127.0.0.1`
  - [ ] `PGPORT=5432`

- [ ] **端口占用**: 端口未被占用
  ```bash
  lsof -i :5001  # quantsys-v2
  lsof -i :3001  # web-frontend
  ```

---

## 🔧 部署步骤

### 1. 备份

- [ ] **备份数据库**
  ```bash
  pg_dump quant_investment > backup_$(date +%Y%m%d).sql
  ```

- [ ] **备份止损规则**
  ```bash
  cp ~/.pi-invest/stop_loss_rules.json ~/.pi-invest/stop_loss_rules.json.backup
  ```

- [ ] **备份代码**
  ```bash
  git stash
  git branch backup-$(date +%Y%m%d)
  ```

### 2. 部署后端

- [ ] **停止后端服务**
  ```bash
  # 如果使用 systemd
  sudo systemctl stop quantsys-v2
  
  # 或者手动停止进程
  pkill -f "python api/server.py"
  ```

- [ ] **更新代码**
  ```bash
  cd quantsys-v2
  git pull origin main
  ```

- [ ] **启动后端服务**
  ```bash
  python api/server.py
  
  # 或使用 systemd
  sudo systemctl start quantsys-v2
  ```

- [ ] **验证服务**
  ```bash
  curl http://127.0.0.1:5001/api/health
  ```

### 3. 部署前端

- [ ] **构建前端**
  ```bash
  cd web-frontend
  npm run build
  ```

- [ ] **部署静态文件**
  ```bash
  # 如果使用 nginx
  sudo cp -r dist/* /var/www/web-frontend/
  
  # 重启 nginx
  sudo systemctl reload nginx
  ```

- [ ] **验证访问**
  ```bash
  curl http://127.0.0.1:3001
  ```

### 4. 验证部署

- [ ] **运行自动化测试**
  ```bash
  ./test-risk-check-api.sh
  ```

- [ ] **手动测试关键功能**
  - [ ] 风险检查
  - [ ] 止损规则创建
  - [ ] 批量设置止损

- [ ] **检查日志**
  ```bash
  # 后端日志
  tail -f quantsys-v2/logs/server.log
  
  # Nginx 日志
  tail -f /var/log/nginx/access.log
  ```

---

## 🔙 回滚计划

### 如果部署失败

- [ ] **回滚后端**
  ```bash
  cd quantsys-v2
  git checkout backup-$(date +%Y%m%d)
  python api/server.py
  ```

- [ ] **回滚前端**
  ```bash
  cd web-frontend
  git checkout backup-$(date +%Y%m%d)
  npm run build
  sudo cp -r dist/* /var/www/web-frontend/
  ```

- [ ] **恢复数据**
  ```bash
  # 恢复数据库
  psql quant_investment < backup_$(date +%Y%m%d).sql
  
  # 恢复止损规则
  cp ~/.pi-invest/stop_loss_rules.json.backup ~/.pi-invest/stop_loss_rules.json
  ```

---

## 📊 监控指标

### 部署后监控（24小时）

- [ ] **错误率**: < 1%
- [ ] **响应时间**: P95 < 3s
- [ ] **CPU 使用率**: < 70%
- [ ] **内存使用率**: < 80%
- [ ] **数据库连接**: 正常
- [ ] **用户反馈**: 无严重问题

### 监控命令

```bash
# 检查进程
ps aux | grep "python api/server.py"

# 检查端口
netstat -tlnp | grep 5001

# 检查日志错误
grep -i error quantsys-v2/logs/server.log | tail -20

# 检查响应时间
curl -w "@curl-format.txt" -o /dev/null -s http://127.0.0.1:5001/api/risk/check
```

---

## ✅ 最终确认

### 部署前最终检查

- [ ] 所有代码审查通过
- [ ] 所有功能测试通过
- [ ] 所有边界情况测试通过
- [ ] 性能测试通过
- [ ] 安全检查通过
- [ ] 文档完整
- [ ] 备份完成
- [ ] 回滚计划准备好

### 部署负责人签字

- **开发人员**: ________________  日期: ________
- **测试人员**: ________________  日期: ________
- **运维人员**: ________________  日期: ________

---

## 📞 紧急联系

**如果部署出现问题**:
- 开发负责人: [联系方式]
- 运维负责人: [联系方式]
- 紧急回滚: 执行"回滚计划"章节

---

**检查清单版本**: 1.0  
**最后更新**: 2026-05-24  
**下次审查**: 部署后 24 小时
