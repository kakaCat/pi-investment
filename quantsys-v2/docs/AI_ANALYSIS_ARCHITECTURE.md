# AI 市场分析架构设计

**如何将 AI 分析集成到 Agent 系统和 quantsys-v2**

---

## 架构选择

### 三种可能的方案

#### 方案 A：AI 分析完全在 quantsys-v2 内部

```
┌─────────────────────────────────────────────────────────┐
│                    AI Agent (Claude)                     │
│  - 发送命令：ai.analyze --symbol BTC/USDT              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    quantsys-v2                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  CLI Layer                                        │  │
│  │  - ai.analyze 命令                                │  │
│  └───────────────────────────────────────────────────┘  │
│                            ↓                             │
│  ┌───────────────────────────────────────────────────┐  │
│  │  AIAnalysisService                                │  │
│  │  - 数据采集                                        │  │
│  │  - 提示词构建                                      │  │
│  │  - LLM 调用 (OpenAI/Claude API)                  │  │
│  │  - 结果验证                                        │  │
│  └───────────────────────────────────────────────────┘  │
│                            ↓                             │
│  ┌───────────────────────────────────────────────────┐  │
│  │  LLMService                                       │  │
│  │  - OpenAI Provider                                │  │
│  │  - OpenRouter Provider                            │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**优点**：
- ✅ quantsys-v2 功能完整，可独立使用
- ✅ AI Agent 调用简单（一条命令）
- ✅ 人类用户也可以直接使用

**缺点**：
- ❌ quantsys-v2 需要管理 LLM API key
- ❌ 增加 quantsys-v2 的复杂度
- ❌ AI Agent 无法利用自己的上下文和能力

---

#### 方案 B：AI 分析由 AI Agent 自己完成

```
┌─────────────────────────────────────────────────────────┐
│                    AI Agent (Claude)                     │
│  1. 调用：market.get_data --symbol BTC/USDT            │
│  2. 获取数据后，自己分析（利用自己的 LLM 能力）         │
│  3. 生成交易建议                                         │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    quantsys-v2                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  CLI Layer                                        │  │
│  │  - market.get_data 命令                           │  │
│  └───────────────────────────────────────────────────┘  │
│                            ↓                             │
│  ┌───────────────────────────────────────────────────┐  │
│  │  MarketDataService                                │  │
│  │  - 采集价格、K线、技术指标                         │  │
│  │  - 采集新闻、宏观数据                              │  │
│  │  - 返回结构化 JSON                                 │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**优点**：
- ✅ quantsys-v2 保持简单（只负责数据）
- ✅ AI Agent 充分利用自己的能力
- ✅ AI Agent 可以结合对话上下文分析

**缺点**：
- ❌ 每次需要传输大量数据给 AI Agent
- ❌ 人类用户无法直接使用 AI 分析
- ❌ AI Agent 需要重复实现分析逻辑

---

#### 方案 C：混合方案（推荐）⭐

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AI Agent (Claude)                            │
│                                                                       │
│  场景 1：快速分析（使用 quantsys-v2 的 AI 分析）                     │
│    → ai.analyze --symbol BTC/USDT                                   │
│                                                                       │
│  场景 2：深度分析（获取数据，自己分析）                              │
│    → market.get_analysis_data --symbol BTC/USDT                     │
│    → 自己分析数据，结合对话上下文                                    │
│                                                                       │
│  场景 3：辅助决策（获取 AI 建议作为参考）                            │
│    → ai.analyze --symbol BTC/USDT                                   │
│    → 结合自己的判断，做出最终决策                                    │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                            quantsys-v2                               │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  CLI Layer                                                   │   │
│  │  - ai.analyze: 完整 AI 分析（调用 LLM）                      │   │
│  │  - market.get_analysis_data: 只返回数据（不调用 LLM）        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                    ↓                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  AIAnalysisService (可选)                                   │   │
│  │  - 完整的 AI 分析流程                                        │   │
│  │  - 调用 LLMService                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                    ↓                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  MarketDataService (核心)                                   │   │
│  │  - 数据采集和预处理                                          │   │
│  │  - 技术指标计算                                              │   │
│  │  - 新闻和宏观数据                                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**优点**：
- ✅ 灵活性最高：AI Agent 可以选择使用方式
- ✅ quantsys-v2 功能完整：人类用户可以直接使用
- ✅ 性能优化：快速场景用内置 AI，深度场景自己分析
- ✅ 成本优化：避免重复调用 LLM

