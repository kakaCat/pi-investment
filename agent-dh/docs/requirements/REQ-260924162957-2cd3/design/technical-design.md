---
requirement_refs:
  - FR-1
  - FR-2
  - FR-3
  - FR-4
  - FR-5
  - FR-6
  - FR-7
  - FR-8
  - FR-9
  - FR-10
  - FR-11
  - FR-12
  - FR-13
  - FR-14
  - FR-15
---

# 坦克大作战游戏 - 技术设计文档

**需求ID**: REQ-260924162957-2cd3  
**类型**: feature  
**难度**: expert  
**文档版本**: 1.0  
**创建时间**: 2024-09-24

---

## 一、目标

**代码层面的可证伪目标**：

实现一个基于 TypeScript + Canvas 2D 的坦克大作战游戏，满足以下技术指标：

1. **运行时性能**：稳定 60 FPS（Chrome DevTools Performance 验证）
2. **代码质量**：单元测试覆盖率 ≥ 80%，ESLint 零错误
3. **构建产物**：生产构建 < 500KB gzipped
4. **架构可扩展**：支持插件式关卡加载，新增关卡无需修改核心代码

---

## 二、核心架构设计

### 2.1 游戏引擎架构（serves: FR-1, FR-2, FR-3, FR-4）

**架构决策**：轻量级 ECS（Entity-Component-System）+ Service Locator

**核心接口**：

```typescript
// 实体系统
interface Entity {
  id: string;
  active: boolean;
  components: Map<string, Component>;
  
  addComponent(component: Component): void;
  getComponent<T extends Component>(type: string): T | null;
  removeComponent(type: string): void;
}

// 组件基类
interface Component {
  type: string;
  enabled: boolean;
}

// 系统基类
interface System {
  priority: number;
  update(entities: Entity[], deltaTime: number): void;
}

// 游戏引擎
class GameEngine {
  private entities: Map<string, Entity>;
  private systems: System[];
  
  constructor(config: GameConfig);
  
  addEntity(entity: Entity): void;
  removeEntity(id: string): void;
  
  addSystem(system: System): void;
  
  start(): void;
  pause(): void;
  resume(): void;
  
  update(deltaTime: number): void;
}
```

**改动文件**：
- `src/core/Engine.ts` - 游戏引擎主循环
- `src/core/Entity.ts` - 实体管理
- `src/core/Component.ts` - 组件基类
- `src/core/System.ts` - 系统基类

---

### 2.2 核心系统设计（serves: FR-1, FR-2, FR-3, FR-4, FR-5）

**系统清单**：

```typescript
// 渲染系统
class RenderSystem implements System {
  priority = 100;
  
  update(entities: Entity[], deltaTime: number): void {
    // 按 z-index 排序
    // 绘制精灵
    // 绘制粒子特效
  }
}

// 物理系统
class PhysicsSystem implements System {
  priority = 10;
  
  update(entities: Entity[], deltaTime: number): void {
    // 更新速度与位置
    // 应用边界限制
  }
}

// 碰撞检测系统
class CollisionSystem implements System {
  priority = 20;
  private quadTree: QuadTree;
  
  update(entities: Entity[], deltaTime: number): void {
    // 四叉树空间分区
    // AABB 碰撞检测
    // 触发碰撞事件
  }
}

// AI 系统
class AISystem implements System {
  priority = 15;
  
  update(entities: Entity[], deltaTime: number): void {
    // 巡逻型 AI：随机移动
    // 追击型 AI：A* 寻路
    // 狙击型 AI：保持距离
  }
}

// 粒子系统
class ParticleSystem implements System {
  priority = 90;
  private pool: ObjectPool<Particle>;
  
  update(entities: Entity[], deltaTime: number): void {
    // 更新粒子生命周期
    // 回收到对象池
  }
}
```

**改动文件**：
- `src/systems/RenderSystem.ts`
- `src/systems/PhysicsSystem.ts`
- `src/systems/CollisionSystem.ts`
- `src/systems/AISystem.ts`
- `src/systems/ParticleSystem.ts`

---

### 2.3 组件设计（serves: FR-1, FR-2, FR-3, FR-9）

**核心组件**：

