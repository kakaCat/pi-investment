# 需求文档：坦克大作战企业级游戏开发

**需求ID**: REQ-260924162957-2cd3  
**类型**: feature  
**难度**: expert  
**状态**: brainstorming  
**创建时间**: 2024-09-24  
**最后更新**: 2024-09-24

---


## 升级声明

**本需求已从轻档升级为重档**

**升级理由**：
1. 这是全新游戏开发，不是"改动面小"的增量修改
2. 需要多个架构决策（游戏引擎架构、状态管理、资源加载策略）
3. 需要新增多个子系统（场景管理、音效、粒子系统、关卡编辑）
4. 企业级要求：TypeScript、测试覆盖、构建工具链、代码规范

---

## 一、概述与目标

### 1.1 一句话目标

开发一个**企业级质量**的坦克大作战游戏，具备完整的关卡系统、丰富的游戏机制、专业的代码架构和可扩展性。

### 1.2 可证伪判定标准

#### 基础功能（P0）
1. ✅ 运行 `npm run dev` 启动开发服务器
2. ✅ 访问 `http://localhost:5173` 看到游戏主菜单
3. ✅ 使用 WASD/方向键控制玩家坦克移动流畅（60 FPS）
4. ✅ 按空格键发射子弹，带音效反馈
5. ✅ 敌方坦克 AI 自动移动、射击、避障
6. ✅ 击毁坦克显示爆炸粒子特效
7. ✅ 完成第1关进入第2关，关卡过渡动画流畅

#### 企业级质量（P0）
8. ✅ 运行 `npm test` 单元测试通过率 ≥ 80%
9. ✅ 运行 `npm run build` 生成生产构建（< 500KB gzipped）
10. ✅ 运行 `npm run lint` 无 ESLint 错误
11. ✅ Chrome DevTools Performance 分析帧率稳定 55-60 FPS
12. ✅ 支持暂停（P键）、重新开始、返回主菜单

#### 关卡系统（P0）
13. ✅ 至少 5 个关卡，难度递增
14. ✅ 关卡配置使用 JSON 格式，可外部编辑
15. ✅ 关卡间过渡显示关卡名称和目标

---

## 边界

### 2.1 做什么 ✅

#### 核心游戏机制
- **玩家控制**
  - 四方向移动（WASD/方向键）
  - 炮管独立转向（跟随移动或鼠标）
  - 射击系统（空格/鼠标左键）
  - 边界碰撞与反弹

- **敌方 AI**
  - 三级 AI（巡逻型、追击型、狙击型）
  - 自动寻路与避障
  - 射击预判
  - 团队协作（包抄、掩护）

- **关卡系统**
  - JSON 配置驱动
  - 5 个手工设计关卡
  - 关卡目标系统（消灭全部敌人、保护基地）
  - 关卡过渡动画

#### 游戏系统
- **生命与得分**
  - 生命值系统（玩家 3 条命，敌军单次击毁）
  - 得分系统（击毁+100，连击奖励+50，关卡完成奖励）
  - 最高分记录（LocalStorage 持久化）

- **障碍物与地形**
  - 砖墙（可摧毁）
  - 钢墙（不可摧毁）
  - 水域（不可通行）
  - 草地（视觉遮蔽）
  - 基地（玩家需保护）

- **道具系统**
  - 生命补给（+1 命）
  - 护盾（5 秒无敌）
  - 火力增强（穿透、连发）
  - 时间冻结（敌军暂停 3 秒）

#### 视觉与音效
- **图形效果**
  - 精灵图集（坦克、子弹、地形）
  - 爆炸粒子系统
  - 开火闪光效果
  - 履带移动动画

- **音效系统**
  - 射击音效
  - 爆炸音效
  - 道具拾取音效
  - 背景音乐（可关闭）

#### 企业级架构
- **技术栈**
  - TypeScript（严格模式）
  - Vite（构建工具）
  - Vitest（单元测试）
  - Canvas 2D API