**缺点**：
- ⚠️ 实现复杂度稍高（需要两套命令）

---

## 推荐方案：混合架构详细设计

### 核心理念

**quantsys-v2 提供两层能力**：
1. **数据层**：采集和预处理市场数据（必需）
2. **分析层**：可选的 AI 分析功能（可选）

**AI Agent 根据场景选择**：
- 简单快速场景：直接调用 quantsys-v2 的 AI 分析
- 复杂深度场景：获取数据后自己分析
- 辅助决策场景：获取 AI 建议作为参考

---

### CLI 命令设计

#### 命令 1：market.get_analysis_data（数据层）

**用途**：获取结构化的市场数据，供 AI Agent 自己分析

**命令**：
```bash
python cli/main.py market.get_analysis_data \
  --market Crypto \
  --symbol BTC/USDT \
  --timeframe 1D \
  --include-macro true \
  --include-news true
```

**返回数据**：
```json
{
  "market": "Crypto",
  "symbol": "BTC/USDT",
  "timeframe": "1D",
  "timestamp": "2024-01-01T12:00:00Z",
  
  "price": {
    "current": 43250.5,
    "change_24h": 2.3,
    "volume_24h": 28500000000
  },
  
  "indicators": {
    "rsi": {
      "value": 65.2,
      "signal": "neutral",
      "interpretation": "RSI在中性区域，无明显超买超卖"
    },
    "macd": {
      "value": 125.3,
      "signal_line": 118.7,
      "histogram": 6.6,
      "signal": "bullish",
      "interpretation": "MACD金叉，看涨信号"
    },
    "moving_averages": {
      "ma5": 42800,
      "ma10": 42500,
      "ma20": 42000,
      "trend": "uptrend",
      "interpretation": "价格在所有均线之上，上升趋势"
    },
    "levels": {
      "support": 42000,
      "resistance": 45000,
      "pivot": 43500
    },
    "volatility": {
      "atr": 850,
      "level": "medium",
      "pct": 2.1
    }
  },
  
  "crypto_factors": {
    "funding_rate": 0.01,
    "open_interest": 12000000000,
    "long_short_ratio": 1.2,
    "exchange_netflow": -150000000,
    "signals": {
      "derivatives_bias": "bullish",
      "flow_bias": "bullish",
      "squeeze_risk": "low"
    },
    "interpretation": "资金费率正常，未平仓量上升，交易所净流出，整体看涨"
  },
  
  "macro": {
    "DXY": {
      "price": 103.5,
      "change": 0.2,
      "changePercent": 0.19,
      "interpretation": "美元小幅走强，对加密货币略有压力"
    },
    "VIX": {
      "price": 18.5,
      "level": "normal",
      "interpretation": "市场波动率正常，风险偏好中性"
    },
    "TNX": {
      "price": 4.25,
      "interpretation": "利率处于高位，对风险资产不利"
    }
  },
  
  "news": [
    {
      "title": "美联储维持利率不变",
      "summary": "美联储宣布维持利率在5.25%-5.50%区间",
      "sentiment": "neutral",
      "date": "2024-01-01",
      "source": "Reuters",
      "geopolitical_level": "none"
    },
    {
      "title": "比特币ETF申请获批",
      "summary": "SEC批准多家机构的比特币现货ETF申请",
      "sentiment": "positive",
      "date": "2024-01-01",
      "source": "Bloomberg",
      "geopolitical_level": "none"
    }
  ],
  
  "summary": {
    "technical_bias": "bullish",
    "fundamental_bias": "neutral",
    "sentiment_bias": "positive",
    "overall_bias": "bullish",
    "confidence": "medium"
  }
}
```