```typescript
// 位置与变换
class Transform implements Component {
  type = 'Transform';
  position: Vector2D;
  rotation: number;
  scale: Vector2D;
}

// 速度
class Velocity implements Component {
  type = 'Velocity';
  linear: Vector2D;
  angular: number;
}

// 精灵渲染
class Sprite implements Component {
  type = 'Sprite';
  texture: string;
  frame: number;
  zIndex: number;
}

// 碰撞体
class Collider implements Component {
  type = 'Collider';
  shape: 'box' | 'circle';
  width: number;
  height: number;
  radius: number;
  layer: number;  // 用于分层检测
}

// AI 行为
class AIBehavior implements Component {
  type = 'AIBehavior';
  behaviorType: 'patrol' | 'chase' | 'sniper';
  target: Entity | null;
  state: any;
}

// 武器
class Weapon implements Component {
  type = 'Weapon';
  fireRate: number;
  lastFireTime: number;
  bulletSpeed: number;
}

// 生命值
class Health implements Component {
  type = 'Health';
  current: number;
  max: number;
}
```

**改动文件**：
- `src/components/Transform.ts`
- `src/components/Velocity.ts`
- `src/components/Sprite.ts`
- `src/components/Collider.ts`
- `src/components/AIBehavior.ts`
- `src/components/Weapon.ts`
- `src/components/Health.ts`

---

### 2.4 状态管理设计（serves: FR-12）

**状态机模式**：

```typescript
enum GameState {
  Boot,
  MainMenu,
  Playing,
  Paused,
  LevelComplete,
  GameOver
}

interface State {
  enter(): void;
  update(deltaTime: number): void;
  exit(): void;
}

class StateManager {
  private current: GameState;
  private states: Map<GameState, State>;
  
  transition(to: GameState): void {
    this.states.get(this.current)?.exit();
    this.current = to;
    this.states.get(to)?.enter();
  }
}

// 游戏中状态
class PlayingState implements State {
  enter(): void {
    // 初始化关卡
    // 创建玩家坦克
    // 生成敌军
  }
  
  update(deltaTime: number): void {
    // 更新所有系统
    // 检查胜利/失败条件
  }
  
  exit(): void {
    // 清理实体
    // 保存进度
  }
}
```

**改动文件**：
- `src/states/StateManager.ts`
- `src/states/BootState.ts`
- `src/states/MainMenuState.ts`
- `src/states/PlayingState.ts`
- `src/states/PausedState.ts`
- `src/states/LevelCompleteState.ts`
- `src/states/GameOverState.ts`

---

### 2.5 资源管理设计（serves: FR-11）

**预加载 + 懒加载混合策略**：

```typescript
interface AssetManifest {
  images: { key: string; url: string }[];
  sounds: { key: string; url: string }[];
  levels: { key: string; url: string }[];
}

class AssetLoader {
  private cache: Map<string, any>;
  
  async preload(manifest: AssetManifest): Promise<void> {
    // 批量加载核心资源
    // 显示进度条
    await Promise.all([
      this.loadImages(manifest.images),
      this.loadSounds(manifest.sounds)
    ]);
  }
  
  async loadLevel(levelId: number): Promise<LevelData> {
    const key = `level-${levelId}`;
    if (this.cache.has(key)) {
      return this.cache.get(key);
    }
    
    const response = await fetch(`/assets/levels/level-${levelId}.json`);
    const data = await response.json();
    this.cache.set(key, data);
    return data;
  }
  
  get<T>(key: string): T {
    return this.cache.get(key);
  }
}

class AudioManager {
  private context: AudioContext;
  private buffers: Map<string, AudioBuffer>;
  private volume: number = 1.0;
  
  play(key: string, options?: { loop?: boolean; volume?: number }): void {
    const buffer = this.buffers.get(key);
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.loop = options?.loop || false;
    
    const gainNode = this.context.createGain();
    gainNode.gain.value = (options?.volume || 1.0) * this.volume;
    
    source.connect(gainNode).connect(this.context.destination);
    source.start(0);
  }
  
  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
  }
}
```

**改动文件**：
- `src/services/AssetLoader.ts`
- `src/services/AudioManager.ts`

---

### 2.6 关卡系统设计（serves: FR-8）