- **代码规范**
  - ESLint + Prettier
  - 模块化架构（分层设计）
  - 接口与抽象类
  - 依赖注入

- **性能优化**
  - 对象池（子弹、粒子复用）
  - 空间分区（四叉树碰撞检测）
  - 脏矩形渲染（可选）
  - 资源预加载

### 2.2 不做什么 ❌

#### 本次不实现（P1/P2 功能）
- 联机对战（网络同步复杂度高）
- 关卡编辑器 UI（本次只提供 JSON 格式）
- 移动端适配（触摸控制、屏幕旋转）
- 成就系统
- 剧情模式
- 自定义皮肤

#### 明确排除
- 后端服务器（纯前端）
- 用户账号系统
- 云存档
- 内购/广告
- 社交分享

---

## 三、架构设计

### 3.1 核心架构决策

#### AD-1: 游戏引擎架构 → **ECS + Service Locator**

**决策**：采用轻量级 ECS（Entity-Component-System）+ 服务定位器模式

**理由**：
- ECS 分离数据与行为，便于测试和扩展
- Service Locator 管理全局服务（输入、音效、资源）
- 避免过度设计（不引入完整 ECS 框架如 Phaser/PixiJS）

**实现**：
```typescript
// 核心接口
interface Entity {
  id: string;
  components: Map<string, Component>;
}

interface Component {
  type: string;
}

interface System {
  update(entities: Entity[], deltaTime: number): void;
}
```

#### AD-2: 状态管理 → **状态机模式**

**决策**：使用显式状态机管理游戏状态

**状态图**：
```
[Boot] → [MainMenu] ⇄ [Settings]
            ↓
        [Playing] ⇄ [Paused]
            ↓
      [LevelComplete] → [Playing] (next level)
            ↓
       [GameOver] → [MainMenu]
```

**实现**：
```typescript
enum GameState {
  Boot, MainMenu, Playing, Paused, LevelComplete, GameOver
}

class StateManager {
  private current: GameState;
  private states: Map<GameState, State>;
  
  transition(to: GameState): void;
}
```

#### AD-3: 资源管理 → **预加载 + 懒加载混合**

**决策**：
- **启动时预加载**：核心图片（坦克、地形）、必需音效
- **关卡切换时懒加载**：关卡特定资源

**实现**：
```typescript
class AssetLoader {
  async preload(manifest: AssetManifest): Promise<void>;
  async loadLevel(levelId: number): Promise<void>;
  get<T>(key: string): T;
}
```

#### AD-4: 碰撞检测 → **四叉树 + AABB**

**决策**：空间分区（四叉树）+ 轴对齐包围盒（AABB）

**理由**：
- 四叉树将 O(n²) 降至 O(n log n)
- AABB 足够精确且性能好
- 不需要像素级碰撞

#### AD-5: 关卡数据格式 → **JSON Schema**

**决策**：JSON 格式 + JSON Schema 校验

**示例**：
```json
{
  "id": 1,
  "name": "Tutorial",
  "width": 26,
  "height": 26,
  "tiles": "...",
  "enemies": [
    { "type": "patrol", "x": 10, "y": 5 }
  ],
  "objectives": {
    "type": "eliminate_all",
    "timeLimit": 180
  }
}
```

---

## 四、数据契约

### 4.1 游戏配置（GameConfig）

```typescript
interface GameConfig {
  canvas: {
    width: number;        // 800
    height: number;       // 600
    backgroundColor: string;
  };
  physics: {
    gravity: number;      // 0 (2D 俯视角无重力)
    maxVelocity: number;  // 300 px/s
  };
  player: {
    speed: number;        // 150 px/s
    fireRate: number;     // 500 ms
    maxLives: number;     // 3
  };
  enemy: {
    types: EnemyConfig[];
  };
}
```

### 4.2 关卡数据（Level）

