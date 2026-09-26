---
requirement_refs:
  - FR-6
  - FR-7
  - FR-8
  - FR-9
  - FR-10
  - FR-13
---

# 数据模型设计文档

**需求ID**: REQ-260924162957-2cd3  
**文档类型**: 数据模型设计  
**版本**: 1.0  
**创建时间**: 2024-09-24

---

## 一、核心数据模型（serves: FR-6, FR-7, FR-8）

### 1.1 游戏配置（GameConfig）

```typescript
interface GameConfig {
  canvas: {
    width: number;              // 800
    height: number;             // 600
    backgroundColor: string;    // '#000000'
  };
  
  physics: {
    maxVelocity: number;        // 300 px/s
    friction: number;           // 0.98
  };
  
  player: {
    speed: number;              // 150 px/s
    rotationSpeed: number;      // 180 度/秒
    fireRate: number;           // 500 ms
    maxLives: number;           // 3
    bulletSpeed: number;        // 400 px/s
    bulletDamage: number;       // 1
  };
  
  enemy: {
    types: {
      patrol: EnemyConfig;
      chase: EnemyConfig;
      sniper: EnemyConfig;
    };
  };
  
  scoring: {
    enemyKill: number;          // 100
    comboBonus: number;         // 50
    comboWindow: number;        // 5000 ms
    levelComplete: number;      // 500
  };
}

interface EnemyConfig {
  speed: number;                // 移动速度
  fireRate: number;             // 射击间隔
  health: number;               // 生命值
  bulletSpeed: number;          // 子弹速度
  detectionRange: number;       // 侦测范围（像素）
  score: number;                // 击杀得分
}
```

### 1.2 组件数据模型（serves: FR-1, FR-2, FR-3, FR-9）

#### Transform（位置与变换）
```typescript
class Transform implements Component {
  type = 'Transform';
  enabled = true;
  
  position: Vector2D;           // 世界坐标
  rotation: number;             // 旋转角度（弧度）
  scale: Vector2D;              // 缩放（默认 1, 1）
  
  constructor(x: number, y: number) {
    this.position = new Vector2D(x, y);
    this.rotation = 0;
    this.scale = new Vector2D(1, 1);
  }
}
```

#### Velocity（速度）
```typescript
class Velocity implements Component {
  type = 'Velocity';
  enabled = true;
  
  linear: Vector2D;             // 线速度（px/s）
  angular: number;              // 角速度（rad/s）
  
  constructor() {
    this.linear = new Vector2D(0, 0);
    this.angular = 0;
  }
}
```

#### Sprite（精灵渲染）
```typescript
class Sprite implements Component {
  type = 'Sprite';
  enabled = true;
  
  texture: string;              // 纹理键名
  frame: number;                // 动画帧索引
  width: number;                // 宽度
  height: number;               // 高度
  zIndex: number;               // 渲染层级（越大越靠前）
  alpha: number;                // 透明度（0-1）
  tint: string;                 // 着色（CSS 颜色）
  
  constructor(texture: string, width: number, height: number) {
    this.texture = texture;
    this.frame = 0;
    this.width = width;
    this.height = height;
    this.zIndex = 0;
    this.alpha = 1.0;
    this.tint = '#ffffff';
  }
}
```

#### Collider（碰撞体）
```typescript
class Collider implements Component {
  type = 'Collider';
  enabled = true;
  
  shape: 'box' | 'circle';      // 碰撞形状
  width: number;                // 宽度（box）
  height: number;               // 高度（box）
  radius: number;               // 半径（circle）
  layer: number;                // 碰撞层（位掩码）
  isTrigger: boolean;           // 是否为触发器（不产生物理响应）
  
  constructor(shape: 'box' | 'circle', size: number) {
    this.shape = shape;
    if (shape === 'box') {
      this.width = size;
      this.height = size;
      this.radius = 0;
    } else {
      this.width = 0;
      this.height = 0;
      this.radius = size;
    }
    this.layer = 0;
    this.isTrigger = false;
  }
}
```