**关卡数据格式**：

```typescript
interface LevelData {
  id: number;
  name: string;
  width: number;       // 格子数（26）
  height: number;      // 格子数（26）
  tileSize: number;    // 每格像素（32）
  
  // 地形编码（0=空地, 1=砖墙, 2=钢墙, 3=水域, 4=草地, 5=基地）
  tiles: string;       // 压缩字符串："0000112220000..."
  
  // 敌军配置
  enemies: {
    type: 'patrol' | 'chase' | 'sniper';
    x: number;
    y: number;
    delay?: number;    // 出场延迟（秒）
  }[];
  
  // 道具生成点
  powerupSpawns: {
    x: number;
    y: number;
    spawnTime: number;  // 游戏开始后多少秒
  }[];
  
  // 关卡目标
  objectives: {
    type: 'eliminate_all' | 'protect_base';
    timeLimit?: number;  // 秒
  };
}

class LevelLoader {
  async load(levelId: number): Promise<Level> {
    const data = await assetLoader.loadLevel(levelId);
    
    // 解析地形
    const tiles = this.parseTiles(data.tiles, data.width, data.height);
    
    // 创建关卡实例
    return new Level(data, tiles);
  }
  
  private parseTiles(encoded: string, width: number, height: number): Tile[][] {
    const tiles: Tile[][] = [];
    let index = 0;
    
    for (let y = 0; y < height; y++) {
      tiles[y] = [];
      for (let x = 0; x < width; x++) {
        const type = parseInt(encoded[index++]);
        tiles[y][x] = this.createTile(type, x, y);
      }
    }
    
    return tiles;
  }
}
```

**示例关卡配置**（`assets/levels/level-1.json`）：

```json
{
  "id": 1,
  "name": "Tutorial",
  "width": 26,
  "height": 26,
  "tileSize": 32,
  "tiles": "0000000000000000000000000000111111111111111111111111222222222222222222222222...",
  "enemies": [
    { "type": "patrol", "x": 10, "y": 5 },
    { "type": "patrol", "x": 15, "y": 5 }
  ],
  "powerupSpawns": [
    { "x": 13, "y": 13, "spawnTime": 30 }
  ],
  "objectives": {
    "type": "eliminate_all",
    "timeLimit": 180
  }
}
```

**改动文件**：
- `src/services/LevelLoader.ts`
- `src/entities/Level.ts`
- `assets/levels/level-1.json` ~ `level-5.json`

---

### 2.7 性能优化设计（serves: FR-14）

**对象池**：

```typescript
class ObjectPool<T> {
  private available: T[] = [];
  private inUse: Set<T> = new Set();
  
  constructor(
    private factory: () => T,
    private reset: (obj: T) => void,
    initialSize: number = 50
  ) {
    for (let i = 0; i < initialSize; i++) {
      this.available.push(factory());
    }
  }
  
  acquire(): T {
    let obj = this.available.pop();
    if (!obj) {
      obj = this.factory();
    }
    this.inUse.add(obj);
    return obj;
  }
  
  release(obj: T): void {
    if (this.inUse.has(obj)) {
      this.reset(obj);
      this.inUse.delete(obj);
      this.available.push(obj);
    }
  }
}

// 使用示例
const bulletPool = new ObjectPool(
  () => new Bullet(),
  (bullet) => {
    bullet.active = false;
    bullet.position.set(0, 0);
  },
  100  // 预创建 100 个子弹
);
```

**四叉树空间分区**：

