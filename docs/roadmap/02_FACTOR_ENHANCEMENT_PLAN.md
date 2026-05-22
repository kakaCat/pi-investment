# 因子工程提升计划 (8.5 → 9.5)

**目标**: 将因子工程从8.5分提升到9.5分  
**时间**: 2-3个月  
**难度**: ⭐⭐⭐⭐⭐ (非常困难)

---

## 📊 当前状态

### 现有因子 (64个)
- ✅ 技术指标因子 (50个): MA, RSI, MACD, Bollinger等
- ✅ 基本面因子 (12个): PE, PB, ROE, 现金流等
- ✅ 情绪因子 (2个): 换手率、振幅

### 缺失因子
- ❌ 另类数据因子 (0个)
- ❌ 因子正交化处理
- ❌ 因子IC/IR分析

---

## 🎯 提升目标

### 新增能力

1. **另类数据因子** (20个) - 预计+0.4分
2. **因子正交化** - 预计+0.3分
3. **因子IC/IR分析** - 预计+0.3分

**总计**: 从64个增加到84个因子，新增因子分析框架

---

## 📋 实施计划

### Phase 1: 另类数据因子 (6-8周)

#### 1.1 舆情因子 (2周)

**因子1: 新闻情绪因子**
```python
# quantsys-v2/quant/engine/alternative/news_sentiment_factor.py

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class NewsSentimentFactor:
    """
    新闻情绪因子
    
    数据源：
    - 财经新闻API
    - 社交媒体
    - 公告文本
    
    方法：
    - BERT情感分析
    - 关键词提取
    - 事件分类
    """
    
    def __init__(self):
        # 加载预训练模型
        self.tokenizer = AutoTokenizer.from_pretrained("bert-base-chinese")
        self.model = AutoModelForSequenceClassification.from_pretrained(
            "bert-base-chinese-sentiment"
        )
        self.model.eval()
    
    def analyze_sentiment(self, text):
        """分析文本情感"""
        inputs = self.tokenizer(text, return_tensors="pt", 
                               truncation=True, max_length=512)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            scores = torch.softmax(outputs.logits, dim=1)
        
        # 返回情感分数 [-1, 1]
        sentiment = scores[0][1].item() - scores[0][0].item()
        return sentiment
    
    def fetch_news(self, symbol, days=7):
        """获取新闻"""
        # 调用新闻API
        news_api_url = f"https://api.news.com/search?symbol={symbol}&days={days}"
        response = requests.get(news_api_url)
        return response.json()['articles']
    
    def calculate(self, symbol, date):
        """计算新闻情绪因子"""
        # 1. 获取最近7天新闻
        news = self.fetch_news(symbol, days=7)
        
        if not news:
            return None
        
        # 2. 分析每条新闻情感
        sentiments = []
        for article in news:
            text = article['title'] + ' ' + article['content']
            sentiment = self.analyze_sentiment(text)
            
            # 根据新闻重要性加权
            weight = article.get('importance', 1.0)
            sentiments.append(sentiment * weight)
        
        # 3. 计算加权平均情感
        avg_sentiment = np.average(sentiments)
        
        # 4. 计算情感变化率
        recent_sentiment = np.mean(sentiments[-3:])  # 最近3天
        older_sentiment = np.mean(sentiments[:3])    # 之前3天
        sentiment_change = recent_sentiment - older_sentiment
        
        return {
            'news_sentiment': avg_sentiment,
            'sentiment_change': sentiment_change,
            'news_count': len(news)
        }
```

