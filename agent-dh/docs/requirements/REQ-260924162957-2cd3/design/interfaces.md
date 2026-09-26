---
requirement_refs:
  - FR-1
  - FR-11
  - FR-12
  - FR-15
---

# 接口设计文档

**需求ID**: REQ-260924162957-2cd3  
**文档类型**: 接口设计  
**版本**: 1.0  
**创建时间**: 2024-09-24

---

## 一、公共 API（serves: FR-15）

### 1.1 游戏实例接口

```typescript
/**
 * 坦克大作战游戏主类
 * @example
 * const game = new TankBattleGame('game-container', {
 *   canvas: { width: 800, height: 600 }
 * });
 * game.start();
 */
class TankBattleGame {
  /**
   * 创建游戏实例
   * @param containerId - HTML 容器元素 ID
   * @param config - 游戏配置（可选，使用默认配置）
   * @throws {Error} 容器元素不存在
   */
  constructor(containerId: string, config?: Partial<GameConfig>);
  
  /**
   * 启动游戏
   * 加载资源 → 进入主菜单
   * @throws {Error} 资源加载失败
   */
  start(): void;
  
  /**
   * 暂停游戏
   * 只在 Playing 状态有效
   */
  pause(): void;
  
  /**
   * 恢复游戏
   * 只在 Paused 状态有效
   */
  resume(): void;
  
  /**
   * 重新开始当前关卡
   */
  restart(): void;
  
  /**
   * 销毁游戏实例
   * 释放所有资源，移除事件监听
   */
  destroy(): void;
  
  /**
   * 加载指定关卡
   * @param levelId - 关卡 ID（1-5）
   * @throws {Error} 关卡不存在或加载失败
   */
  loadLevel(levelId: number): Promise<void>;
  
  /**
   * 进入下一关
   * 当前关卡完成后调用
   */
  nextLevel(): void;
  
  /**
   * 设置音量
   * @param volume - 音量（0-1）
   */
  setVolume(volume: number): void;
  
  /**
   * 获取当前游戏状态快照
   * @returns 游戏状态的只读副本
   */
  getState(): Readonly<GameStateSnapshot>;
}
```

### 1.2 事件系统接口（serves: FR-12）

```typescript
/**
 * 游戏事件类型枚举
 */
enum GameEvent {
  /** 关卡开始 */
  LevelStart = 'level:start',
  
  /** 关卡完成 */
  LevelComplete = 'level:complete',
  
  /** 游戏结束 */
  GameOver = 'game:over',
  
  /** 得分变化 */
  ScoreChange = 'score:change',
  
  /** 生命值变化 */
  LivesChange = 'lives:change',
  
  /** 敌军被摧毁 */
  EnemyDestroyed = 'enemy:destroyed',
  
  /** 道具收集 */
  PowerupCollected = 'powerup:collected'
}

/**
 * 事件回调函数类型
 */
type EventCallback<T = any> = (data: T) => void;

/**
 * 事件系统接口
 */
interface EventEmitter {
  /**
   * 注册事件监听器
   * @param event - 事件类型
   * @param callback - 回调函数
   */
  on(event: GameEvent, callback: EventCallback): void;
  
  /**
   * 移除事件监听器
   * @param event - 事件类型
   * @param callback - 回调函数
   */
  off(event: GameEvent, callback: EventCallback): void;
  
  /**
   * 注册一次性事件监听器
   * @param event - 事件类型
   * @param callback - 回调函数
   */
  once(event: GameEvent, callback: EventCallback): void;
  
  /**
   * 触发事件
   * @param event - 事件类型
   * @param data - 事件数据
   */
  emit(event: GameEvent, data?: any): void;
}

// 使用示例
game.on(GameEvent.LevelComplete, (level: number) => {
  console.log(`Level ${level} completed!`);
  // 显示关卡完成动画
});

game.on(GameEvent.ScoreChange, (score: number) => {
  console.log(`New score: ${score}`);
  // 更新 UI
});

game.on(GameEvent.GameOver, (finalScore: number) => {
  console.log(`Game Over! Final score: ${finalScore}`);
  // 显示游戏结束界面
});
```

---

## 二、内部接口

### 2.1 实体系统接口