```typescript
interface Level {
  id: number;
  name: string;
  width: number;        // 格子数（26x26）
  height: number;
  tiles: string;        // 编码字符串："0"=空地, "1"=砖墙, "2"=钢墙
  enemies: EnemySpawn[];
  powerups: PowerupSpawn[];
  objectives: Objective;
}
```

### 4.3 游戏状态（GameState）

```typescript
interface GameState {
  currentLevel: number;
  score: number;
  lives: number;
  highScore: number;     // LocalStorage 持久化
  isPaused: boolean;
  entities: Entity[];
}
```

---

## 五、接口定义

### 5.1 对外接口（Public API）

#### 游戏实例
```typescript
class TankBattleGame {
  constructor(containerId: string, config?: Partial<GameConfig>);
  
  start(): void;
  pause(): void;
  resume(): void;
  restart(): void;
  destroy(): void;
  
  on(event: GameEvent, callback: Function): void;
  off(event: GameEvent, callback: Function): void;
}
```

#### 事件系统
```typescript
enum GameEvent {
  LevelStart = 'level:start',
  LevelComplete = 'level:complete',
  GameOver = 'game:over',
  ScoreChange = 'score:change',
  LivesChange = 'lives:change',
}

// 示例
game.on(GameEvent.LevelComplete, (level: number) => {
  console.log(`Level ${level} completed!`);
});
```

### 5.2 内部接口

#### 核心系统
```typescript
interface System {
  priority: number;
  update(deltaTime: number): void;
}

interface Renderer {
  render(entities: Entity[]): void;
  clear(): void;
}

interface InputManager {
  isKeyPressed(key: string): boolean;
  getMousePosition(): { x: number; y: number };
}
```

---

## 功能点

### FR-1: 玩家坦克控制
- 支持 WASD 和方向键四向移动
- 炮管方向跟随移动方向或鼠标（可配置）
- 空格键或鼠标左键发射子弹
- 射击冷却时间 500ms
- 边界碰撞检测与限制

### FR-2: 敌方坦克 AI
- **巡逻型 AI**：随机移动，遇到障碍改变方向
- **追击型 AI**：检测玩家，主动接近并攻击
- **狙击型 AI**：远程攻击，保持距离
- 所有 AI 具备避障能力
- 射击预判（提前瞄准移动目标）

### FR-3: 子弹系统
- 玩家子弹与敌方子弹区分渲染
- 子弹速度 400 px/s
- 出界自动销毁
- 击中目标产生爆炸效果
- 对象池复用（性能优化）

### FR-4: 碰撞检测
- 坦克与坦克碰撞（阻挡）
- 坦克与障碍物碰撞（阻挡或摧毁）
- 子弹与坦克碰撞（伤害）
- 子弹与障碍物碰撞（摧毁砖墙，钢墙反弹）
- 四叉树空间分区优化

### FR-5: 爆炸与粒子效果
- 坦克被摧毁显示爆炸动画
- 粒子系统（火焰、烟雾、碎片）
- 子弹击中墙壁的火花效果
- 开火时的闪光效果

### FR-6: 生命值系统
- 玩家初始 3 条命
- 被击中减少 1 条命
- 生命归零游戏结束
- 拾取生命道具 +1 命（最多 5 命）

### FR-7: 得分系统
- 击毁敌方坦克 +100 分
- 连击奖励（5 秒内连续击毁）+50 分
- 关卡完成奖励 +500 分
- 最高分保存到 LocalStorage
- 实时显示当前得分和最高分

### FR-8: 关卡系统
- 至少 5 个手工设计关卡
- JSON 配置格式
- 关卡目标系统（消灭全部敌人/保护基地）
- 关卡间过渡动画
- 难度递增（敌军数量、AI 类型）

### FR-9: 障碍物与地形
- **砖墙**：可被子弹摧毁
- **钢墙**：不可摧毁，子弹反弹
- **水域**：不可通行
- **草地**：坦克可通过，视觉遮蔽
- **基地**：玩家需保护，被摧毁游戏失败