#### Health（生命值）（serves: FR-6）
```typescript
class Health implements Component {
  type = 'Health';
  enabled = true;
  
  current: number;              // 当前生命值
  max: number;                  // 最大生命值
  invulnerable: boolean;        // 是否无敌
  invulnerableUntil: number;    // 无敌持续到（时间戳）
  
  constructor(max: number) {
    this.current = max;
    this.max = max;
    this.invulnerable = false;
    this.invulnerableUntil = 0;
  }
  
  isDead(): boolean {
    return this.current <= 0;
  }
  
  takeDamage(amount: number): void {
    if (!this.invulnerable) {
      this.current = Math.max(0, this.current - amount);
    }
  }
  
  heal(amount: number): void {
    this.current = Math.min(this.max, this.current + amount);
  }
}
```

#### Weapon（武器）
```typescript
class Weapon implements Component {
  type = 'Weapon';
  enabled = true;
  
  fireRate: number;             // 射击间隔（ms）
  lastFireTime: number;         // 上次射击时间（时间戳）
  bulletSpeed: number;          // 子弹速度
  bulletDamage: number;         // 子弹伤害
  bulletType: string;           // 子弹类型
  ammo: number;                 // 弹药数（-1 = 无限）
  
  constructor(fireRate: number, bulletSpeed: number) {
    this.fireRate = fireRate;
    this.lastFireTime = 0;
    this.bulletSpeed = bulletSpeed;
    this.bulletDamage = 1;
    this.bulletType = 'normal';
    this.ammo = -1;
  }
  
  canFire(currentTime: number): boolean {
    return (
      this.enabled &&
      currentTime - this.lastFireTime >= this.fireRate &&
      (this.ammo === -1 || this.ammo > 0)
    );
  }
}
```

#### AIBehavior（AI 行为）（serves: FR-2）
```typescript
class AIBehavior implements Component {
  type = 'AIBehavior';
  enabled = true;
  
  behaviorType: 'patrol' | 'chase' | 'sniper';
  target: Entity | null;        // 追击目标
  state: AIState;               // AI 状态机
  detectionRange: number;       // 侦测范围
  lastDecisionTime: number;     // 上次决策时间
  decisionInterval: number;     // 决策间隔（ms）
  
  constructor(type: 'patrol' | 'chase' | 'sniper') {
    this.behaviorType = type;
    this.target = null;
    this.state = { type: 'idle' };
    this.detectionRange = 300;
    this.lastDecisionTime = 0;
    this.decisionInterval = 500;
  }
}

interface AIState {
  type: 'idle' | 'patrol' | 'chase' | 'attack' | 'evade';
  data?: any;
}
```

---

## 二、关卡数据模型（serves: FR-8）

### 2.1 关卡配置（LevelData）

```typescript
interface LevelData {
  id: number;                   // 关卡 ID
  name: string;                 // 关卡名称
  schemaVersion: number;        // 数据格式版本（当前 1）
  
  // 地图配置
  width: number;                // 地图宽度（格子数）
  height: number;               // 地图高度（格子数）
  tileSize: number;             // 每格像素大小
  
  // 地形编码
  tiles: string;                // 压缩字符串
  
  // 实体配置
  playerSpawn: { x: number; y: number };
  enemies: EnemySpawn[];
  powerupSpawns: PowerupSpawn[];
  
  // 关卡目标
  objectives: Objective;
  
  // 元数据
  difficulty: number;           // 难度系数（1-5）
  timeLimit?: number;           // 时间限制（秒）
  parScore?: number;            // 标准分数
}

interface EnemySpawn {
  type: 'patrol' | 'chase' | 'sniper';
  x: number;                    // 格子坐标
  y: number;
  delay?: number;               // 延迟出场（秒）
  facing?: number;              // 初始朝向（度）
}

interface PowerupSpawn {
  type: 'life' | 'shield' | 'power' | 'freeze';
  x: number;
  y: number;
  spawnTime: number;            // 游戏开始后多少秒生成
  duration: number;             // 存在时长（秒）
}

interface Objective {
  type: 'eliminate_all' | 'protect_base' | 'survive';
  timeLimit?: number;           // 时间限制（秒）
  requiredKills?: number;       // 需击杀数
}
```

### 2.2 地形编码规则（serves: FR-9）