```typescript
/**
 * 实体接口
 */
interface Entity {
  /** 唯一标识符 */
  readonly id: string;
  
  /** 是否激活 */
  active: boolean;
  
  /** 实体标签（用于分类） */
  tags: Set<string>;
  
  /**
   * 添加组件
   * @param component - 组件实例
   * @throws {Error} 组件类型已存在
   */
  addComponent(component: Component): void;
  
  /**
   * 获取组件
   * @param type - 组件类型名
   * @returns 组件实例或 null
   */
  getComponent<T extends Component>(type: string): T | null;
  
  /**
   * 移除组件
   * @param type - 组件类型名
   * @returns 是否成功移除
   */
  removeComponent(type: string): boolean;
  
  /**
   * 检查是否拥有组件
   * @param type - 组件类型名
   */
  hasComponent(type: string): boolean;
  
  /**
   * 检查是否拥有指定标签
   * @param tag - 标签名
   */
  hasTag(tag: string): boolean;
}

/**
 * 组件接口
 */
interface Component {
  /** 组件类型名 */
  readonly type: string;
  
  /** 是否启用 */
  enabled: boolean;
}

/**
 * 系统接口
 */
interface System {
  /** 执行优先级（越小越先执行） */
  readonly priority: number;
  
  /**
   * 更新系统
   * @param entities - 实体列表
   * @param deltaTime - 时间增量（秒）
   */
  update(entities: Entity[], deltaTime: number): void;
  
  /**
   * 初始化系统（可选）
   */
  init?(): void;
  
  /**
   * 销毁系统（可选）
   */
  destroy?(): void;
}
```

### 2.2 服务接口

#### AssetLoader（资源加载器）
```typescript
interface AssetManifest {
  images: { key: string; url: string }[];
  sounds: { key: string; url: string }[];
  levels: { key: string; url: string }[];
}

interface AssetLoader {
  /**
   * 预加载资源清单
   * @param manifest - 资源清单
   * @param onProgress - 进度回调（0-1）
   */
  preload(
    manifest: AssetManifest,
    onProgress?: (progress: number) => void
  ): Promise<void>;
  
  /**
   * 加载单个图片
   * @param key - 资源键名
   * @param url - 图片 URL
   */
  loadImage(key: string, url: string): Promise<HTMLImageElement>;
  
  /**
   * 加载单个音效
   * @param key - 资源键名
   * @param url - 音效 URL
   */
  loadSound(key: string, url: string): Promise<AudioBuffer>;
  
  /**
   * 获取已加载的资源
   * @param key - 资源键名
   * @returns 资源对象或 undefined
   */
  get<T>(key: string): T | undefined;
  
  /**
   * 检查资源是否已加载
   * @param key - 资源键名
   */
  has(key: string): boolean;
}
```

#### AudioManager（音效管理器）（serves: FR-11）
```typescript
interface AudioManager {
  /**
   * 播放音效
   * @param key - 音效键名
   * @param options - 播放选项
   */
  play(key: string, options?: {
    loop?: boolean;
    volume?: number;
  }): void;
  
  /**
   * 停止音效
   * @param key - 音效键名
   */
  stop(key: string): void;
  
  /**
   * 停止所有音效
   */
  stopAll(): void;
  
  /**
   * 设置全局音量
   * @param volume - 音量（0-1）
   */
  setVolume(volume: number): void;
  
  /**
   * 获取全局音量
   */
  getVolume(): number;
  
  /**
   * 静音/取消静音
   * @param muted - 是否静音
   */
  setMuted(muted: boolean): void;
  
  /**
   * 检查是否静音
   */
  isMuted(): boolean;
}
```

#### InputManager（输入管理器）（serves: FR-1）
```typescript
interface InputManager {
  /**
   * 检查按键是否按下
   * @param key - 按键名（小写）
   * @example isKeyPressed('w') → WASD 控制
   */
  isKeyPressed(key: string): boolean;
  
  /**
   * 检查按键是否刚按下（单帧）
   * @param key - 按键名
   */
  isKeyJustPressed(key: string): boolean;
  
  /**
   * 检查鼠标按钮是否按下
   * @param button - 按钮编号（0=左键，1=中键，2=右键）
   */
  isMouseButtonPressed(button: number): boolean;
  
  /**
   * 获取鼠标位置（Canvas 坐标）
   * @returns 鼠标坐标
   */
  getMousePosition(): { x: number; y: number };
  
  /**
   * 获取鼠标世界坐标
   * @param camera - 相机对象
   * @returns 世界坐标
   */
  getMouseWorldPosition(camera: Camera): { x: number; y: number };
}
```

#### LevelLoader（关卡加载器）
```typescript
interface LevelLoader {
  /**
   * 加载关卡数据
   * @param levelId - 关卡 ID
   * @returns 关卡数据
   * @throws {Error} 关卡不存在或格式错误
   */
  load(levelId: number): Promise<LevelData>;
  
  /**
   * 解析关卡数据为游戏对象
   * @param data - 关卡数据
   * @returns 关卡实例
   */
  parse(data: LevelData): Level;
  
  /**
   * 验证关卡数据格式
   * @param data - 关卡数据
   * @returns 是否有效
   */
  validate(data: any): boolean;
}
```