**AI Agent 使用示例**：
```python
# AI Agent 内部逻辑
data = execute_cli("market.get_analysis_data --market Crypto --symbol BTC/USDT")

# AI Agent 自己分析
analysis = f"""
基于以下市场数据分析 BTC/USDT：

技术面：
- RSI: {data['indicators']['rsi']['value']} ({data['indicators']['rsi']['interpretation']})
- MACD: {data['indicators']['macd']['interpretation']}
- 趋势: {data['indicators']['moving_averages']['interpretation']}

加密货币因子：
- {data['crypto_factors']['interpretation']}

宏观环境：
- 美元指数: {data['macro']['DXY']['interpretation']}
- VIX: {data['macro']['VIX']['interpretation']}

新闻：
{format_news(data['news'])}

综合判断：
{自己的分析逻辑}
"""
```

---

#### 命令 2：ai.analyze（分析层）

**用途**：完整的 AI 市场分析（调用 LLM）

**命令**：
```bash
python cli/main.py ai.analyze \
  --market Crypto \
  --symbol BTC/USDT \
  --language zh-CN \
  --model openai/gpt-4o \
  --timeframe 1D
```

**返回数据**：
```json
{
  "decision": "BUY",
  "confidence": 75,
  "summary": "技术指标显示上升趋势，MACD金叉，加密货币市场结构看涨。建议在42800-43500区间建仓，止损42000，目标45000。",
  
  "analysis": {
    "technical": "RSI 65处于中性偏强区域，MACD金叉确认上升动能。价格站稳所有主要均线，短期趋势向上。支撑位42000，阻力位45000。",
    "fundamental": "比特币ETF获批是重大利好，机构资金流入预期强烈。链上数据显示交易所净流出，持有者信心增强。",
    "sentiment": "新闻面偏正面，ETF获批提振市场情绪。宏观环境中性，美元小幅走强但影响有限。无重大地缘政治风险。"
  },
  
  "entry_price": 43200,
  "stop_loss": 42000,
  "take_profit": 45000,
  "position_size_pct": 30,
  "timeframe": "short",
  
  "key_reasons": [
    "MACD金叉，技术面确认上升趋势",
    "比特币ETF获批，机构资金流入预期",
    "加密货币市场结构看涨，资金费率正常，交易所净流出"
  ],
  
  "risks": [
    "美元走强可能对加密货币形成压力",
    "高利率环境对风险资产不利",
    "短期涨幅较大，注意回调风险"
  ],
  
  "technical_score": 75,
  "fundamental_score": 70,
  "sentiment_score": 65,
  "objective_score": 42,
  
  "model": "openai/gpt-4o",
  "usage": {
    "prompt_tokens": 3200,
    "completion_tokens": 520,
    "total_tokens": 3720
  },
  "cost_usd": 0.0128,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**AI Agent 使用示例**：
```python
# AI Agent 快速获取 AI 建议
ai_analysis = execute_cli("ai.analyze --market Crypto --symbol BTC/USDT --language zh-CN")

# AI Agent 可以：
# 1. 直接采纳建议
# 2. 作为参考，结合自己的判断
# 3. 与自己的分析对比验证
```

---

### 实现架构

#### 1. MarketDataService（核心，必需）

```python
# services/market_data_service.py