```typescript
class QuadTree {
  private maxObjects = 10;
  private maxLevels = 5;
  private level: number;
  private bounds: Rectangle;
  private objects: Entity[] = [];
  private nodes: QuadTree[] = [];
  
  constructor(level: number, bounds: Rectangle) {
    this.level = level;
    this.bounds = bounds;
  }
  
  clear(): void {
    this.objects = [];
    for (const node of this.nodes) {
      node.clear();
    }
    this.nodes = [];
  }
  
  insert(entity: Entity): void {
    if (this.nodes.length > 0) {
      const index = this.getIndex(entity);
      if (index !== -1) {
        this.nodes[index].insert(entity);
        return;
      }
    }
    
    this.objects.push(entity);
    
    if (this.objects.length > this.maxObjects && this.level < this.maxLevels) {
      if (this.nodes.length === 0) {
        this.split();
      }
      
      // 重新分配对象
      let i = 0;
      while (i < this.objects.length) {
        const index = this.getIndex(this.objects[i]);
        if (index !== -1) {
          this.nodes[index].insert(this.objects.splice(i, 1)[0]);
        } else {
          i++;
        }
      }
    }
  }
  
  retrieve(entity: Entity): Entity[] {
    const returnObjects: Entity[] = [];
    const index = this.getIndex(entity);
    
    if (index !== -1 && this.nodes.length > 0) {
      returnObjects.push(...this.nodes[index].retrieve(entity));
    }
    
    returnObjects.push(...this.objects);
    return returnObjects;
  }
  
  private split(): void {
    const subWidth = this.bounds.width / 2;
    const subHeight = this.bounds.height / 2;
    const x = this.bounds.x;
    const y = this.bounds.y;
    
    this.nodes[0] = new QuadTree(this.level + 1, new Rectangle(x + subWidth, y, subWidth, subHeight));
    this.nodes[1] = new QuadTree(this.level + 1, new Rectangle(x, y, subWidth, subHeight));
    this.nodes[2] = new QuadTree(this.level + 1, new Rectangle(x, y + subHeight, subWidth, subHeight));
    this.nodes[3] = new QuadTree(this.level + 1, new Rectangle(x + subWidth, y + subHeight, subWidth, subHeight));
  }
  
  private getIndex(entity: Entity): number {
    // 确定实体属于哪个象限
    // 返回 0-3 或 -1（跨越多个象限）
  }
}
```

**改动文件**：
- `src/utils/ObjectPool.ts`
- `src/utils/QuadTree.ts`
- `src/systems/CollisionSystem.ts`（集成四叉树）

---

### 2.8 输入管理设计（serves: FR-1）

```typescript
class InputManager {
  private keys: Set<string> = new Set();
  private mouse: {
    x: number;
    y: number;
    buttons: Set<number>;
  };
  
  constructor(canvas: HTMLCanvasElement) {
    this.setupKeyboardListeners();
    this.setupMouseListeners(canvas);
  }
  
  isKeyPressed(key: string): boolean {
    return this.keys.has(key);
  }
  
  isMouseButtonPressed(button: number): boolean {
    return this.mouse.buttons.has(button);
  }
  
  getMousePosition(): { x: number; y: number } {
    return { x: this.mouse.x, y: this.mouse.y };
  }
  
  private setupKeyboardListeners(): void {
    window.addEventListener('keydown', (e) => {
      this.keys.add(e.key.toLowerCase());
    });
    
    window.addEventListener('keyup', (e) => {
      this.keys.delete(e.key.toLowerCase());
    });
  }
}
```

**改动文件**：
- `src/services/InputManager.ts`

---

### 2.9 UI 系统设计（serves: FR-12）

```typescript
class UIManager {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  
  renderHUD(state: GameState): void {
    // 生命值
    this.drawLives(state.lives, 10, 10);
    
    // 得分
    this.drawText(`Score: ${state.score}`, 10, 40, '20px Arial', '#fff');
    
    // 关卡
    this.drawText(`Level: ${state.currentLevel}`, 10, 70, '20px Arial', '#fff');
    
    // 暂停按钮
    if (!state.isPaused) {
      this.drawButton('Pause [P]', 700, 10, 90, 30);
    }
  }
  
  renderMenu(options: MenuOption[]): void {
    // 绘制菜单背景
    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    
    // 标题
    this.drawText('TANK BATTLE', 400, 100, '48px Arial', '#ff0', 'center');
    
    // 菜单选项
    options.forEach((option, index) => {
      const y = 250 + index * 60;
      this.drawButton(option.label, 300, y, 200, 50);
    });
  }
  
  private drawLives(lives: number, x: number, y: number): void {
    for (let i = 0; i < lives; i++) {
      // 绘制坦克小图标
      this.ctx.drawImage(tankIcon, x + i * 30, y, 24, 24);
    }
  }
}
```

**改动文件**：
- `src/ui/UIManager.ts`
- `src/ui/HUD.ts`
- `src/ui/Menu.ts`