### FR-10: 道具系统
- **生命补给**：+1 命
- **护盾**：5 秒无敌状态
- **火力增强**：子弹穿透 / 连发
- **时间冻结**：敌军暂停 3 秒
- 道具随机生成，持续 10 秒后消失

### FR-11: 音效系统
- 射击音效（区分玩家/敌方）
- 爆炸音效
- 道具拾取音效
- 背景音乐（循环播放，可关闭）
- 音量控制（0-100）

### FR-12: UI 系统
- **主菜单**：开始游戏、设置、关于
- **游戏 HUD**：生命、得分、关卡、暂停按钮
- **暂停菜单**：继续、重新开始、返回主菜单
- **游戏结束界面**：最终得分、最高分、重新开始
- **关卡过渡**：关卡名称、目标提示

### FR-13: 企业级代码质量
- TypeScript 严格模式（无 any）
- 单元测试覆盖率 ≥ 80%
- ESLint 零错误
- 所有公共 API 有 JSDoc 注释
- 代码评审通过

### FR-14: 性能优化
- 稳定 60 FPS（Chrome DevTools 验证）
- 对象池（子弹、粒子）
- 四叉树碰撞检测
- 资源预加载
- 生产构建 < 500KB gzipped

### FR-15: 可扩展性
- 插件式关卡加载
- 可配置游戏参数
- 事件驱动架构
- 依赖注入设计

---

## 七、迁移与兼容

### 7.1 数据迁移

**本项目为全新开发，无数据迁移需求。**

但需考虑版本演进：
- 使用语义化版本（SemVer）
- 关卡数据包含 `schemaVersion` 字段
- 升级时提供数据转换工具

### 7.2 浏览器兼容

**最低要求**：
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**兼容策略**：
- 使用 Vite 自动 polyfill
- 不支持 IE11

---

## 八、非功能需求

### 8.1 性能
- 初始加载时间 < 2 秒（Fast 3G）
- 关卡切换时间 < 500ms
- 帧率稳定 55-60 FPS
- 内存占用 < 100MB

### 8.2 可维护性
- 代码复杂度 < 10（ESLint complexity）
- 函数最大行数 < 50
- 类最大行数 < 300
- 测试覆盖率 ≥ 80%

### 8.3 可用性
- 学习曲线 < 5 分钟（新手教程）
- 操作响应延迟 < 50ms
- 错误提示友好

---

## 九、验收标准

### 9.1 功能验收
- [ ] 所有功能点（FR-1 到 FR-15）实现并通过测试
- [ ] 至少 5 个关卡可完整游玩
- [ ] 所有音效正常播放
- [ ] 所有 UI 交互正常

### 9.2 质量验收
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] ESLint 零错误
- [ ] TypeScript 编译零错误
- [ ] Chrome Lighthouse 性能评分 ≥ 90

### 9.3 性能验收
- [ ] Chrome DevTools Performance 分析帧率 55-60 FPS
- [ ] 初始加载时间 < 2 秒（Fast 3G）
- [ ] 生产构建 < 500KB gzipped

### 9.4 文档验收
- [ ] README.md 包含快速开始、开发指南
- [ ] API 文档完整（JSDoc 自动生成）
- [ ] 关卡配置格式文档
- [ ] 架构设计文档

---

## 十、项目结构