class MarketDataService:
    """市场数据采集和预处理服务"""
    
    def __init__(self):
        self.kline_repo = KlineRepository()
        self.stock_repo = StockRepository()
        self.news_service = NewsService()
        self.macro_service = MacroDataService()
    
    def get_analysis_data(
        self,
        market: str,
        symbol: str,
        timeframe: str = '1D',
        include_macro: bool = True,
        include_news: bool = True
    ) -> Dict[str, Any]:
        """
        获取完整的分析数据（不调用 LLM）
        
        这是核心方法，供：
        1. AI Agent 获取数据自己分析
        2. AIAnalysisService 调用后再传给 LLM
        3. Web 前端展示原始数据
        """
        result = {
            'market': market,
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now().isoformat()
        }
        
        # 1. 价格数据
        result['price'] = self._fetch_price(market, symbol)
        
        # 2. K线数据
        klines = self._fetch_klines(market, symbol, timeframe)
        
        # 3. 技术指标（带解读）
        result['indicators'] = self._calculate_indicators_with_interpretation(klines)
        
        # 4. 加密货币因子（如果适用）
        if market == 'Crypto':
            result['crypto_factors'] = self._fetch_crypto_factors_with_interpretation(symbol)
        
        # 5. 基本面（如果是股票）
        if market == 'USStock':
            result['fundamental'] = self._fetch_fundamental(symbol)
        
        # 6. 宏观数据
        if include_macro:
            result['macro'] = self._fetch_macro_with_interpretation(market)
        
        # 7. 新闻
        if include_news:
            result['news'] = self._fetch_news_with_sentiment(market, symbol)
        
        # 8. 综合摘要（规则引擎，不用 LLM）
        result['summary'] = self._generate_summary(result)
        
        return result
    
    def _calculate_indicators_with_interpretation(self, klines: List[Dict]) -> Dict:
        """计算技术指标并添加解读"""
        indicators = self._calculate_indicators(klines)
        
        # 添加人类可读的解读
        indicators['rsi']['interpretation'] = self._interpret_rsi(indicators['rsi'])
        indicators['macd']['interpretation'] = self._interpret_macd(indicators['macd'])
        indicators['moving_averages']['interpretation'] = self._interpret_ma(indicators['moving_averages'])
        
        return indicators
    
    def _interpret_rsi(self, rsi_data: Dict) -> str:
        """RSI 解读"""
        value = rsi_data['value']
        if value < 30:
            return f"RSI {value:.1f} 处于超卖区域，可能出现反弹"
        elif value > 70:
            return f"RSI {value:.1f} 处于超买区域，注意回调风险"
        else:
            return f"RSI {value:.1f} 在中性区域，无明显超买超卖"
```

#### 2. AIAnalysisService（可选）

```python
# services/ai_analysis_service.py

class AIAnalysisService:
    """AI 市场分析服务（调用 LLM）"""
    
    def __init__(self):
        self.market_data_service = MarketDataService()
        self.llm_service = LLMService()
    
    def analyze(
        self,
        market: str,
        symbol: str,
        language: str = 'en-US',
        model: Optional[str] = None,
        timeframe: str = '1D'
    ) -> Dict[str, Any]:
        """
        完整的 AI 分析（调用 LLM）
        """
        # 1. 获取市场数据（复用 MarketDataService）
        data = self.market_data_service.get_analysis_data(
            market=market,
            symbol=symbol,
            timeframe=timeframe
        )
        
        # 2. 构建提示词
        system_prompt, user_prompt = self._build_analysis_prompt(data, language)
        
        # 3. 调用 LLM
        llm_result = self.llm_service.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        # 4. 验证和后处理
        analysis = self._validate_and_post_process(llm_result, data)
        
        return analysis
```

#### 3. CLI 命令实现

```python
# cli/commands/market_commands.py