#### StorageManager（存储管理器）
```typescript
interface StorageManager {
  /**
   * 加载存档数据
   * @returns 存档数据或默认数据
   */
  load(): SaveData;
  
  /**
   * 保存存档数据
   * @param data - 存档数据
   */
  save(data: SaveData): void;
  
  /**
   * 清除存档
   */
  clear(): void;
  
  /**
   * 检查是否有存档
   */
  hasSave(): boolean;
}
```

---

## 三、工具接口

### 3.1 数学工具

```typescript
/**
 * 二维向量
 */
class Vector2D {
  x: number;
  y: number;
  
  constructor(x: number, y: number);
  
  /** 向量加法 */
  add(other: Vector2D): Vector2D;
  
  /** 向量减法 */
  sub(other: Vector2D): Vector2D;
  
  /** 标量乘法 */
  mul(scalar: number): Vector2D;
  
  /** 点积 */
  dot(other: Vector2D): number;
  
  /** 长度 */
  length(): number;
  
  /** 归一化 */
  normalize(): Vector2D;
  
  /** 距离 */
  distance(other: Vector2D): number;
  
  /** 角度（弧度） */
  angle(): number;
  
  /** 旋转 */
  rotate(angle: number): Vector2D;
  
  /** 克隆 */
  clone(): Vector2D;
  
  /** 设置值 */
  set(x: number, y: number): void;
}

/**
 * 矩形
 */
class Rectangle {
  x: number;
  y: number;
  width: number;
  height: number;
  
  constructor(x: number, y: number, width: number, height: number);
  
  /** 检测点是否在矩形内 */
  contains(x: number, y: number): boolean;
  
  /** 检测矩形相交 */
  intersects(other: Rectangle): boolean;
  
  /** 获取中心点 */
  getCenter(): Vector2D;
}
```

### 3.2 对象池接口

```typescript
interface ObjectPool<T> {
  /**
   * 获取对象
   * @returns 池中对象或新创建对象
   */
  acquire(): T;
  
  /**
   * 归还对象
   * @param obj - 对象实例
   */
  release(obj: T): void;
  
  /**
   * 获取池中可用对象数
   */
  getAvailableCount(): number;
  
  /**
   * 获取正在使用的对象数
   */
  getInUseCount(): number;
  
  /**
   * 清空池
   */
  clear(): void;
}
```

---

## 四、扩展接口（serves: FR-15）

### 4.1 插件接口

```typescript
/**
 * 游戏插件接口
 * 用于扩展游戏功能
 */
interface Plugin {
  /** 插件名称 */
  readonly name: string;
  
  /** 插件版本 */
  readonly version: string;
  
  /**
   * 初始化插件
   * @param game - 游戏实例
   */
  init(game: TankBattleGame): void;
  
  /**
   * 插件更新（每帧调用）
   * @param deltaTime - 时间增量
   */
  update?(deltaTime: number): void;
  
  /**
   * 销毁插件
   */
  destroy?(): void;
}

// 使用示例
class LeaderboardPlugin implements Plugin {
  name = 'leaderboard';
  version = '1.0.0';
  
  init(game: TankBattleGame): void {
    game.on(GameEvent.LevelComplete, (score: number) => {
      // 提交分数到排行榜
    });
  }
}

game.registerPlugin(new LeaderboardPlugin());
```

---

## 五、错误处理

### 5.1 错误类型

```typescript
/**
 * 游戏错误基类
 */
class GameError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'GameError';
  }
}

/**
 * 资源加载错误
 */
class AssetLoadError extends GameError {
  constructor(assetKey: string, reason: string) {
    super(`Failed to load asset "${assetKey}": ${reason}`);
    this.name = 'AssetLoadError';
  }
}

/**
 * 关卡加载错误
 */
class LevelLoadError extends GameError {
  constructor(levelId: number, reason: string) {
    super(`Failed to load level ${levelId}: ${reason}`);
    this.name = 'LevelLoadError';
  }
}

/**
 * 配置错误
 */
class ConfigError extends GameError {
  constructor(message: string) {
    super(`Configuration error: ${message}`);
    this.name = 'ConfigError';
  }
}
```

---

## 六、TypeScript 类型导出

```typescript
// src/types/index.ts
export * from './entities';
export * from './components';
export * from './systems';
export * from './services';
export * from './events';
export * from './config';

// 外部使用
import type { 
  GameConfig, 
  LevelData, 
  GameEvent 
} from 'tank-battle-game';
```

---

**文档版本**: 1.0  
**最后更新**: 2024-09-24