**因子2: 社交媒体热度因子**
```python
# quantsys-v2/quant/engine/alternative/social_media_factor.py

class SocialMediaFactor:
    """
    社交媒体热度因子
    
    数据源：
    - 微博
    - 雪球
    - 东方财富股吧
    
    指标：
    - 讨论量
    - 情绪倾向
    - 关注度变化
    """
    
    def __init__(self):
        self.platforms = ['weibo', 'xueqiu', 'eastmoney']
    
    def fetch_social_data(self, symbol, platform, days=7):
        """获取社交媒体数据"""
        api_url = f"https://api.{platform}.com/stock/{symbol}/posts?days={days}"
        response = requests.get(api_url)
        return response.json()
    
    def calculate_attention_score(self, posts):
        """计算关注度分数"""
        # 考虑因素：
        # - 帖子数量
        # - 阅读量
        # - 评论数
        # - 转发数
        
        total_posts = len(posts)
        total_views = sum(p.get('views', 0) for p in posts)
        total_comments = sum(p.get('comments', 0) for p in posts)
        total_shares = sum(p.get('shares', 0) for p in posts)
        
        # 归一化
        attention_score = (
            np.log1p(total_posts) * 0.2 +
            np.log1p(total_views) * 0.3 +
            np.log1p(total_comments) * 0.3 +
            np.log1p(total_shares) * 0.2
        )
        
        return attention_score
    
    def calculate(self, symbol, date):
        """计算社交媒体因子"""
        all_posts = []
        
        # 1. 从各平台获取数据
        for platform in self.platforms:
            posts = self.fetch_social_data(symbol, platform, days=7)
            all_posts.extend(posts)
        
        if not all_posts:
            return None
        
        # 2. 计算关注度
        attention = self.calculate_attention_score(all_posts)
        
        # 3. 计算情绪
        sentiments = [p.get('sentiment', 0) for p in all_posts]
        avg_sentiment = np.mean(sentiments)
        
        # 4. 计算热度变化
        recent_posts = [p for p in all_posts if self.is_recent(p, days=3)]
        older_posts = [p for p in all_posts if not self.is_recent(p, days=3)]
        
        recent_attention = self.calculate_attention_score(recent_posts)
        older_attention = self.calculate_attention_score(older_posts)
        attention_change = recent_attention - older_attention
        
        return {
            'social_attention': attention,
            'social_sentiment': avg_sentiment,
            'attention_change': attention_change,
            'post_count': len(all_posts)
        }
```

**因子3-5**: 分析师评级因子、机构调研因子、高管变动因子

#### 1.2 卫星图像因子 (2周)

**因子6: 停车场车辆数因子**
```python
# quantsys-v2/quant/engine/alternative/satellite_parking_factor.py

import cv2
from ultralytics import YOLO

class SatelliteParkingFactor:
    """
    卫星图像停车场车辆数因子
    
    应用场景：
    - 零售企业（商场客流）
    - 制造企业（产能利用率）
    - 物流企业（仓储活跃度）
    
    数据源：
    - Planet Labs卫星图像
    - Sentinel-2卫星数据
    """
    
    def __init__(self):
        # 加载车辆检测模型
        self.model = YOLO('yolov8n.pt')
    
    def fetch_satellite_image(self, location, date):
        """获取卫星图像"""
        # 调用卫星图像API
        api_url = f"https://api.planet.com/data/v1/quick-search"
        
        payload = {
            "item_types": ["PSScene"],
            "filter": {
                "type": "AndFilter",
                "config": [
                    {
                        "type": "GeometryFilter",
                        "field_name": "geometry",
                        "config": location
                    },
                    {
                        "type": "DateRangeFilter",
                        "field_name": "acquired",
                        "config": {
                            "gte": date,
                            "lte": date
                        }
                    }
                ]
            }
        }
        
        response = requests.post(api_url, json=payload)
        image_url = response.json()['features'][0]['assets']['visual']['href']
        
        # 下载图像
        image = cv2.imread(image_url)
        return image
    
    def count_vehicles(self, image):
        """检测车辆数量"""
        results = self.model(image)
        
        vehicle_count = 0
        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls = int(box.cls[0])
                # 车辆类别：2=car, 5=bus, 7=truck
                if cls in [2, 5, 7]:
                    vehicle_count += 1
        
        return vehicle_count
    
    def calculate(self, symbol, date):
        """计算停车场车辆数因子"""
        # 1. 获取公司停车场位置
        locations = self.get_company_locations(symbol)
        
        if not locations:
            return None
        
        # 2. 获取卫星图像并计数
        vehicle_counts = []
        for location in locations:
            image = self.fetch_satellite_image(location, date)
            count = self.count_vehicles(image)
            vehicle_counts.append(count)
        
        # 3. 计算平均车辆数
        avg_vehicles = np.mean(vehicle_counts)
        
        # 4. 计算同比变化
        last_year_date = date - timedelta(days=365)
        last_year_counts = []
        for location in locations:
            image = self.fetch_satellite_image(location, last_year_date)
            count = self.count_vehicles(image)
            last_year_counts.append(count)
        
        yoy_change = (avg_vehicles - np.mean(last_year_counts)) / np.mean(last_year_counts)
        
        return {
            'parking_vehicles': avg_vehicles,
            'parking_yoy_change': yoy_change,
            'location_count': len(locations)
        }
```