```
编码字符 → 地形类型：
'0' → 空地（可通行）
'1' → 砖墙（可摧毁）
'2' → 钢墙（不可摧毁）
'3' → 水域（不可通行）
'4' → 草地（视觉遮蔽）
'5' → 基地（需保护）

示例（5x5 地图）：
"0000011111222223333344444"
→ 解析为 5x5 网格：
┌─────┬─────┬─────┬─────┬─────┐
│  0  │  0  │  0  │  0  │  0  │  空地行
├─────┼─────┼─────┼─────┼─────┤
│  1  │  1  │  1  │  1  │  1  │  砖墙行
├─────┼─────┼─────┼─────┼─────┤
│  2  │  2  │  2  │  2  │  2  │  钢墙行
├─────┼─────┼─────┼─────┼─────┤
│  3  │  3  │  3  │  3  │  3  │  水域行
├─────┼─────┼─────┼─────┼─────┤
│  4  │  4  │  4  │  4  │  4  │  草地行
└─────┴─────┴─────┴─────┴─────┘
```

---

## 三、游戏状态模型（serves: FR-7）

### 3.1 运行时状态（GameState）

```typescript
interface GameState {
  // 关卡进度
  currentLevel: number;
  levelStartTime: number;       // 关卡开始时间（时间戳）
  
  // 玩家状态
  lives: number;                // 剩余生命数
  score: number;                // 当前得分
  combo: number;                // 连击数
  lastKillTime: number;         // 上次击杀时间
  
  // 全局状态
  isPaused: boolean;
  gameOver: boolean;
  victory: boolean;
  
  // 统计数据
  totalKills: number;
  totalShots: number;
  accuracy: number;             // 命中率（%）
}
```

### 3.2 持久化数据（SaveData）

```typescript
interface SaveData {
  // 进度
  highScore: number;
  unlockedLevels: number[];
  completedLevels: number[];
  
  // 设置
  settings: {
    volume: number;             // 0-1
    musicEnabled: boolean;
    sfxEnabled: boolean;
    difficulty: 'easy' | 'normal' | 'hard';
  };
  
  // 统计
  stats: {
    totalPlayTime: number;      // 总游戏时间（秒）
    totalKills: number;
    totalDeaths: number;
    bestAccuracy: number;
  };
  
  // 元数据
  version: string;              // 存档版本
  lastPlayed: number;           // 最后游玩时间（时间戳）
}
```

---

## 四、事件数据模型

### 4.1 游戏事件（GameEvent）

```typescript
enum GameEventType {
  // 生命周期
  LevelStart = 'level:start',
  LevelComplete = 'level:complete',
  GameOver = 'game:over',
  
  // 实体事件
  EntityCreated = 'entity:created',
  EntityDestroyed = 'entity:destroyed',
  
  // 碰撞事件
  CollisionEnter = 'collision:enter',
  CollisionExit = 'collision:exit',
  
  // 玩家事件
  PlayerHit = 'player:hit',
  PlayerDied = 'player:died',
  PlayerRespawn = 'player:respawn',
  
  // 敌军事件
  EnemySpawned = 'enemy:spawned',
  EnemyDestroyed = 'enemy:destroyed',
  
  // 道具事件
  PowerupSpawned = 'powerup:spawned',
  PowerupCollected = 'powerup:collected',
  PowerupExpired = 'powerup:expired',
  
  // 得分事件
  ScoreChange = 'score:change',
  ComboStart = 'combo:start',
  ComboEnd = 'combo:end',
  
  // 生命事件
  LivesChange = 'lives:change'
}

interface GameEvent {
  type: GameEventType;
  timestamp: number;
  data: any;
}
```

---

## 五、数据约束与验证（serves: FR-13）

### 5.1 类型约束

```typescript
// 使用 TypeScript 严格模式
// tsconfig.json:
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true
  }
}
```

### 5.2 运行时验证

```typescript
// 关卡数据验证
function validateLevelData(data: any): LevelData {
  // 必填字段检查
  if (!data.id || !data.name || !data.tiles) {
    throw new Error('Missing required level fields');
  }
  
  // 版本兼容检查
  if (data.schemaVersion !== 1) {
    throw new Error(`Unsupported schema version: ${data.schemaVersion}`);
  }
  
  // 地形数据长度检查
  const expectedLength = data.width * data.height;
  if (data.tiles.length !== expectedLength) {
    throw new Error(`Invalid tiles length: expected ${expectedLength}, got ${data.tiles.length}`);
  }
  
  return data as LevelData;
}
```

---

## 六、数据流图

```
用户输入
   ↓
InputManager (采集)
   ↓
Entity + Components (存储)
   ↓
Systems (处理)
   ↓
Events (通知)
   ↓
UI / Audio / Rendering (输出)
```

---

**文档版本**: 1.0  
**最后更新**: 2024-09-24
