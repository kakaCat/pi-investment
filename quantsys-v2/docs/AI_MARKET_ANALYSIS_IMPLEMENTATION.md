# AI 市场分析实现指南

**基于 QuantDinger 的实现分析**

---

## 📋 目录

1. [概述](#概述)
2. [核心架构](#核心架构)
3. [数据采集层](#数据采集层)
4. [提示词工程](#提示词工程)
5. [LLM 集成](#llm-集成)
6. [实施方案](#实施方案)

---

## 概述

AI 市场分析是 QuantDinger 的核心功能之一，通过 LLM 分析市场数据、技术指标、新闻、宏观经济等多维度信息，生成可执行的交易建议。

### 核心价值

- **多维度分析**：技术指标 + 基本面 + 新闻情绪 + 宏观经济
- **结构化输出**：JSON 格式，包含决策、置信度、入场/止损/止盈价格
- **地缘政治检测**：自动识别战争、冲突等重大事件
- **历史记忆**：存储分析历史，识别相似市场模式
- **多时间框架**：支持 1H/4H/1D 等多周期分析

### 技术特点

- **单次 LLM 调用**：避免多轮对话的延迟和成本
- **强约束提示词**：确保输出格式和质量
- **客观评分系统**：基于规则计算技术/基本面/情绪得分
- **安全边界**：价格建议限制在当前价格 ±10% 范围内

---

## 核心架构

### 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                               │
│  POST /api/fast-analysis/analyze                            │
│  - 参数验证、权限检查、计费扣费                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer                              │
│  FastAnalysisService                                         │
│  - 数据采集 (MarketDataCollector)                            │
│  - 提示词构建 (Prompt Engineering)                           │
│  - LLM 调用 (LLMService)                                     │
│  - 结果验证和后处理                                           │
│  - 历史记忆存储 (AnalysisMemory)                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  - MarketDataCollector: 统一数据采集                         │
│  - LLMService: 多 LLM 支持 (OpenAI/OpenRouter/Custom)       │
│  - AnalysisMemory: 分析历史存储和检索                        │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

#### 1. FastAnalysisService

**职责**：
- 协调整个分析流程
- 数据采集和预处理
- 提示词构建
- LLM 调用和结果解析
- 历史记忆管理

**关键方法**：
```python
class FastAnalysisService:
    def analyze(self, market, symbol, language, model, timeframe, user_id):
        """主分析方法"""
        # 1. 数据采集
        data = self._collect_market_data(market, symbol, timeframe)
        
        # 2. 构建提示词
        system_prompt, user_prompt = self._build_analysis_prompt(data, language)
        
        # 3. LLM 调用
        llm_result = self.llm_service.chat(system_prompt, user_prompt, model)
        
        # 4. 结果验证
        result = self._validate_and_post_process(llm_result, data)
        
        # 5. 存储历史
        self._store_analysis_memory(result, user_id)
        
        return result
```

#### 2. MarketDataCollector

**职责**：统一采集所有市场数据

**数据层次**：
```python
{
    "price": {
        "price": 43250.5,
        "changePercent": 2.3,
        "volume": 1234567890
    },
    "indicators": {
        "rsi": {"value": 65, "signal": "neutral"},
        "macd": {"signal": "bullish", "trend": "golden_cross"},
        "moving_averages": {"trend": "uptrend"},
        "levels": {"support": 42000, "resistance": 45000}
    },
    "fundamental": {
        "pe_ratio": 25.3,
        "market_cap": 850000000000,
        "financial_statements": {...}
    },
    "macro": {
        "DXY": {"price": 103.5, "changePercent": 0.2},
        "VIX": {"price": 18.5},
        "TNX": {"price": 4.25}
    },
    "news": [
        {"title": "...", "sentiment": "positive", "date": "2024-01-01"}
    ],
    "crypto_factors": {
        "funding_rate": 0.01,
        "open_interest": 12000000000,
        "long_short_ratio": 1.2
    }
}
```

#### 3. LLMService

**职责**：多 LLM 提供商抽象层

**支持的模型**：
- OpenAI: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
- OpenRouter: anthropic/claude-3.5-sonnet, google/gemini-pro
- Custom: 自定义 API 端点

**关键方法**：
```python
class LLMService:
    def chat(self, system_prompt, user_prompt, model=None):
        """统一的聊天接口"""
        provider = self._get_provider(model)
        return provider.chat(system_prompt, user_prompt)
    
    def get_default_model(self):
        """获取默认模型"""
        return os.getenv('DEFAULT_LLM_MODEL', 'openai/gpt-4o')
```

#### 4. AnalysisMemory

**职责**：分析历史存储和检索

**功能**：
- 存储每次分析结果
- 根据技术指标相似度检索历史模式
- 追踪预测准确率
- 用户反馈收集

---

## 数据采集层

### 数据源整合

QuantDinger 使用统一的 `MarketDataCollector` 采集所有数据：

```python
class MarketDataCollector:
    def collect_all(self, market, symbol, timeframe, 
                    include_macro=True, include_news=True, timeout=45):
        """采集所有市场数据"""
        result = {}
        
        # 1. 核心价格数据
        result['price'] = self._fetch_price(market, symbol)
        result['klines'] = self._fetch_klines(market, symbol, timeframe)
        
        # 2. 技术指标计算
        result['indicators'] = self._calculate_indicators(result['klines'])
        
        # 3. 基本面数据 (股票)
        if market == 'USStock':
            result['fundamental'] = self._fetch_fundamental(symbol)
            result['company'] = self._fetch_company_info(symbol)
        
        # 4. 加密货币特有数据
        if market == 'Crypto':
            result['crypto_factors'] = self._fetch_crypto_factors(symbol)
        
        # 5. 宏观经济数据
        if include_macro:
            result['macro'] = self._fetch_macro_data(market)
        
        # 6. 新闻数据
        if include_news:
            result['news'] = self._fetch_news(market, symbol)
        
        return result
```

### 技术指标计算

**计算的指标**：
- RSI (14): 超买/超卖信号
- MACD: 趋势和动量
- 移动平均线 (MA5/MA10/MA20): 趋势方向
- 支撑/阻力位: 关键价格水平
- ATR: 波动率
- 布林带: 价格通道

**信号解读**（规则引擎，无需 LLM）：
```python
def _calculate_indicators(self, klines):
    # RSI 解读
    if rsi < 30:
        rsi_signal = "oversold"  # 超卖
        rsi_action = "potential_buy"
    elif rsi > 70:
        rsi_signal = "overbought"  # 超买
        rsi_action = "potential_sell"
    else:
        rsi_signal = "neutral"
    
    # MACD 解读
    if macd > signal_line and macd_hist > 0:
        macd_signal = "bullish"  # 看涨
    elif macd < signal_line and macd_hist < 0:
        macd_signal = "bearish"  # 看跌
    
    # 趋势判断
    if price > ma5 > ma10 > ma20:
        trend = "strong_uptrend"  # 强上升趋势
    elif price < ma5 < ma10 < ma20:
        trend = "strong_downtrend"  # 强下降趋势
    
    return {
        "rsi": {"value": rsi, "signal": rsi_signal, "action": rsi_action},
        "macd": {"signal": macd_signal, "trend": macd_trend},
        "moving_averages": {"trend": trend},
        "levels": {"support": support, "resistance": resistance}
    }
```

### 宏观数据采集

**采集的宏观指标**：
- **DXY (美元指数)**: 影响加密货币和大宗商品
- **VIX (恐慌指数)**: 市场波动率和风险偏好
- **TNX (10年期美债收益率)**: 利率环境
- **GOLD (黄金)**: 避险情绪
- **SPY (标普500)**: 整体市场情绪
- **BTC (比特币)**: 风险资产指标

**影响分析**：
```python
def _format_macro_summary(self, macro, market):
    # 美元指数对加密货币的影响
    if market == 'Crypto' and 'DXY' in macro:
        if dxy_change > 0:
            impact = "利空加密货币"  # 美元走强，加密货币承压
        else:
            impact = "利好加密货币"  # 美元走弱，加密货币受益
    
    # VIX 恐慌指数
    if vix > 30:
        level = "极度恐慌"  # 高风险环境
    elif vix > 20:
        level = "较高恐慌"
    else:
        level = "正常"
    
    # 利率环境
    if tnx > 4.5:
        impact = "高利率环境，对估值不利"
```

### 新闻采集和情绪分析

**新闻来源**：
- 结构化 API（无需深度阅读）
- 标题 + 摘要 + 情绪标签
- 时间戳和来源

**地缘政治检测**（关键特性）：
```python
# 严重级别关键词
_GEO_SEVERE_PATTERNS = [
    r"\b(?:war|invasion|airstrike|military attack)\b",
    r"\b(?:declare war|martial law|coup)\b",
    r"\b(?:terrorist attack)\b"
]

# 中等级别关键词
_GEO_MODERATE_PATTERNS = [
    r"\bgeopolitical\b",
    r"\b(?:armed|military) conflict\b",
    r"\bsanctions? (?:on|against)\b",
    r"\bnuclear (?:threat|strike)\b"
]

def _geopolitical_match_level(text):
    """检测地缘政治风险级别"""
    for pattern in _GEO_SEVERE_PATTERNS:
        if pattern.search(text):
            return "severe", pattern  # 严重：战争、入侵
    
    for pattern in _GEO_MODERATE_PATTERNS:
        if pattern.search(text):
            return "moderate", pattern  # 中等：制裁、冲突
    
    return "none", None

# 情绪得分惩罚
def _geopolitical_sentiment_penalty(level):
    if level == "severe":
        return -42  # 严重事件：大幅降低情绪得分
    if level == "moderate":
        return -18  # 中等事件：适度降低
    return 0
```

### 加密货币特有数据

**采集的指标**：
- **资金费率 (Funding Rate)**: 多空力量对比
- **未平仓量 (Open Interest)**: 市场参与度
- **多空比 (Long/Short Ratio)**: 市场情绪
- **交易所净流 (Exchange Netflow)**: 资金流向
- **稳定币净流 (Stablecoin Netflow)**: 购买力

**信号解读**：
```python
def _analyze_crypto_factors(self, factors):
    signals = {}
    
    # 资金费率分析
    funding_rate = factors.get('funding_rate', 0)
    if funding_rate > 0.05:
        signals['derivatives_bias'] = 'bullish_crowded'  # 多头拥挤
        signals['squeeze_risk'] = 'high'  # 挤仓风险高
    elif funding_rate < -0.05:
        signals['derivatives_bias'] = 'bearish_crowded'
    
    # 未平仓量分析
    oi_change = factors.get('open_interest_change_24h', 0)
    if oi_change > 10 and funding_rate > 0:
        signals['derivatives_bias'] = 'bullish_momentum'  # 多头动能
    
    # 资金流分析
    exchange_netflow = factors.get('exchange_netflow', 0)
    if exchange_netflow < 0:
        signals['flow_bias'] = 'bullish'  # 流出交易所，看涨
    elif exchange_netflow > 0:
        signals['flow_bias'] = 'bearish'  # 流入交易所，看跌
    
    return signals
```

---

## 提示词工程

### System Prompt（系统提示词）

**核心约束**：

```python
system_prompt = f"""You are QuantDinger's Senior Financial Analyst with 20+ years of experience. 
You are CONSERVATIVE and OBJECTIVE. Your analysis must be based on DATA, not speculation.

{language_instruction}  # 强制语言约束

🎯 CRITICAL DECISION RULES (MUST FOLLOW):

1. **Market Context**: 
   - 支持做多(BUY)和做空(SELL)
   - SELL 是有效的交易机会，不只是风险警告

2. **Multi-Factor Analysis** (考虑所有因素):
   - 技术指标 (RSI, MACD, MA)
   - 宏观环境 (DXY, VIX, 利率, 地缘政治)
   - 突发新闻和事件
   - 基本面数据
   - 市场情绪

3. **Decision Priority** (因素冲突时的优先级):
   - 重大宏观事件 > 技术指标
   - 突发新闻 > 短期技术
   - 技术指标 > 一般新闻情绪
   - 基本面 > 短期价格波动

4. **Balance Your Decisions** (给出 SELL 信号):
   - BUY: RSI < 40, 看涨 MACD, 上升趋势, 或强催化剂
   - SELL: RSI > 60, 看跌 MACD, 下降趋势, 或重大负面事件
   - HOLD: 信号真正混合或不清晰时

5. **Confidence Thresholds**:
   - BUY 需要 confidence >= 60 且有技术或基本面支持
   - SELL 需要 confidence >= 60 且有技术支持或负面事件
   - HOLD 仅当 confidence < 60 且信号不清晰

6. **Consider Macro Impact**:
   - 强美元 (DXY↑) → 加密货币/大宗商品看跌
   - 高 VIX (>30) → 恐慌，避免 BUY
   - 利率上升 → 成长股看跌
   - 地缘政治紧张 → 风险规避

7. **Crypto Market Structure Override** (加密货币特殊规则):
   - 不要依赖股票式估值逻辑
   - 优先考虑衍生品定位、资金费率、未平仓量、多空比、资金流
   - 正资金费率 + 上升 OI = 看涨动能（但极端值可能是拥挤多头）
   - 交易所净流出 = 看涨；净流入 = 看跌
   - 稳定币净流入 = 新购买力进入市场

⚠️ CRITICAL PRICE RULES:
1. Current price: ${current_price}
2. BUY: stop_loss < current_price < take_profit
3. SELL (short): take_profit < current_price < stop_loss
4. 所有价格必须在当前价格 ±10% 范围内

📐 TECHNICAL LEVELS (Pre-calculated):
- Support: ${support} | Resistance: ${resistance}
- ATR: ${atr} | Volatility: {volatility_pct}%
- Suggested Stop Loss: ${suggested_stop_loss}
- Suggested Take Profit: ${suggested_take_profit}
- Risk/Reward Ratio: {risk_reward_ratio}

📊 OUTPUT FORMAT (JSON only):
{{
  "decision": "BUY" | "SELL" | "HOLD",
  "confidence": 0-100,
  "summary": "2-3句执行摘要",
  "analysis": {{
    "technical": "技术分析详情",
    "fundamental": "基本面评估",
    "sentiment": "市场情绪分析"
  }},
  "entry_price": number,
  "stop_loss": number,
  "take_profit": number,
  "position_size_pct": 1-100,
  "timeframe": "short" | "medium" | "long",
  "key_reasons": ["原因1", "原因2", "原因3"],
  "risks": ["风险1", "风险2"],
  "technical_score": 0-100,
  "fundamental_score": 0-100,
  "sentiment_score": 0-100
}}

📊 OBJECTIVE SCORING SYSTEM:
- Score >= +20: 看涨 → BUY
- Score <= -20: 看跌 → SELL
- Score -20 to +20: 中性 → HOLD
- 地缘政治事件在情绪得分中权重很高
- 宏观因素权重也很高
"""
```

### User Prompt（用户提示词）

**数据呈现**：

```python
user_prompt = f"""Analyze {symbol} in {market} market.

📊 REAL-TIME DATA:
- Current Price: ${current_price}
- 24h Change: {change_24h}%
- Support: ${support} | Resistance: ${resistance}

📈 TECHNICAL INDICATORS:
- RSI(14): {rsi_value} ({rsi_signal})
- MACD: {macd_signal} ({macd_trend})
- MA Trend: {ma_trend}
- Volatility: {volatility_level} ({volatility_pct}%)
- Trend: {trend}
- Price Position (20d): {price_position}%

🪙 CRYPTO MARKET STRUCTURE (if crypto):
- 24h Volume: {volume_24h}
- Funding Rate: {funding_rate}%
- Open Interest: {open_interest}
- Long/Short Ratio: {long_short_ratio}
- Exchange Netflow: {exchange_netflow}
- Derivatives Bias: {derivatives_bias}
- Squeeze Risk: {squeeze_risk}

🌐 MACRO ENVIRONMENT:
- USD Index (DXY): {dxy_price} ({dxy_change}%)
- VIX: {vix_value} - {vix_level}
- 10Y Treasury: {tnx_rate}%
- Gold: ${gold_price}
- S&P 500: ${spy_price}

📰 MARKET NEWS ({news_count} items):
- [positive] 标题1 (2024-01-01)
- [negative] 标题2 (2024-01-02)
- [neutral] 标题3 (2024-01-03)

💼 FUNDAMENTALS (if stock):
- P/E Ratio: {pe_ratio}
- Market Cap: {market_cap}
- ROE: {roe}%
- Revenue Growth: {revenue_growth}%
- Debt/Equity: {debt_to_equity}

📚 HISTORICAL PATTERNS (similar conditions):
- Decision: BUY at $42000 (Outcome: Correct, Return: +5.2%)
- Decision: SELL at $45000 (Outcome: Incorrect, Return: -2.1%)

IMPORTANT:
1. **CRITICAL**: 检查新闻中的地缘政治事件（战争、冲突、军事行动）
2. 考虑宏观环境（DXY, VIX, 利率, 地缘政治）
3. 注意突发新闻和国际事件
4. 对于加密货币，解释衍生品和资金流数据是否确认价格走势
5. 如果看到战争、冲突等新闻，必须在分析中提及并调整建议
"""
```

### 决策指导（动态生成）

根据技术指标动态生成决策建议：

```python
def _build_decision_guidance(self, rsi, macd_signal, ma_trend, change_24h):
    """根据技术指标生成决策指导"""
    guidance = []
    
    # RSI 指导
    if rsi < 30:
        guidance.append("⚠️ RSI < 30 (超卖) → 考虑 BUY 机会")
    elif rsi > 70:
        guidance.append("⚠️ RSI > 70 (超买) → 考虑 SELL 机会")
    
    # MACD 指导
    if macd_signal == "bullish":
        guidance.append("✅ MACD 看涨 → 支持 BUY")
    elif macd_signal == "bearish":
        guidance.append("❌ MACD 看跌 → 支持 SELL")
    
    # 趋势指导
    if ma_trend in ["strong_uptrend", "uptrend"]:
        guidance.append("📈 上升趋势 → 倾向 BUY")
    elif ma_trend in ["strong_downtrend", "downtrend"]:
        guidance.append("📉 下降趋势 → 倾向 SELL")
    
    # 价格动量
    if change_24h > 5:
        guidance.append("🚀 强劲上涨 (+{change_24h}%) → 注意超买风险")
    elif change_24h < -5:
        guidance.append("💥 大幅下跌 ({change_24h}%) → 注意超卖反弹")
    
    return "\n".join(guidance) if guidance else "信号混合，需综合判断"
```

### 语言强制约束

**多语言支持**：

```python
lang_map = {
    'zh-CN': '⚠️ 重要：你必须用简体中文回答所有内容，包括summary、key_reasons、risks等所有文本字段。不要使用英文。',
    'zh-TW': '⚠️ 重要：你必須用繁體中文回答所有內容。',
    'en-US': '⚠️ IMPORTANT: You MUST answer ALL content in English. Do NOT use Chinese.',
    'ja-JP': '⚠️ 重要：すべての内容を日本語で回答してください。'
}
```

---

## LLM 集成

### LLMService 架构

**多提供商支持**：

```python
class LLMService:
    def __init__(self):
        self.providers = {
            'openai': OpenAIProvider(),
            'openrouter': OpenRouterProvider(),
            'custom': CustomProvider()
        }
    
    def chat(self, system_prompt, user_prompt, model=None):
        """统一聊天接口"""
        if not model:
            model = self.get_default_model()
        
        provider_name = self._parse_provider(model)
        provider = self.providers[provider_name]
        
        return provider.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=0.3,  # 低温度，更确定性
            response_format={"type": "json_object"}  # 强制 JSON 输出
        )
    
    def _parse_provider(self, model):
        """从模型名解析提供商"""
        if model.startswith('openai/'):
            return 'openai'
        elif model.startswith('anthropic/') or model.startswith('google/'):
            return 'openrouter'
        else:
            return 'custom'
```

### OpenAI Provider

```python
class OpenAIProvider:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
    
    def chat(self, system_prompt, user_prompt, model, temperature=0.3, **kwargs):
        """OpenAI 聊天接口"""
        response = self.client.chat.completions.create(
            model=model.replace('openai/', ''),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            response_format={"type": "json_object"},  # JSON mode
            timeout=60
        )
        
        return {
            'content': response.choices[0].message.content,
            'model': response.model,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        }
```

### OpenRouter Provider

```python
class OpenRouterProvider:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = 'https://openrouter.ai/api/v1'
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def chat(self, system_prompt, user_prompt, model, temperature=0.3, **kwargs):
        """OpenRouter 聊天接口（支持多模型）"""
        response = self.client.chat.completions.create(
            model=model,  # 例如: anthropic/claude-3.5-sonnet
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            extra_headers={
                "HTTP-Referer": "https://quantdinger.com",
                "X-Title": "QuantDinger AI Analysis"
            }
        )
        
        return {
            'content': response.choices[0].message.content,
            'model': response.model,
            'usage': response.usage.dict() if response.usage else {}
        }
```

### 结果验证和后处理

```python
def _validate_and_post_process(self, llm_result, market_data):
    """验证 LLM 输出并后处理"""
    try:
        # 1. 解析 JSON
        analysis = json.loads(llm_result['content'])
        
        # 2. 验证必需字段
        required_fields = ['decision', 'confidence', 'summary', 'entry_price', 
                          'stop_loss', 'take_profit']
        for field in required_fields:
            if field not in analysis:
                raise ValueError(f"Missing required field: {field}")
        
        # 3. 验证决策
        if analysis['decision'] not in ['BUY', 'SELL', 'HOLD']:
            raise ValueError(f"Invalid decision: {analysis['decision']}")
        
        # 4. 验证价格逻辑
        current_price = market_data['price']['price']
        entry = analysis['entry_price']
        stop_loss = analysis['stop_loss']
        take_profit = analysis['take_profit']
        
        if analysis['decision'] == 'BUY':
            # BUY: stop_loss < entry < take_profit
            if not (stop_loss < entry < take_profit):
                logger.warning(f"Invalid BUY prices: SL={stop_loss}, Entry={entry}, TP={take_profit}")
                # 自动修正
                analysis['stop_loss'] = entry * 0.97
                analysis['take_profit'] = entry * 1.05
        
        elif analysis['decision'] == 'SELL':
            # SELL: take_profit < entry < stop_loss
            if not (take_profit < entry < stop_loss):
                logger.warning(f"Invalid SELL prices: TP={take_profit}, Entry={entry}, SL={stop_loss}")
                # 自动修正
                analysis['take_profit'] = entry * 0.95
                analysis['stop_loss'] = entry * 1.03
        
        # 5. 验证价格范围（±10%）
        price_lower = current_price * 0.90
        price_upper = current_price * 1.10
        
        for price_field in ['entry_price', 'stop_loss', 'take_profit']:
            price = analysis[price_field]
            if price < price_lower or price > price_upper:
                logger.warning(f"{price_field} out of range: {price}")
                # 限制在范围内
                analysis[price_field] = max(price_lower, min(price_upper, price))
        
        # 6. 计算客观评分
        objective_scores = self._calculate_objective_scores(market_data)
        analysis['objective_score'] = objective_scores['total']
        analysis['objective_breakdown'] = objective_scores
        
        # 7. 添加元数据
        analysis['model'] = llm_result.get('model')
        analysis['usage'] = llm_result.get('usage')
        analysis['timestamp'] = time.time()
        
        return analysis
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return {"error": "Invalid JSON response from LLM"}
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {"error": str(e)}
```

### 客观评分系统

```python
def _calculate_objective_scores(self, data):
    """计算客观评分（基于规则）"""
    scores = {
        'technical': 0,
        'fundamental': 0,
        'sentiment': 0,
        'macro': 0
    }
    
    # 1. 技术评分 (-100 to +100)
    indicators = data.get('indicators', {})
    
    # RSI
    rsi = indicators.get('rsi', {}).get('value', 50)
    if rsi < 30:
        scores['technical'] += 30  # 超卖，看涨
    elif rsi > 70:
        scores['technical'] -= 30  # 超买，看跌
    
    # MACD
    macd_signal = indicators.get('macd', {}).get('signal', 'neutral')
    if macd_signal == 'bullish':
        scores['technical'] += 25
    elif macd_signal == 'bearish':
        scores['technical'] -= 25
    
    # 趋势
    trend = indicators.get('moving_averages', {}).get('trend', 'sideways')
    if trend in ['strong_uptrend', 'uptrend']:
        scores['technical'] += 20
    elif trend in ['strong_downtrend', 'downtrend']:
        scores['technical'] -= 20
    
    # 2. 基本面评分 (-100 to +100)
    fundamental = data.get('fundamental', {})
    
    # P/E 比率
    pe = fundamental.get('pe_ratio')
    if pe and pe < 15:
        scores['fundamental'] += 20  # 低估
    elif pe and pe > 30:
        scores['fundamental'] -= 20  # 高估
    
    # ROE
    roe = fundamental.get('roe')
    if roe and roe > 15:
        scores['fundamental'] += 15  # 高回报
    
    # 3. 情绪评分 (-100 to +100)
    news = data.get('news', [])
    
    # 新闻情绪
    positive_count = sum(1 for n in news if n.get('sentiment') == 'positive')
    negative_count = sum(1 for n in news if n.get('sentiment') == 'negative')
    scores['sentiment'] = (positive_count - negative_count) * 10
    
    # 地缘政治惩罚
    for news_item in news:
        text = f"{news_item.get('title', '')} {news_item.get('summary', '')}"
        geo_level, _ = _geopolitical_match_level(text)
        penalty = _geopolitical_sentiment_penalty_delta(geo_level)
        scores['sentiment'] += penalty  # -42 for severe, -18 for moderate
    
    # 4. 宏观评分 (-100 to +100)
    macro = data.get('macro', {})
    
    # VIX
    vix = macro.get('VIX', {}).get('price', 15)
    if vix > 30:
        scores['macro'] -= 30  # 高恐慌
    elif vix < 15:
        scores['macro'] += 15  # 低波动
    
    # DXY (对加密货币)
    if data.get('market') == 'Crypto':
        dxy_change = macro.get('DXY', {}).get('changePercent', 0)
        scores['macro'] -= dxy_change * 5  # 美元走强，加密货币承压
    
    # 总分
    scores['total'] = sum(scores.values())
    
    return scores
```

---

## 实施方案

### 在 quantsys-v2 中实施 AI 分析

#### Phase 1: 基础架构（1周）

**1.1 创建 LLM 服务抽象层**

```
services/
├── llm_service.py              # LLM 服务主类
└── llm_providers/
    ├── __init__.py
    ├── base.py                 # Provider 基类
    ├── openai_provider.py      # OpenAI 实现
    ├── openrouter_provider.py  # OpenRouter 实现
    └── custom_provider.py      # 自定义 API
```

**实现要点**：
```python
# services/llm_service.py
class LLMService:
    def __init__(self):
        self.providers = self._load_providers()
        self.default_model = os.getenv('DEFAULT_LLM_MODEL', 'openai/gpt-4o')
    
    def chat(self, system_prompt: str, user_prompt: str, 
             model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """统一聊天接口"""
        model = model or self.default_model
        provider = self._get_provider(model)
        return provider.chat(system_prompt, user_prompt, model, **kwargs)
    
    def get_default_model(self) -> str:
        return self.default_model
```

**1.2 创建市场数据采集器**

```
services/
└── market_data_collector.py    # 统一数据采集
```

**实现要点**：
```python
class MarketDataCollector:
    def __init__(self):
        self.kline_repo = KlineRepository()
        self.stock_repo = StockRepository()
        # ... 其他 repositories
    
    def collect_all(self, market: str, symbol: str, timeframe: str,
                    include_macro: bool = True, 
                    include_news: bool = True) -> Dict[str, Any]:
        """采集所有市场数据"""
        result = {}
        
        # 1. 价格和K线
        result['price'] = self._fetch_price(market, symbol)
        result['klines'] = self._fetch_klines(market, symbol, timeframe)
        
        # 2. 技术指标
        result['indicators'] = self._calculate_indicators(result['klines'])
        
        # 3. 基本面（股票）
        if market == 'USStock':
            result['fundamental'] = self._fetch_fundamental(symbol)
        
        # 4. 加密货币因子
        if market == 'Crypto':
            result['crypto_factors'] = self._fetch_crypto_factors(symbol)
        
        # 5. 宏观数据
        if include_macro:
            result['macro'] = self._fetch_macro_data(market)
        
        # 6. 新闻
        if include_news:
            result['news'] = self._fetch_news(market, symbol)
        
        return result
```

#### Phase 2: AI 分析服务（2周）

**2.1 创建 AI 分析服务**

```
services/
└── ai_analysis_service.py      # AI 分析主服务
```

**核心方法**：
```python
class AIAnalysisService:
    def __init__(self):
        self.llm_service = LLMService()
        self.data_collector = MarketDataCollector()
        self.memory = AnalysisMemory()
    
    def analyze(self, market: str, symbol: str, 
                language: str = 'en-US',
                model: Optional[str] = None,
                timeframe: str = '1D',
                user_id: Optional[int] = None) -> Dict[str, Any]:
        """执行 AI 市场分析"""
        
        # 1. 数据采集
        data = self.data_collector.collect_all(
            market=market,
            symbol=symbol,
            timeframe=timeframe
        )
        
        # 2. 构建提示词
        system_prompt, user_prompt = self._build_analysis_prompt(
            data=data,
            language=language
        )
        
        # 3. LLM 调用
        llm_result = self.llm_service.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        # 4. 验证和后处理
        analysis = self._validate_and_post_process(llm_result, data)
        
        # 5. 存储历史
        if user_id:
            self._store_analysis_memory(analysis, user_id)
        
        return analysis
    
    def _build_analysis_prompt(self, data: Dict, language: str) -> Tuple[str, str]:
        """构建提示词（参考 QuantDinger 实现）"""
        # ... 详见前面的提示词工程章节
        pass
    
    def _validate_and_post_process(self, llm_result: Dict, data: Dict) -> Dict:
        """验证 LLM 输出"""
        # ... 详见前面的验证章节
        pass
```

**2.2 创建分析记忆系统**

```
services/
└── analysis_memory.py          # 分析历史存储
```

```python
class AnalysisMemory:
    def __init__(self):
        self.db = get_database_connection()
    
    def store(self, analysis: Dict, user_id: int) -> int:
        """存储分析结果"""
        query = """
            INSERT INTO ai_analysis_history 
            (user_id, market, symbol, decision, confidence, 
             entry_price, stop_loss, take_profit, 
             analysis_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        # ... 执行插入
    
    def get_similar_patterns(self, market: str, symbol: str, 
                            indicators: Dict, limit: int = 3) -> List[Dict]:
        """检索相似的历史模式"""
        # 基于 RSI、MACD、趋势等指标的相似度
        query = """
            SELECT * FROM ai_analysis_history
            WHERE market = %s AND symbol = %s
            AND ABS(indicators->>'rsi' - %s) < 10
            ORDER BY created_at DESC
            LIMIT %s
        """
        # ... 执行查询
```

#### Phase 3: CLI 和 API 集成（1周）

**3.1 CLI 命令**

```
cli/commands/
└── ai_commands.py              # AI 分析命令
```

```python
class AIAnalyzeCommand(Command):
    """AI 市场分析命令"""
    
    def get_name(self) -> str:
        return "ai.analyze"
    
    def get_description(self) -> str:
        return "使用 AI 分析市场并生成交易建议"
    
    def get_parameters(self) -> List[Parameter]:
        return [
            Parameter("market", str, True, "市场类型 (Crypto/USStock)"),
            Parameter("symbol", str, True, "交易对或股票代码"),
            Parameter("language", str, False, "语言 (zh-CN/en-US)", "en-US"),
            Parameter("model", str, False, "LLM 模型"),
            Parameter("timeframe", str, False, "时间周期", "1D")
        ]
    
    def execute(self, market: str, symbol: str, 
                language: str = "en-US",
                model: Optional[str] = None,
                timeframe: str = "1D") -> Dict[str, Any]:
        """执行 AI 分析"""
        service = AIAnalysisService()
        result = service.analyze(
            market=market,
            symbol=symbol,
            language=language,
            model=model,
            timeframe=timeframe
        )
        
        # 格式化输出
        self._print_analysis(result)
        return result
    
    def _print_analysis(self, result: Dict):
        """格式化打印分析结果"""
        print(f"\n{'='*60}")
        print(f"AI 市场分析 - {result['symbol']}")
        print(f"{'='*60}\n")
        
        print(f"📊 决策: {result['decision']}")
        print(f"💯 置信度: {result['confidence']}%")
        print(f"\n📝 摘要:\n{result['summary']}\n")
        
        print(f"💰 交易建议:")
        print(f"  - 入场价: ${result['entry_price']:.4f}")
        print(f"  - 止损价: ${result['stop_loss']:.4f}")
        print(f"  - 止盈价: ${result['take_profit']:.4f}")
        print(f"  - 仓位: {result['position_size_pct']}%")
        print(f"  - 时间框架: {result['timeframe']}\n")
        
        print(f"🎯 关键原因:")
        for i, reason in enumerate(result['key_reasons'], 1):
            print(f"  {i}. {reason}")
        
        print(f"\n⚠️  风险:")
        for i, risk in enumerate(result['risks'], 1):
            print(f"  {i}. {risk}")
        
        print(f"\n📊 评分:")
        print(f"  - 技术: {result['technical_score']}/100")
        print(f"  - 基本面: {result['fundamental_score']}/100")
        print(f"  - 情绪: {result['sentiment_score']}/100")
```

**使用示例**：
```bash
# 分析比特币
python cli/main.py ai.analyze --market Crypto --symbol BTC/USDT --language zh-CN

# 分析苹果股票
python cli/main.py ai.analyze --market USStock --symbol AAPL --language en-US

# 指定模型
python cli/main.py ai.analyze --market Crypto --symbol ETH/USDT --model anthropic/claude-3.5-sonnet
```

**3.2 API 路由（可选）**

```
api/routes/
└── ai_routes.py                # AI 分析 API
```

```python
@ai_bp.route('/analyze', methods=['POST'])
def analyze():
    """AI 市场分析 API"""
    data = request.get_json()
    
    service = AIAnalysisService()
    result = service.analyze(
        market=data['market'],
        symbol=data['symbol'],
        language=data.get('language', 'en-US'),
        model=data.get('model'),
        timeframe=data.get('timeframe', '1D'),
        user_id=g.user_id if hasattr(g, 'user_id') else None
    )
    
    return jsonify({
        'code': 1 if not result.get('error') else 0,
        'msg': 'success' if not result.get('error') else result['error'],
        'data': result
    })
```

#### Phase 4: 测试和优化（1周）

**4.1 单元测试**

```python
# tests/test_ai_analysis.py
def test_llm_service():
    """测试 LLM 服务"""
    service = LLMService()
    result = service.chat(
        system_prompt="You are a helpful assistant.",
        user_prompt="Say hello",
        model="openai/gpt-4o"
    )
    assert 'content' in result
    assert result['content']

def test_data_collector():
    """测试数据采集"""
    collector = MarketDataCollector()
    data = collector.collect_all(
        market='Crypto',
        symbol='BTC/USDT',
        timeframe='1D'
    )
    assert 'price' in data
    assert 'indicators' in data
    assert 'news' in data

def test_ai_analysis():
    """测试 AI 分析"""
    service = AIAnalysisService()
    result = service.analyze(
        market='Crypto',
        symbol='BTC/USDT',
        language='en-US'
    )
    assert result['decision'] in ['BUY', 'SELL', 'HOLD']
    assert 0 <= result['confidence'] <= 100
    assert result['entry_price'] > 0
```

**4.2 集成测试**

```bash
# 测试完整流程
python cli/main.py ai.analyze --market Crypto --symbol BTC/USDT

# 测试不同语言
python cli/main.py ai.analyze --market Crypto --symbol BTC/USDT --language zh-CN

# 测试不同模型
python cli/main.py ai.analyze --market Crypto --symbol BTC/USDT --model anthropic/claude-3.5-sonnet
```

---

## 配置和环境变量

### 必需的环境变量

```bash
# .env 文件

# LLM 配置
DEFAULT_LLM_MODEL=openai/gpt-4o
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选，支持代理

# OpenRouter（可选）
OPENROUTER_API_KEY=sk-or-xxx

# 自定义 LLM（可选）
CUSTOM_LLM_BASE_URL=https://your-api.com/v1
CUSTOM_LLM_API_KEY=xxx

# 数据源配置
NEWS_API_KEY=xxx  # 新闻 API
CRYPTO_DATA_API_KEY=xxx  # 加密货币数据

# 分析配置
AI_ANALYSIS_CONSENSUS_TIMEFRAMES=1D,4H  # 多周期共识
AI_ANALYSIS_TIMEOUT=60  # 超时时间（秒）
```

### 数据库 Schema

```sql
-- AI 分析历史表
CREATE TABLE IF NOT EXISTS ai_analysis_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    market VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10),
    
    -- 决策信息
    decision VARCHAR(10) NOT NULL,  -- BUY/SELL/HOLD
    confidence INTEGER NOT NULL,
    
    -- 价格建议
    entry_price DECIMAL(20, 8),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    position_size_pct INTEGER,
    
    -- 分析内容
    summary TEXT,
    key_reasons JSONB,
    risks JSONB,
    
    -- 评分
    technical_score INTEGER,
    fundamental_score INTEGER,
    sentiment_score INTEGER,
    objective_score INTEGER,
    
    -- 完整分析数据
    analysis_data JSONB,
    
    -- 市场数据快照
    indicators JSONB,
    macro_data JSONB,
    news_data JSONB,
    
    -- 元数据
    model VARCHAR(100),
    language VARCHAR(10),
    usage JSONB,  -- token 使用量
    
    -- 反馈和验证
    user_feedback VARCHAR(50),  -- helpful/not_helpful/accurate/inaccurate
    was_correct BOOLEAN,  -- 预测是否正确（事后验证）
    actual_return_pct DECIMAL(10, 2),  -- 实际收益率
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_ai_analysis_user ON ai_analysis_history(user_id);
CREATE INDEX idx_ai_analysis_symbol ON ai_analysis_history(market, symbol);
CREATE INDEX idx_ai_analysis_created ON ai_analysis_history(created_at DESC);
CREATE INDEX idx_ai_analysis_indicators ON ai_analysis_history USING GIN(indicators);
```

---

## 成本估算

### LLM 调用成本

**OpenAI GPT-4o**：
- 输入：$2.50 / 1M tokens
- 输出：$10.00 / 1M tokens
- 单次分析：~3000 输入 tokens + ~500 输出 tokens
- **单次成本**：约 $0.0125 (1.25美分)

**OpenRouter Claude 3.5 Sonnet**：
- 输入：$3.00 / 1M tokens
- 输出：$15.00 / 1M tokens
- **单次成本**：约 $0.0165 (1.65美分)

**优化建议**：
- 使用缓存减少重复数据传输
- 批量分析时共享宏观数据
- 对于简单查询使用 GPT-3.5-turbo（成本降低 10x）

---

## 性能优化

### 1. 数据采集优化

```python
# 并行采集多个数据源
import asyncio

async def collect_all_async(self, market, symbol, timeframe):
    """异步并行采集数据"""
    tasks = [
        self._fetch_price_async(market, symbol),
        self._fetch_klines_async(market, symbol, timeframe),
        self._fetch_news_async(market, symbol),
        self._fetch_macro_async(market)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {
        'price': results[0],
        'klines': results[1],
        'news': results[2],
        'macro': results[3]
    }
```

### 2. 提示词缓存

```python
# 缓存系统提示词（不变部分）
@lru_cache(maxsize=10)
def _get_system_prompt_template(language: str) -> str:
    """缓存系统提示词模板"""
    return self._build_system_prompt_template(language)
```

### 3. 结果缓存

```python
# 缓存分析结果（5分钟）
from functools import lru_cache
import time

def analyze_with_cache(self, market, symbol, timeframe):
    """带缓存的分析"""
    cache_key = f"{market}:{symbol}:{timeframe}"
    cache_ttl = 300  # 5分钟
    
    cached = self._get_from_cache(cache_key)
    if cached and time.time() - cached['timestamp'] < cache_ttl:
        return cached['result']
    
    result = self.analyze(market, symbol, timeframe)
    self._set_cache(cache_key, result)
    return result
```

---

## 监控和日志

### 关键指标

```python
# 记录分析性能
logger.info(f"AI Analysis completed", extra={
    'market': market,
    'symbol': symbol,
    'decision': result['decision'],
    'confidence': result['confidence'],
    'model': result['model'],
    'duration_ms': duration,
    'tokens_used': result['usage']['total_tokens'],
    'cost_usd': calculate_cost(result['usage'], result['model'])
})
```

### 错误处理

```python
try:
    result = self.analyze(market, symbol)
except LLMTimeoutError as e:
    logger.error(f"LLM timeout: {e}")
    return {"error": "Analysis timeout, please try again"}
except LLMRateLimitError as e:
    logger.error(f"Rate limit: {e}")
    return {"error": "Rate limit exceeded, please wait"}
except Exception as e:
    logger.error(f"Analysis failed: {e}", exc_info=True)
    return {"error": str(e)}
```

---

## 安全考虑

### 1. API Key 保护

```python
# 不要在日志中暴露 API Key
def _sanitize_config(config):
    """清理配置中的敏感信息"""
    sanitized = config.copy()
    if 'api_key' in sanitized:
        sanitized['api_key'] = '***'
    return sanitized
```

### 2. 输入验证

```python
def validate_input(market, symbol):
    """验证输入参数"""
    valid_markets = ['Crypto', 'USStock', 'Forex']
    if market not in valid_markets:
        raise ValueError(f"Invalid market: {market}")
    
    # 防止注入攻击
    if not re.match(r'^[A-Z0-9/\-]+$', symbol):
        raise ValueError(f"Invalid symbol: {symbol}")
```

### 3. 输出验证

```python
def validate_output(analysis):
    """验证 LLM 输出的安全性"""
    # 检查价格是否合理
    if analysis['entry_price'] <= 0:
        raise ValueError("Invalid entry price")
    
    # 检查是否包含恶意内容
    for field in ['summary', 'key_reasons', 'risks']:
        if contains_malicious_content(analysis[field]):
            raise ValueError("Malicious content detected")
```

---

## 总结

### 核心优势

1. **多维度分析**：技术 + 基本面+ 新闻 + 宏观 + 地缘政治
2. **结构化输出**：JSON 格式，易于解析和使用
3. **强约束提示词**：确保输出质量和一致性
4. **地缘政治检测**：自动识别重大风险事件
5. **历史记忆**：学习和改进分析质量
6. **多 LLM 支持**：灵活切换不同模型

### 实施时间线

- **Phase 1**: 基础架构（1周）
- **Phase 2**: AI 分析服务（2周）
- **Phase 3**: CLI 和 API 集成（1周）
- **Phase 4**: 测试和优化（1周）

**总计**: 约 5 周

### 下一步行动

1. 创建 LLMService 和 Provider 抽象层
2. 实现 MarketDataCollector 统一数据采集
3. 构建提示词模板和验证逻辑
4. 实现 AIAnalysisService 主服务
5. 添加 CLI 命令和测试

---

**文档版本**: 1.0  
**最后更新**: 2026-05-22  
**作者**: AI Assistant  
**参考**: QuantDinger Fast Analysis Service 3.0