**因子7-10**: 工厂烟囱排放因子、港口船舶数因子、农田作物长势因子、建筑工地活跃度因子

#### 1.3 其他另类数据因子 (2-4周)

**因子11-20**:
- 招聘数据因子（企业扩张）
- 专利申请因子（创新能力）
- 供应链数据因子（上下游关系）
- 信用卡消费因子（消费趋势）
- 电商销量因子（产品热度）
- 物流数据因子（商品流通）
- 天气数据因子（季节性影响）
- 能源消耗因子（产能利用率）
- 移动位置因子（客流量）
- 网络搜索因子（关注度）

---

### Phase 2: 因子正交化 (2-3周)

#### 2.1 因子相关性分析

```python
# quantsys-v2/quant/engine/factor_analysis/correlation_analyzer.py

class FactorCorrelationAnalyzer:
    """
    因子相关性分析器
    
    功能：
    - 计算因子相关性矩阵
    - 识别高度相关因子
    - 可视化相关性热图
    """
    
    def __init__(self):
        self.correlation_matrix = None
    
    def calculate_correlation_matrix(self, factor_data):
        """计算因子相关性矩阵"""
        # factor_data: DataFrame, columns=因子名称, rows=股票×日期
        self.correlation_matrix = factor_data.corr()
        return self.correlation_matrix
    
    def find_highly_correlated_pairs(self, threshold=0.8):
        """找出高度相关的因子对"""
        corr_matrix = self.correlation_matrix
        
        highly_correlated = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                if abs(corr_matrix.iloc[i, j]) > threshold:
                    highly_correlated.append({
                        'factor1': corr_matrix.columns[i],
                        'factor2': corr_matrix.columns[j],
                        'correlation': corr_matrix.iloc[i, j]
                    })
        
        return highly_correlated
    
    def plot_correlation_heatmap(self, save_path=None):
        """绘制相关性热图"""
        import seaborn as sns
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(20, 16))
        sns.heatmap(self.correlation_matrix, 
                   annot=False, 
                   cmap='coolwarm',
                   center=0,
                   vmin=-1, vmax=1)
        plt.title('Factor Correlation Matrix')
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
```

#### 2.2 因子正交化实现

```python
# quantsys-v2/quant/engine/factor_analysis/orthogonalization.py

from sklearn.decomposition import PCA
from scipy.linalg import qr

class FactorOrthogonalizer:
    """
    因子正交化处理器
    
    方法：
    1. Schmidt正交化
    2. PCA主成分分析
    3. 对称正交化
    """
    
    def schmidt_orthogonalization(self, factor_data, base_factors):
        """
        Schmidt正交化
        
        原理：
        - 选择基础因子（如市值、行业）
        - 其他因子对基础因子做回归
        - 使用残差作为正交化后的因子
        """
        orthogonal_factors = factor_data.copy()
        
        for factor in factor_data.columns:
            if factor in base_factors:
                continue
            
            # 对基础因子做回归
            X = factor_data[base_factors]
            y = factor_data[factor]
            
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
            model.fit(X, y)
            
            # 残差作为正交化因子
            residuals = y - model.predict(X)
            orthogonal_factors[factor] = residuals
        
        return orthogonal_factors
    
    def pca_orthogonalization(self, factor_data, n_components=None):
        """
        PCA主成分分析
        
        原理：
        - 提取主成分
        - 主成分之间正交
        - 保留最重要的成分
        """
        if n_components is None:
            n_components = min(factor_data.shape)
        
        pca = PCA(n_components=n_components)
        principal_components = pca.fit_transform(factor_data)
        
        # 转换为DataFrame
        pc_names = [f'PC{i+1}' for i in range(n_components)]
        pc_df = pd.DataFrame(
            principal_components,
            index=factor_data.index,
            columns=pc_names
        )
        
        return pc_df, pca.explained_variance_ratio_
    
    def symmetric_orthogonalization(self, factor_data):
        """
        对称正交化
        
        原理：
        - 使用QR分解
        - 保持因子的对称性
        """
        # 标准化
        standardized = (factor_data - factor_data.mean()) / factor_data.std()
        
        # QR分解
        Q, R = qr(standardized.values)
        
        # Q矩阵的列向量是正交的
        orthogonal_df = pd.DataFrame(
            Q,
            index=factor_data.index,
            columns=factor_data.columns
        )
        
        return orthogonal_df
```