---

## 三、数据契约

### 3.1 游戏配置（serves: FR-13）

```typescript
interface GameConfig {
  canvas: {
    width: number;        // 800
    height: number;       // 600
    backgroundColor: string;
  };
  
  physics: {
    maxVelocity: number;  // 300 px/s
  };
  
  player: {
    speed: number;        // 150 px/s
    fireRate: number;     // 500 ms
    maxLives: number;     // 3
    bulletSpeed: number;  // 400 px/s
  };
  
  enemy: {
    types: {
      patrol: { speed: number; fireRate: number; health: number };
      chase: { speed: number; fireRate: number; health: number };
      sniper: { speed: number; fireRate: number; health: number };
    };
  };
  
  scoring: {
    enemyKill: number;        // 100
    comboBonus: number;       // 50
    levelComplete: number;    // 500
  };
}
```

### 3.2 持久化数据（serves: FR-7）

```typescript
interface SaveData {
  highScore: number;
  settings: {
    volume: number;       // 0-1
    musicEnabled: boolean;
    sfxEnabled: boolean;
  };
  unlockedLevels: number[];
}

class StorageManager {
  private key = 'tank-battle-save';
  
  load(): SaveData {
    const json = localStorage.getItem(this.key);
    return json ? JSON.parse(json) : this.getDefaultSave();
  }
  
  save(data: SaveData): void {
    localStorage.setItem(this.key, JSON.stringify(data));
  }
  
  private getDefaultSave(): SaveData {
    return {
      highScore: 0,
      settings: {
        volume: 1.0,
        musicEnabled: true,
        sfxEnabled: true
      },
      unlockedLevels: [1]
    };
  }
}
```

---

## 四、接口定义

### 4.1 公共 API（serves: FR-15）

```typescript
class TankBattleGame {
  constructor(containerId: string, config?: Partial<GameConfig>);
  
  // 生命周期
  start(): void;
  pause(): void;
  resume(): void;
  restart(): void;
  destroy(): void;
  
  // 关卡控制
  loadLevel(levelId: number): Promise<void>;
  nextLevel(): void;
  
  // 事件系统
  on(event: GameEvent, callback: Function): void;
  off(event: GameEvent, callback: Function): void;
  
  // 配置
  setVolume(volume: number): void;
  getState(): GameStateSnapshot;
}

enum GameEvent {
  LevelStart = 'level:start',
  LevelComplete = 'level:complete',
  GameOver = 'game:over',
  ScoreChange = 'score:change',
  LivesChange = 'lives:change',
  EnemyDestroyed = 'enemy:destroyed'
}

// 使用示例
const game = new TankBattleGame('game-container', {
  canvas: { width: 800, height: 600 }
});

game.on(GameEvent.LevelComplete, (level: number) => {
  console.log(`Completed level ${level}`);
});

game.start();
```

---

## 五、测试策略（serves: FR-13）

### 5.1 单元测试

```typescript
// tests/unit/QuadTree.test.ts
describe('QuadTree', () => {
  it('should insert entities correctly', () => {
    const tree = new QuadTree(0, new Rectangle(0, 0, 800, 600));
    const entity = createMockEntity(100, 100);
    
    tree.insert(entity);
    const retrieved = tree.retrieve(entity);
    
    expect(retrieved).toContain(entity);
  });
  
  it('should split when max objects exceeded', () => {
    // ...
  });
});

// tests/unit/ObjectPool.test.ts
describe('ObjectPool', () => {
  it('should reuse objects', () => {
    const pool = new ObjectPool(() => ({}), () => {});
    const obj1 = pool.acquire();
    pool.release(obj1);
    const obj2 = pool.acquire();
    
    expect(obj1).toBe(obj2);
  });
});
```

### 5.2 集成测试

```typescript
// tests/integration/Collision.test.ts
describe('Collision System', () => {
  it('should detect tank-bullet collision', async () => {
    const game = new TankBattleGame('test-container');
    await game.loadLevel(1);
    
    // 创建测试场景
    const tank = createTank(100, 100);
    const bullet = createBullet(100, 50, { vy: 10 });
    
    // 模拟碰撞
    game.update(50); // 50ms
    
    expect(tank.health.current).toBeLessThan(tank.health.max);
  });
});
```