```
tank-battle/
├── src/
│   ├── core/              # 核心引擎
│   │   ├── Engine.ts
│   │   ├── Entity.ts
│   │   ├── Component.ts
│   │   └── System.ts
│   ├── systems/           # 游戏系统
│   │   ├── RenderSystem.ts
│   │   ├── PhysicsSystem.ts
│   │   ├── CollisionSystem.ts
│   │   ├── AISystem.ts
│   │   └── ParticleSystem.ts
│   ├── entities/          # 游戏实体
│   │   ├── Tank.ts
│   │   ├── Bullet.ts
│   │   ├── Obstacle.ts
│   │   └── Powerup.ts
│   ├── components/        # 组件
│   │   ├── Transform.ts
│   │   ├── Velocity.ts
│   │   ├── Sprite.ts
│   │   └── Collider.ts
│   ├── states/            # 游戏状态
│   │   ├── StateManager.ts
│   │   ├── MainMenuState.ts
│   │   ├── PlayingState.ts
│   │   └── GameOverState.ts
│   ├── services/          # 全局服务
│   │   ├── AssetLoader.ts
│   │   ├── AudioManager.ts
│   │   ├── InputManager.ts
│   │   └── LevelLoader.ts
│   ├── utils/             # 工具类
│   │   ├── QuadTree.ts
│   │   ├── ObjectPool.ts
│   │   └── Vector2D.ts
│   ├── ui/                # UI 组件
│   │   ├── HUD.ts
│   │   ├── Menu.ts
│   │   └── Dialog.ts
│   └── main.ts            # 入口文件
├── assets/
│   ├── sprites/           # 精灵图
│   ├── sounds/            # 音效
│   └── levels/            # 关卡配置
│       ├── level-1.json
│       ├── level-2.json
│       └── ...
├── tests/
│   ├── unit/              # 单元测试
│   └── integration/       # 集成测试
├── docs/
│   ├── api/               # API 文档
│   ├── architecture.md    # 架构设计
│   └── level-format.md    # 关卡格式
├── public/
│   └── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── vitest.config.ts
└── README.md
```

---

## 十一、技术栈

### 11.1 核心技术
- **TypeScript 5.x**（严格模式）
- **Canvas 2D API**（渲染）
- **Web Audio API**（音效）

### 11.2 开发工具
- **Vite 5.x**（构建工具）
- **Vitest**（单元测试）
- **ESLint + Prettier**（代码规范）
- **TypeDoc**（文档生成）

### 11.3 依赖库
- 无运行时依赖（纯原生实现）
- 开发依赖：
  - `typescript`
  - `vite`
  - `vitest`
  - `eslint`
  - `prettier`
  - `typedoc`

---

## 十二、开发计划（估算）

### Phase 1: 核心引擎（2 周）
- 搭建项目脚手架
- 实现 ECS 架构
- 基础渲染系统
- 输入管理系统

### Phase 2: 游戏机制（3 周）
- 玩家坦克控制
- 敌方 AI
- 碰撞检测系统
- 子弹系统

### Phase 3: 关卡与地形（2 周）
- 关卡加载系统
- 障碍物系统
- 地形渲染
- 关卡配置格式

### Phase 4: 视觉与音效（2 周）
- 粒子系统
- 音效系统
- UI 系统
- 动画效果

### Phase 5: 优化与测试（2 周）
- 性能优化
- 单元测试
- 集成测试
- 文档编写

**总计**：约 11 周

---

## 十三、风险与挑战

### 13.1 技术风险
- **性能瓶颈**：大量实体时帧率下降
  - **缓解**：对象池、四叉树、脏矩形渲染
- **音效卡顿**：iOS Safari Web Audio 延迟
  - **缓解**：预加载、AudioContext 优化

### 13.2 设计风险
- **关卡设计**：难度曲线不平滑
  - **缓解**：迭代测试、收集反馈
- **AI 表现**：过强或过弱
  - **缓解**：可配置参数、多轮调优

---

## 十四、参考资料