---

### Phase 3: 因子IC/IR分析 (2-3周)

#### 3.1 IC分析实现

```python
# quantsys-v2/quant/engine/factor_analysis/ic_analyzer.py

class ICAnalyzer:
    """
    因子IC（Information Coefficient）分析器
    
    IC指标：
    - IC: 因子值与未来收益的相关系数
    - IC_mean: IC均值
    - IC_std: IC标准差
    - IC_IR: IC信息比率 = IC_mean / IC_std
    - ICIR: 年化IC信息比率
    """
    
    def calculate_ic(self, factor_values, forward_returns):
        """
        计算IC
        
        参数：
        - factor_values: 因子值 (N stocks)
        - forward_returns: 未来收益 (N stocks)
        
        返回：
        - IC: Spearman相关系数
        """
        from scipy.stats import spearmanr
        
        # 去除NaN
        mask = ~(np.isnan(factor_values) | np.isnan(forward_returns))
        factor_clean = factor_values[mask]
        returns_clean = forward_returns[mask]
        
        if len(factor_clean) < 10:  # 样本太少
            return np.nan
        
        ic, pvalue = spearmanr(factor_clean, returns_clean)
        return ic
    
    def calculate_ic_series(self, factor_data, return_data, periods=[1, 5, 10, 20]):
        """
        计算IC时间序列
        
        参数：
        - factor_data: DataFrame (dates × stocks)
        - return_data: DataFrame (dates × stocks)
        - periods: 预测周期列表
        
        返回：
        - ic_series: DataFrame (dates × periods)
        """
        ic_results = {}
        
        for period in periods:
            ic_list = []
            dates = []
            
            for date in factor_data.index[:-period]:
                # 当日因子值
                factor_values = factor_data.loc[date].values
                
                # 未来period天的收益
                future_date = factor_data.index[factor_data.index.get_loc(date) + period]
                forward_returns = return_data.loc[future_date].values
                
                # 计算IC
                ic = self.calculate_ic(factor_values, forward_returns)
                ic_list.append(ic)
                dates.append(date)
            
            ic_results[f'IC_{period}D'] = pd.Series(ic_list, index=dates)
        
        return pd.DataFrame(ic_results)
    
    def calculate_ic_statistics(self, ic_series):
        """计算IC统计指标"""
        stats = {}
        
        for col in ic_series.columns:
            ic_values = ic_series[col].dropna()
            
            stats[col] = {
                'IC_mean': ic_values.mean(),
                'IC_std': ic_values.std(),
                'IC_IR': ic_values.mean() / ic_values.std() if ic_values.std() > 0 else 0,
                'IC_positive_rate': (ic_values > 0).sum() / len(ic_values),
                'IC_abs_mean': ic_values.abs().mean(),
                'ICIR_annual': ic_values.mean() / ic_values.std() * np.sqrt(252) if ic_values.std() > 0 else 0
            }
        
        return pd.DataFrame(stats).T
    
    def plot_ic_series(self, ic_series, save_path=None):
        """绘制IC时间序列"""
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        
        # IC时间序列
        ic_series.plot(ax=axes[0], alpha=0.7)
        axes[0].axhline(y=0, color='r', linestyle='--', alpha=0.5)
        axes[0].set_title('IC Time Series')
        axes[0].set_ylabel('IC')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # IC累积值
        ic_series.cumsum().plot(ax=axes[1], alpha=0.7)
        axes[1].set_title('Cumulative IC')
        axes[1].set_ylabel('Cumulative IC')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
```

#### 3.2 因子分层回测