### 5.3 性能测试

```typescript
// tests/performance/FPS.test.ts
describe('Performance', () => {
  it('should maintain 60 FPS with 50 entities', () => {
    const game = new TankBattleGame('test-container');
    
    // 创建 50 个实体
    for (let i = 0; i < 50; i++) {
      game.addEntity(createEnemy());
    }
    
    const frameTime = measureFrameTime(game, 60); // 60 帧
    expect(frameTime).toBeLessThan(16.67); // < 16.67ms per frame
  });
});
```

**测试覆盖目标**：
- 核心引擎：90%
- 系统（System）：85%
- 工具类：80%
- UI：60%（渲染逻辑难测）

---

## 六、构建与部署

### 6.1 构建配置（serves: FR-14）

**vite.config.ts**：

```typescript
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    target: 'esnext',
    minify: 'terser',
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor': ['tslib'],
          'core': [
            './src/core/Engine.ts',
            './src/core/Entity.ts',
            './src/core/System.ts'
          ]
        }
      }
    },
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true
      }
    }
  },
  
  optimizeDeps: {
    include: []  // 无外部依赖
  }
});
```

**package.json 脚本**：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "lint": "eslint src --ext .ts",
    "lint:fix": "eslint src --ext .ts --fix"
  }
}
```

### 6.2 代码规范

**eslint.config.js**：

```javascript
export default [
  {
    files: ['src/**/*.ts'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/explicit-function-return-type': 'warn',
      'complexity': ['error', 10],
      'max-lines-per-function': ['error', 50],
      'max-lines': ['error', 300]
    }
  }
];
```

---

## 七、验收口径

### 7.1 功能验收命令（serves: FR-1 ~ FR-15）

```bash
# 1. 启动开发服务器
npm run dev
# 预期：http://localhost:5173 显示游戏主菜单

# 2. 操作验证
# - 使用 WASD 控制坦克移动
# - 按空格键发射子弹，听到射击音效
# - 敌方坦克自动移动并攻击
# - 击毁坦克显示爆炸效果
# - 完成关卡显示过渡动画

# 3. 运行单元测试
npm test
# 预期：All tests passed (覆盖率 ≥ 80%)

# 4. 运行 ESLint
npm run lint
# 预期：0 errors, 0 warnings

# 5. 生产构建
npm run build
# 预期：dist/ 目录生成，总大小 < 500KB gzipped

# 6. 验证构建产物
du -sh dist/
gzip -c dist/assets/*.js | wc -c
# 预期：< 512000 字节（500KB）
```

### 7.2 性能验收命令（serves: FR-14）

```bash
# 使用 Chrome DevTools
# 1. 打开 Performance 面板
# 2. 录制游戏运行 10 秒
# 3. 查看 FPS 图表
# 预期：稳定在 55-60 FPS，无大幅波动

# 检查点：
# - 平均帧时间 < 16.67ms
# - 主线程任务 < 10ms per frame
# - 内存占用 < 100MB
```

### 7.3 关卡系统验收（serves: FR-8）

```bash
# 1. 验证关卡配置可加载
curl http://localhost:5173/assets/levels/level-1.json
# 预期：返回 JSON 数据

# 2. 手动测试
# - 完成第 1 关，进入第 2 关
# - 验证关卡名称显示正确
# - 验证难度递增（敌军更多/更强）

# 3. 修改关卡配置测试
# - 编辑 assets/levels/level-1.json
# - 刷新页面
# - 预期：新配置立即生效（无需重新构建）
```

---

## 八、迁移与兼容

### 8.1 浏览器兼容

**最低要求**：
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**兼容策略**：
- Vite 自动 polyfill（target: 'esnext'）
- Canvas 2D API（广泛支持）
- Web Audio API（现代浏览器标准）
- 不支持 IE11（已终止支持）

### 8.2 关卡数据版本化

```typescript
interface LevelData {
  schemaVersion: number;  // 当前版本：1
  // ...
}

class LevelLoader {
  async load(levelId: number): Promise<Level> {
    const data = await assetLoader.loadLevel(levelId);
    
    // 版本检查与转换
    if (data.schemaVersion !== 1) {
      throw new Error(`Unsupported level schema version: ${data.schemaVersion}`);
    }
    
    return this.parseLevel(data);
  }
}
```

---

## 九、风险与依赖

### 9.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 性能瓶颈（大量实体） | 帧率下降 | 对象池 + 四叉树 + 脏矩形渲染 |
| iOS Safari 音效延迟 | 用户体验差 | AudioContext 预加载 + 触摸启动 |
| 碰撞检测精度不足 | 游戏性问题 | AABB + 四叉树足够精确 |

### 9.2 依赖项

**运行时依赖**：无（纯原生实现）

**开发依赖**：
```json
{
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vitest": "^1.0.0",
    "eslint": "^8.56.0",
    "@typescript-eslint/parser": "^6.19.0",
    "@typescript-eslint/eslint-plugin": "^6.19.0",
    "prettier": "^3.2.0"
  }
}
```

---

## 十、文档交付清单

### 10.1 必需文档

- [ ] `README.md` - 项目说明与快速开始
- [ ] `docs/API.md` - 公共 API 文档（JSDoc 自动生成）
- [ ] `docs/LEVEL_FORMAT.md` - 关卡配置格式说明
- [ ] `docs/ARCHITECTURE.md` - 架构设计详解

### 10.2 代码注释

所有公共 API 必须包含 JSDoc：

```typescript
/**
 * 游戏引擎主类
 * @example
 * const game = new TankBattleGame('container', { ... });
 * game.start();
 */
