# pi-investment 项目结构说明

**项目路径**: `/Users/mac/Documents/ai/pi-investment/`

---

## 📁 项目结构

```
pi-investment/                    # 项目根目录
│
├── src/                         # TypeScript 后端 (AI投资顾问)
│   ├── api/                    # API接口
│   ├── services/               # 业务服务
│   ├── infrastructure/         # 基础设施
│   ├── core/                   # 核心逻辑
│   ├── domain/                 # 领域模型
│   └── ...
│
├── quant/                       # Python 量化系统 ⭐
│   ├── quantsys/               # 量化核心包
│   │   ├── data/              # 数据层
│   │   ├── factors/           # 因子库 (42个因子)
│   │   ├── backtest/          # 回测引擎
│   │   ├── strategies/        # 策略层
│   │   ├── ml/                # 机器学习
│   │   └── risk/              # 风控系统
│   ├── tests/                  # 测试代码
│   ├── examples/               # 使用示例
│   ├── scripts/                # 脚本工具
│   ├── docs/                   # 文档
│   ├── setup.py                # 包配置
│   ├── requirements.txt        # 依赖
│   └── README.md               # 说明
│
├── skills/                      # Agent技能
├── plugins/                     # 插件
├── dashboard/                   # 仪表盘
├── docs/                        # 项目文档
├── package.json                 # Node.js配置
└── tsconfig.json                # TypeScript配置
```

---

## 🎯 两个子项目

### 1. TypeScript 后端 (`src/`)
- **技术栈**: TypeScript + Node.js
- **功能**: AI投资顾问、飞书Bot、API服务
- **运行**: `npm run dev`

### 2. Python 量化系统 (`quant/`)
- **技术栈**: Python + pandas + scikit-learn
- **功能**: 数据获取、因子计算、策略回测、风控管理
- **运行**: `cd quant && python -m quantsys.xxx`

---

## 🔗 两者关系

```
TypeScript后端 (src/)
    ↓ 调用
Python量化系统 (quant/)
    ↓ 返回
量化分析结果
```

**集成方式**:
- TypeScript通过 `python-shell` 或 `child_process` 调用Python脚本
- Python返回JSON格式的分析结果
- TypeScript展示给用户（飞书/API）

---

## ✅ 目录结构优势

1. **清晰分离**: TypeScript和Python代码完全分开
2. **独立开发**: 两个团队可以并行开发
3. **易于维护**: 各自的依赖和配置独立
4. **灵活部署**: 可以分别部署或一起部署

---

## 📝 总结

**当前结构是合理的！**

- ✅ TypeScript后端在 `src/`
- ✅ Python量化在 `quant/`
- ✅ 两者通过进程间通信集成
- ✅ 符合微服务架构思想

**不需要再调整目录结构！**