```python
# quantsys-v2/quant/engine/factor_analysis/layering_backtest.py

class FactorLayeringBacktest:
    """
    因子分层回测
    
    方法：
    - 按因子值分N层
    - 计算每层收益
    - 分析单调性
    """
    
    def __init__(self, n_quantiles=5):
        self.n_quantiles = n_quantiles
    
    def backtest(self, factor_data, return_data, holding_period=20):
        """
        分层回测
        
        参数：
        - factor_data: 因子值 (dates × stocks)
        - return_data: 收益率 (dates × stocks)
        - holding_period: 持有期
        
        返回：
        - layer_returns: 每层收益 (dates × layers)
        """
        layer_returns_list = []
        dates = []
        
        for i, date in enumerate(factor_data.index[:-holding_period]):
            # 当日因子值
            factor_values = factor_data.loc[date]
            
            # 分层
            quantiles = pd.qcut(factor_values, q=self.n_quantiles, 
                               labels=False, duplicates='drop')
            
            # 未来收益
            future_date = factor_data.index[i + holding_period]
            forward_returns = return_data.loc[future_date]
            
            # 计算每层平均收益
            layer_returns = []
            for layer in range(self.n_quantiles):
                mask = (quantiles == layer)
                layer_return = forward_returns[mask].mean()
                layer_returns.append(layer_return)
            
            layer_returns_list.append(layer_returns)
            dates.append(date)
        
        # 转换为DataFrame
        layer_names = [f'Layer_{i+1}' for i in range(self.n_quantiles)]
        layer_returns_df = pd.DataFrame(
            layer_returns_list,
            index=dates,
            columns=layer_names
        )
        
        return layer_returns_df
    
    def calculate_layer_statistics(self, layer_returns):
        """计算分层统计"""
        stats = {}
        
        for col in layer_returns.columns:
            returns = layer_returns[col]
            
            stats[col] = {
                'mean_return': returns.mean(),
                'std_return': returns.std(),
                'sharpe_ratio': returns.mean() / returns.std() * np.sqrt(252),
                'win_rate': (returns > 0).sum() / len(returns),
                'cumulative_return': (1 + returns).prod() - 1
            }
        
        return pd.DataFrame(stats).T
    
    def plot_layer_performance(self, layer_returns, save_path=None):
        """绘制分层表现"""
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        
        # 累积收益
        (1 + layer_returns).cumprod().plot(ax=axes[0])
        axes[0].set_title('Cumulative Returns by Layer')
        axes[0].set_ylabel('Cumulative Return')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # 平均收益柱状图
        layer_returns.mean().plot(kind='bar', ax=axes[1])
        axes[1].set_title('Average Returns by Layer')
        axes[1].set_ylabel('Average Return')
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
```

---

## 📊 实施时间表

| 阶段 | 任务 | 时间 | 人力 |
|------|------|------|------|
| Phase 1 | 另类数据因子 (20个) | 6-8周 | 3人 |
| Phase 2 | 因子正交化 | 2-3周 | 2人 |
| Phase 3 | IC/IR分析 | 2-3周 | 2人 |
| **总计** | **完整因子分析框架** | **10-14周** | **2-3人** |

---

## 💰 成本估算

### 人力成本
- 量化研究员 x2: ¥80,000/月 x 3.5个月 = ¥560,000
- 数据工程师 x1: ¥60,000/月 x 3.5个月 = ¥210,000
- **总计**: ¥770,000

### 数据成本
- 新闻舆情数据: ¥30,000/月 x 3.5个月 = ¥105,000
- 卫星图像数据: ¥50,000/月 x 3.5个月 = ¥175,000
- 其他另类数据: ¥40,000/月 x 3.5个月 = ¥140,000
- **总计**: ¥420,000

### 总成本: ¥1,190,000

---

## 🎯 预期收益

### 评分提升
- 因子工程: 8.5 → 9.5 (+1.0分)
- 综合评分: 9.08 → 9.23 (+0.15分)

### 业务收益
- 因子数量: 64个 → 84个 (+31%)
- 因子质量: IC_IR提升20-30%
- 预期年化收益提升: +3-5%

---

## ✅ 成功标准

1. **因子数量**: 新增20个另类数据因子
2. **因子质量**: 平均IC_IR > 1.5
3. **正交化**: 因子间相关性 < 0.5
4. **分析框架**: 完整的IC/IR分析系统
5. **评分达标**: 因子工程评分达到9.5分

---

**文档版本**: v1.0  
**创建日期**: 2026-05-21  
**负责人**: 量化研究团队