- [HTML5 Canvas 教程](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
- [Game Programming Patterns](https://gameprogrammingpatterns.com/)
- [经典坦克大战玩法分析](https://en.wikipedia.org/wiki/Battle_City)

---

**文档版本**: 2.0（重档）  
**最后更新**: 2024-09-24  

## 产品定义

### 产品名称
坦克大作战（Tank Battle）

### 产品类型
单人 2D 俯视角动作射击游戏

### 目标用户
- 休闲游戏玩家：喜欢经典街机风格游戏
- 怀旧玩家：对 FC 时代坦克大战有情怀
- 轻度策略玩家：享受即时反应与策略思考的结合
- 年龄范围：12-45 岁
- 游戏技能：新手到中级玩家

### 产品定位
一款致敬经典但具备现代品质的网页游戏：
- **经典玩法**：保留坦克大战的核心机制
- **现代体验**：流畅画面、精致特效、响应式操作
- **企业级质量**：专业代码架构、完整测试覆盖
- **可扩展性**：支持关卡编辑、便于二次开发

### 核心价值
1. **即时快感**：爽快的射击体验与爆炸特效
2. **策略深度**：多样化的敌军 AI 与关卡设计
3. **成就感**：关卡挑战与高分竞争
4. **怀旧情怀**：经典游戏的现代重制

---

## 用户与角色

### 用户角色定义

#### 角色 1：玩家（Player）
- **描述**：游戏的实际操作者
- **目标**：
  - 通过所有关卡
  - 获得高分
  - 保护基地不被摧毁
  - 享受游戏乐趣
- **使用场景**：
  - 碎片时间娱乐（10-30 分钟）
  - 午休放松
  - 通勤途中（移动端，未来功能）
- **技能水平**：
  - 新手：熟悉基本操作需要 2-5 分钟
  - 熟练玩家：可以挑战更高难度关卡
- **期望**：
  - 操作响应快速（< 50ms）
  - 画面流畅（60 FPS）
  - 学习曲线平滑
  - 有明确的进度反馈

#### 角色 2：开发者（Developer）
- **描述**：基于本游戏进行二次开发的技术人员
- **目标**：
  - 快速理解代码架构
  - 添加新功能（新武器、新敌军类型）
  - 修改游戏参数
  - 设计新关卡
- **使用场景**：
  - 学习游戏开发最佳实践
  - 作为技术面试作品
  - 教学示例项目
- **技能水平**：
  - 熟悉 TypeScript
  - 了解 Canvas API
  - 理解基本游戏开发概念
- **期望**：
  - 清晰的代码注释
  - 完整的 API 文档
  - 模块化设计，易于扩展
  - 详细的架构说明

### 用户故事

#### 故事 1：新手玩家初次体验
**作为** 一名从未玩过坦克大战的新手玩家  
**我想要** 快速了解游戏规则并开始游戏  
**以便于** 在短时间内体验到游戏乐趣

**验收标准**：
- 主菜单提供"开始游戏"和"操作说明"选项
- 第一关为教程关卡，难度较低
- 屏幕上显示清晰的操作提示
- 5 分钟内可以完成第一关

#### 故事 2：熟练玩家挑战高分
**作为** 一名熟练玩家  
**我想要** 在每关获得尽可能高的分数  
**以便于** 刷新自己的最高记录并与他人比较

**验收标准**：
- 实时显示当前得分和最高分
- 连击系统奖励快速击杀
- 得分明细清晰（击杀、连击、关卡奖励）
- 最高分持久化保存

#### 故事 3：开发者添加新武器
**作为** 一名开发者  
**我想要** 为坦克添加新的武器类型（如激光炮）  
**以便于** 丰富游戏玩法

**验收标准**：
- 武器系统采用组件化设计
- 添加新武器只需扩展 Weapon 类
- 配置文件中可以定义武器参数
- 不需要修改核心引擎代码

#### 故事 4：开发者设计新关卡
**作为** 一名开发者  
**我想要** 设计自己的关卡布局和敌军配置  
**以便于** 创造独特的游戏体验

**验收标准**：
- 关卡使用 JSON 格式配置
- 文档详细说明关卡配置格式
- 添加新关卡无需重新编译
- 刷新页面即可加载新关卡

---

**负责人**: Agent-DH