class MarketGetAnalysisDataCommand(Command):
    """获取市场分析数据（不调用 LLM）"""
    
    def get_name(self) -> str:
        return "market.get_analysis_data"
    
    def get_description(self) -> str:
        return "获取结构化的市场数据，供 AI Agent 分析使用"
    
    def get_parameters(self) -> List[Parameter]:
        return [
            Parameter("market", str, True, "市场类型"),
            Parameter("symbol", str, True, "交易对"),
            Parameter("timeframe", str, False, "时间周期", "1D"),
            Parameter("include_macro", bool, False, "包含宏观数据", True),
            Parameter("include_news", bool, False, "包含新闻", True)
        ]
    
    def execute(self, market: str, symbol: str, **kwargs) -> Dict:
        service = MarketDataService()
        data = service.get_analysis_data(
            market=market,
            symbol=symbol,
            timeframe=kwargs.get('timeframe', '1D'),
            include_macro=kwargs.get('include_macro', True),
            include_news=kwargs.get('include_news', True)
        )
        
        # 输出 JSON（供 AI Agent 解析）
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data


# cli/commands/ai_commands.py

class AIAnalyzeCommand(Command):
    """AI 市场分析（调用 LLM）"""
    
    def get_name(self) -> str:
        return "ai.analyze"
    
    def get_description(self) -> str:
        return "使用 AI 分析市场并生成交易建议"
    
    def get_parameters(self) -> List[Parameter]:
        return [
            Parameter("market", str, True, "市场类型"),
            Parameter("symbol", str, True, "交易对"),
            Parameter("language", str, False, "语言", "en-US"),
            Parameter("model", str, False, "LLM 模型"),
            Parameter("timeframe", str, False, "时间周期", "1D")
        ]
    
    def execute(self, market: str, symbol: str, **kwargs) -> Dict:
        service = AIAnalysisService()
        result = service.analyze(
            market=market,
            symbol=symbol,
            language=kwargs.get('language', 'en-US'),
            model=kwargs.get('model'),
            timeframe=kwargs.get('timeframe', '1D')
        )
        
        # 格式化输出（人类可读）
        self._print_analysis(result)
        
        # 也输出 JSON（供 AI Agent 解析）
        print("\n" + "="*60)
        print("JSON Output:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        return result
```

---

### AI Agent 使用场景

#### 场景 1：快速分析（使用 quantsys-v2 的 AI）

**适用情况**：
- 用户要求快速给出交易建议
- 不需要深度定制分析
- 标准的技术+基本面+新闻分析

**AI Agent 工作流**：
```python
# 用户：帮我分析一下比特币现在能不能买

# AI Agent 内部逻辑
result = execute_cli("ai.analyze --market Crypto --symbol BTC/USDT --language zh-CN")

# AI Agent 回复用户
response = f"""
根据 AI 分析，当前比特币：

**决策**: {result['decision']} (置信度: {result['confidence']}%)

**分析摘要**:
{result['summary']}

**交易建议**:
- 入场价: ${result['entry_price']}
- 止损价: ${result['stop_loss']}
- 止盈价: ${result['take_profit']}
- 建议仓位: {result['position_size_pct']}%

**关键原因**:
{format_list(result['key_reasons'])}

**风险提示**:
{format_list(result['risks'])}

你觉得这个建议如何？需要我进一步分析吗？
"""
```

---

#### 场景 2：深度分析（AI Agent 自己分析）

**适用情况**：
- 用户有特殊分析需求
- 需要结合对话上下文
- 需要定制化的分析逻辑

**AI Agent 工作流**：
```python
# 用户：我想做网格交易，帮我分析比特币的波动率和支撑阻力位

# AI Agent 内部逻辑
data = execute_cli("market.get_analysis_data --market Crypto --symbol BTC/USDT")

# AI Agent 自己分析（利用自己的能力）
analysis = f"""
基于你的网格交易需求，我分析了比特币的数据：

**当前价格**: ${data['price']['current']}

**波动率分析**:
- ATR (14日): ${data['indicators']['volatility']['atr']}
- 波动率: {data['indicators']['volatility']['pct']}%
- 波动水平: {data['indicators']['volatility']['level']}

根据波动率，建议网格间距设置为 {calculate_grid_spacing(data)}

**支撑阻力位**:
- 主要支撑: ${data['indicators']['levels']['support']}
- 主要阻力: ${data['indicators']['levels']['resistance']}
- 枢轴点: ${data['indicators']['levels']['pivot']}

**网格交易建议**:
- 网格区间: ${data['indicators']['levels']['support']} - ${data['indicators']['levels']['resistance']}
- 网格数量: {calculate_grid_count(data)}
- 单网格间距: {calculate_grid_spacing(data)}
- 建议总仓位: {calculate_position_size(data)}%

**风险提示**:
{analyze_grid_risks(data)}

这个网格策略符合你的预期吗？
"""
```

---

#### 场景 3：辅助决策（结合两者）

**适用情况**：
- 用户需要多角度验证
- AI Agent 想要第二意见
- 复杂决策需要多方参考

**AI Agent 工作流**：
```python
# 用户：我在考虑是否要买入比特币，帮我全面分析一下

# AI Agent 内部逻辑

# 1. 获取 quantsys-v2 的 AI 建议
ai_suggestion = execute_cli("ai.analyze --market Crypto --symbol BTC/USDT --language zh-CN")

# 2. 获取原始数据
raw_data = execute_cli("market.get_analysis_data --market Crypto --symbol BTC/USDT")

# 3. AI Agent 自己分析
my_analysis = analyze_with_context(raw_data, conversation_history)

# 4. 综合判断
final_decision = f"""
我从多个角度分析了比特币：

## 1. AI 量化分析（quantsys-v2）

{ai_suggestion['summary']}

- 决策: {ai_suggestion['decision']}
- 置信度: {ai_suggestion['confidence']}%
- 建议入场: ${ai_suggestion['entry_price']}

## 2. 我的深度分析

基于当前市场环境和你的风险偏好：

{my_analysis}

## 3. 综合建议

考虑到：
- AI 量化分析给出 {ai_suggestion['decision']} 信号
- 技术面 {raw_data['summary']['technical_bias']}
- 情绪面 {raw_data['summary']['sentiment_bias']}
- 你之前提到的 {extract_user_preference(conversation_history)}

我的最终建议是：{final_recommendation}

理由：
1. {reason_1}
2. {reason_2}
3. {reason_3}

你觉得这个分析如何？
"""
```

---

### 配置和部署

#### 环境变量配置

```bash
# .env

# === quantsys-v2 配置 ===

# 数据库
DATABASE_URL=postgresql://user:pass@localhost/quant_db

# 数据源
BINANCE_API_KEY=xxx
NEWS_API_KEY=xxx

# === AI 分析配置（可选）===

# 是否启用 AI 分析功能
ENABLE_AI_ANALYSIS=true

# LLM 配置
DEFAULT_LLM_MODEL=openai/gpt-4o
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# OpenRouter（可选）
OPENROUTER_API_KEY=sk-or-xxx

# 分析配置
AI_ANALYSIS_TIMEOUT=60
AI_ANALYSIS_MAX_RETRIES=3
```

#### 功能开关

```python
# config/settings.py

class Settings:
    # AI 分析功能开关
    ENABLE_AI_ANALYSIS = os.getenv('ENABLE_AI_ANALYSIS', 'false').lower() == 'true'
    
    # 如果未启用，ai.analyze 命令会返回错误提示
    @staticmethod
    def check_ai_analysis_enabled():
        if not Settings.ENABLE_AI_ANALYSIS:
            raise RuntimeError(
                "AI 分析功能未启用。\n"
                "如需使用，请设置环境变量: ENABLE_AI_ANALYSIS=true\n"
                "并配置 LLM API key: OPENAI_API_KEY=sk-xxx"
            )
```

---

### 成本和性能对比

#### 场景对比

| 场景 | 方法 | LLM 调用 | 成本 | 响应时间 | 灵活性 |
|------|------|----------|------|----------|--------|
| **快速分析** | ai.analyze | 1次 | ~$0.013 | 3-5秒 | 低 |
| **深度分析** | get_analysis_data + AI Agent 自己分析 | 1次（AI Agent） | ~$0.010 | 2-3秒 | 高 |
| **辅助决策** | 两者结合 | 2次 | ~$0.023 | 5-8秒 | 最高 |

#### 成本优化建议

1. **缓存机制**：
   - 市场数据缓存 5 分钟
   - AI 分析结果缓存 10 分钟
   - 相同参数的请求直接返回缓存

2. **批量分析**：
   - 多个标的共享宏观数据
   - 减少重复的数据采集

3. **模型选择**：
   - 简单场景用 GPT-3.5-turbo（成本降低 10x）
   - 复杂场景用 GPT-4o 或 Claude

---

## 实施计划

### Phase 1: 数据层（2周）⭐ 优先级最高

**目标**：实现 MarketDataService 和 market.get_analysis_data 命令

**任务清单**：
- [ ] 创建 MarketDataService
  - [ ] 价格数据采集
  - [ ] K线数据采集
  - [ ] 技术指标计算（带解读）
  - [ ] 加密货币因子采集（带解读）
  - [ ] 宏观数据采集（带解读）
  - [ ] 新闻采集（带情绪分析）
  - [ ] 综合摘要生成（规则引擎）

- [ ] 创建 CLI 命令
  - [ ] market.get_analysis_data 命令
  - [ ] 参数验证
  - [ ] JSON 输出格式

- [ ] 测试
  - [ ] 单元测试（各个数据源）
  - [ ] 集成测试（完整流程）
  - [ ] AI Agent 调用测试

**交付物**：
- `services/market_data_service.py`
- `cli/commands/market_commands.py`
- 测试用例
- 使用文档

**验收标准**：
```bash
# 能够成功执行并返回完整数据
python cli/main.py market.get_analysis_data --market Crypto --symbol BTC/USDT

# 输出包含所有必需字段
# AI Agent 能够解析并使用
```

---

### Phase 2: AI 分析层（2周）可选

**目标**：实现 AIAnalysisService 和 ai.analyze 命令

**任务清单**：
- [ ] 创建 LLMService
  - [ ] OpenAI Provider
  - [ ] OpenRouter Provider
  - [ ] 统一接口

- [ ] 创建 AIAnalysisService
  - [ ] 提示词构建
  - [ ] LLM 调用
  - [ ] 结果验证
  - [ ] 后处理

- [ ] 创建 CLI 命令
  - [ ] ai.analyze 命令
  - [ ] 参数验证
  - [ ] 格式化输出

- [ ] 测试
  - [ ] LLM 调用测试
  - [ ] 提示词测试
  - [ ] 端到端测试

**交付物**：
- `services/llm_service.py`
- `services/llm_providers/`
- `services/ai_analysis_service.py`
- `cli/commands/ai_commands.py`
- 测试用例

**验收标准**：
```bash
# 能够成功执行并返回 AI 分析
python cli/main.py ai.analyze --market Crypto --symbol BTC/USDT --language zh-CN

# 输出包含决策、置信度、交易建议
# 价格逻辑正确（BUY: SL < Entry < TP）
```

---

### Phase 3: 优化和集成（1周）

**任务清单**：
- [ ] 性能优化
  - [ ] 数据采集并行化
  - [ ] 缓存机制
  - [ ] 超时处理

- [ ] 错误处理
  - [ ] 数据源失败降级
  - [ ] LLM 调用重试
  - [ ] 友好的错误提示

- [ ] 文档完善
  - [ ] API 文档
  - [ ] 使用示例
  - [ ] 最佳实践

- [ ] AI Agent 集成测试
  - [ ] 快速分析场景
  - [ ] 深度分析场景
  - [ ] 辅助决策场景

---

## 最佳实践

### 1. AI Agent 使用建议

**快速场景**（用户要求快速决策）：
```python
# 直接使用 ai.analyze
result = execute_cli("ai.analyze --market Crypto --symbol BTC/USDT --language zh-CN")
return format_quick_response(result)
```

**深度场景**（用户有特殊需求）：
```python
# 获取数据自己分析
data = execute_cli("market.get_analysis_data --market Crypto --symbol BTC/USDT")
analysis = custom_analysis(data, user_requirements)
return analysis
```

**验证场景**（需要多方验证）：
```python
# 获取 AI 建议作为参考
ai_suggestion = execute_cli("ai.analyze --market Crypto --symbol BTC/USDT")
data = execute_cli("market.get_analysis_data --market Crypto --symbol BTC/USDT")

# 结合自己的判断
final_decision = combine_analysis(ai_suggestion, data, my_analysis)
return final_decision
```

### 2. 数据解读建议

**技术指标解读**：
```python
# quantsys-v2 已经提供了解读
rsi_interpretation = data['indicators']['rsi']['interpretation']
# "RSI 65.2 在中性区域，无明显超买超卖"

# AI Agent 可以直接使用，或者基于此进一步分析
```

**加密货币因子解读**：
```python
# quantsys-v2 提供了综合解读
crypto_interpretation = data['crypto_factors']['interpretation']
# "资金费率正常，未平仓量上升，交易所净流出，整体看涨"

# AI Agent 可以结合价格走势进一步分析
```

### 3. 错误处理

**数据源失败**：
```python
try:
    data = execute_cli("market.get_analysis_data --market Crypto --symbol BTC/USDT")
except DataSourceError as e:
    # 降级处理：使用部分数据
    data = execute_cli("market.get_analysis_data --market Crypto --symbol BTC/USDT --include-news false")
```

**LLM 调用失败**：
```python
try:
    result = execute_cli("ai.analyze --market Crypto --symbol BTC/USDT")
except LLMError as e:
    # 降级：使用数据层 + AI Agent 自己分析
    data = execute_cli("market.get_analysis_data --market Crypto --symbol BTC/USDT")
    result = fallback_analysis(data)
```

---

## 总结

### 推荐架构：混合方案

**核心理念**：
- quantsys-v2 提供**数据层**（必需）和**分析层**（可选）
- AI Agent 根据场景灵活选择使用方式
- 保持架构简单、灵活、可扩展

**关键优势**：
1. ✅ **灵活性**：AI Agent 可以选择快速分析或深度分析
2. ✅ **独立性**：quantsys-v2 可以独立使用（人类用户）
3. ✅ **成本优化**：避免重复调用 LLM
4. ✅ **性能优化**：数据层可以缓存和复用
5. ✅ **可维护性**：职责清晰，易于测试和维护

**实施优先级**：
1. **Phase 1（必需）**：数据层 - 2周
2. **Phase 2（可选）**：AI 分析层 - 2周
3. **Phase 3（优化）**：性能和集成 - 1周

**总时间**：
- 最小实施（仅数据层）：2周
- 完整实施（数据层 + AI 层）：5周

---

## 附录：命令对比

### quantsys-v2 提供的命令

| 命令 | 用途 | LLM 调用 | 适用场景 |
|------|------|----------|---------|
| `market.get_analysis_data` | 获取结构化数据 | 否 | AI Agent 自己分析 |
| `ai.analyze` | 完整 AI 分析 | 是 | 快速获取建议 |

### AI Agent 的使用方式

| 场景 | 使用命令 | 优势 |
|------|---------|------|
| 快速分析 | `ai.analyze` | 简单快速 |
| 深度分析 | `market.get_analysis_data` | 灵活定制 |
| 辅助决策 | 两者结合 | 多方验证 |

---

**文档版本**: 1.0  
**最后更新**: 2026-05-22  
**作者**: AI Assistant
