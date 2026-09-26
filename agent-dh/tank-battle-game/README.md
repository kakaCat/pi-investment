# 🎮 坦克大作战 (Tank Battle Game)

一个使用 HTML5 Canvas 开发的经典坦克大战游戏。

## 📋 游戏特性

- 🎯 玩家坦克控制系统
- 🤖 智能敌方坦克 AI
- 💥 完整的射击与爆炸效果
- 🏆 得分与关卡系统
- ❤️ 生命值系统
- ⏸️ 暂停功能
- 🎨 精美的视觉效果

## 🎮 操作说明

### 移动控制
- `W` 或 `↑` - 向上移动
- `S` 或 `↓` - 向下移动
- `A` 或 `←` - 向左移动
- `D` 或 `→` - 向右移动

### 战斗控制
- `空格键` - 发射子弹
- `P` - 暂停/继续游戏

## 🚀 快速开始

### 方法一：直接打开 HTML 文件
```bash
# 在浏览器中打开 index.html
open index.html  # macOS
# 或
start index.html  # Windows
# 或
xdg-open index.html  # Linux
```

### 方法二：使用本地服务器（推荐）
```bash
# 使用 Python 3
python3 -m http.server 8000

# 使用 Python 2
python -m SimpleHTTPServer 8000

# 使用 Node.js (需要先安装 http-server)
npx http-server -p 8000
```

然后在浏览器中访问：`http://localhost:8000`

## 📁 项目结构

```
tank-battle-game/
├── index.html          # 游戏主页面
├── src/
│   └── game.js        # 游戏核心逻辑
├── public/            # 资源文件目录（预留）
└── README.md          # 项目说明
```

## 🎯 游戏规则

1. **目标**：消灭所有敌方坦克并存活下来
2. **得分**：每消灭一辆敌方坦克获得 100 分
3. **生命**：玩家拥有 3 条生命，被敌方子弹击中会失去一条生命
4. **关卡**：消灭当前关卡所有敌方坦克后进入下一关
5. **难度**：每个关卡敌方坦克数量会增加

## 🔧 技术实现

- **前端框架**：纯 HTML5 + CSS3 + JavaScript
- **渲染引擎**：Canvas 2D API
- **动画循环**：requestAnimationFrame
- **碰撞检测**：矩形碰撞算法
- **AI 逻辑**：随机移动与射击

## 🎨 游戏特色

- 🌟 流畅的 60 FPS 游戏体验
- 💫 炫酷的爆炸动画效果
- 🎯 精准的碰撞检测系统
- 🤖 智能的敌方坦克 AI
- 📱 响应式游戏界面

## 🛠️ 未来改进

- [ ] 添加障碍物系统
- [ ] 增加不同类型的坦克
- [ ] 添加道具系统（加血、增强火力等）
- [ ] 实现音效系统
- [ ] 添加多人对战模式
- [ ] 保存最高分记录
- [ ] 移动端触摸控制支持

## 📝 开发说明

本游戏使用原生 JavaScript 开发，无需任何第三方库或框架。代码结构清晰，易于理解和扩展。

### 核心类说明

- `PlayerTank` - 玩家坦克类
- `EnemyTank` - 敌方坦克类
- `Bullet` - 子弹类
- `Explosion` - 爆炸效果类

## 📄 许可证

MIT License

## 👨‍💻 作者

开发：AI Assistant
项目：REQ-260924162957-2cd3

---

**享受游戏，祝你好运！🎮**