export class TankBattleGame {
  /**
   * 创建游戏实例
   * @param containerId - HTML 容器元素 ID
   * @param config - 游戏配置（可选）
   */
  constructor(containerId: string, config?: Partial<GameConfig>) {
    // ...
  }
  
  /**
   * 启动游戏
   * @throws {Error} 如果资源加载失败
   */
  start(): void {
    // ...
  }
}
```

---

## 附录：文件清单

### 核心引擎（7 个文件）
- `src/core/Engine.ts`
- `src/core/Entity.ts`
- `src/core/Component.ts`
- `src/core/System.ts`
- `src/core/EventEmitter.ts`
- `src/core/Vector2D.ts`
- `src/main.ts`

### 系统（5 个文件）
- `src/systems/RenderSystem.ts`
- `src/systems/PhysicsSystem.ts`
- `src/systems/CollisionSystem.ts`
- `src/systems/AISystem.ts`
- `src/systems/ParticleSystem.ts`

### 组件（7 个文件）
- `src/components/Transform.ts`
- `src/components/Velocity.ts`
- `src/components/Sprite.ts`
- `src/components/Collider.ts`
- `src/components/AIBehavior.ts`
- `src/components/Weapon.ts`
- `src/components/Health.ts`

### 实体（5 个文件）
- `src/entities/Tank.ts`
- `src/entities/Bullet.ts`
- `src/entities/Obstacle.ts`
- `src/entities/Powerup.ts`
- `src/entities/Level.ts`

### 状态（7 个文件）
- `src/states/StateManager.ts`
- `src/states/BootState.ts`
- `src/states/MainMenuState.ts`
- `src/states/PlayingState.ts`
- `src/states/PausedState.ts`
- `src/states/LevelCompleteState.ts`
- `src/states/GameOverState.ts`

### 服务（4 个文件）
- `src/services/AssetLoader.ts`
- `src/services/AudioManager.ts`
- `src/services/InputManager.ts`
- `src/services/LevelLoader.ts`
- `src/services/StorageManager.ts`

### 工具（3 个文件）
- `src/utils/QuadTree.ts`
- `src/utils/ObjectPool.ts`
- `src/utils/Rectangle.ts`

### UI（3 个文件）
- `src/ui/UIManager.ts`
- `src/ui/HUD.ts`
- `src/ui/Menu.ts`

### 配置与资源
- `assets/levels/level-1.json` ~ `level-5.json`（5 个）
- `assets/sprites/`（精灵图）
- `assets/sounds/`（音效）
- `public/index.html`
- `vite.config.ts`
- `tsconfig.json`
- `vitest.config.ts`
- `eslint.config.js`
- `package.json`

**总计约 50 个文件**（不含资源文件）

---

**文档结束**