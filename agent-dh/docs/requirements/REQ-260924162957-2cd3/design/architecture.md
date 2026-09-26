---
requirement_refs:
  - FR-1
  - FR-2
  - FR-3
  - FR-4
  - FR-5
  - FR-14
---

# 架构设计文档

**需求ID**: REQ-260924162957-2cd3  
**文档类型**: 架构设计  
**版本**: 1.0  
**创建时间**: 2024-09-24

---

## 一、架构概览（serves: FR-1, FR-2, FR-3, FR-4）

### 1.1 整体架构

本游戏采用**轻量级 ECS（Entity-Component-System）架构 + Service Locator 模式**。

```
┌─────────────────────────────────────────┐
│          Game Engine (主循环)            │
│  • 管理实体生命周期                      │
│  • 驱动系统更新                          │
│  • 协调各服务                            │
└──────────────┬──────────────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌─────────────┐   ┌─────────────┐
│  Entities   │   │   Systems   │
│  实体集合    │   │   系统集合   │
└─────────────┘   └─────────────┘
      │                 │
      │ 包含            │ 处理
      ▼                 ▼
┌─────────────┐   ┌─────────────┐
│ Components  │   │  Services   │
│ 组件（数据） │   │  服务定位器  │
└─────────────┘   └─────────────┘
                        │
                        ├── AssetLoader（资源加载）
                        ├── AudioManager（音效管理）
                        ├── InputManager（输入管理）
                        ├── LevelLoader（关卡加载）
                        └── StorageManager（存档管理）
```

### 1.2 架构决策

#### AD-1: ECS 架构（serves: FR-1, FR-2, FR-3, FR-4）

**决策**：采用轻量级 ECS，而非传统 OOP 继承体系

**理由**：
- **数据与行为分离**：组件存储数据，系统处理逻辑，便于测试
- **高性能**：缓存友好，批量处理相同类型组件
- **灵活组合**：新实体通过组合现有组件创建，无需新类
- **易扩展**：新增功能只需添加组件和系统，不影响现有代码

**实现**：
```typescript
// 实体：组件容器
interface Entity {
  id: string;
  active: boolean;
  components: Map<string, Component>;
}

// 组件：纯数据
interface Component {
  type: string;
  enabled: boolean;
}

// 系统：处理逻辑
interface System {
  priority: number;
  update(entities: Entity[], deltaTime: number): void;
}
```

#### AD-2: Service Locator 模式（serves: FR-11）

**决策**：全局服务通过 Service Locator 访问

**理由**：
- **解耦**：系统不直接依赖具体服务实现
- **可测试**：服务可被 mock 替换
- **延迟初始化**：按需加载服务

**实现**：
```typescript
class ServiceLocator {
  private static services: Map<string, any> = new Map();
  
  static register<T>(name: string, service: T): void {
    this.services.set(name, service);
  }
  
  static get<T>(name: string): T {
    return this.services.get(name);
  }
}

// 使用
ServiceLocator.register('audio', new AudioManager());
const audio = ServiceLocator.get<AudioManager>('audio');
```

---

## 二、核心系统设计（serves: FR-1, FR-2, FR-3, FR-4, FR-5）

### 2.1 系统清单与职责

| 系统 | 优先级 | 职责 | 涉及功能点 |
|------|--------|------|-----------|
| InputSystem | 5 | 采集键盘/鼠标输入 | FR-1 |
| AISystem | 15 | 敌军 AI 行为 | FR-2 |
| PhysicsSystem | 10 | 物理运动、速度更新 | FR-1, FR-3 |
| CollisionSystem | 20 | 碰撞检测与响应 | FR-4 |
| WeaponSystem | 25 | 武器射击、冷却 | FR-1, FR-3 |
| ParticleSystem | 90 | 粒子特效更新 | FR-5 |
| RenderSystem | 100 | 渲染所有可见对象 | FR-1~FR-5 |

### 2.2 系统执行顺序

```
每帧执行顺序（按 priority 升序）：
1. InputSystem (5)      - 读取输入
2. PhysicsSystem (10)   - 更新位置
3. AISystem (15)        - AI 决策
4. CollisionSystem (20) - 碰撞检测
5. WeaponSystem (25)    - 处理射击
6. ParticleSystem (90)  - 更新粒子
7. RenderSystem (100)   - 渲染画面
```

### 2.3 渲染系统（serves: FR-1, FR-5）

**职责**：
- 绘制所有可见实体（坦克、子弹、地形、粒子）
- Z-index 排序
- 屏幕外剔除

**实现**：
```typescript
class RenderSystem implements System {
  priority = 100;
  
  update(entities: Entity[], deltaTime: number): void {
    // 1. 筛选可见实体
    const visibleEntities = entities.filter(e => 
      e.getComponent<Sprite>('Sprite')?.enabled
    );
    
    // 2. 按 z-index 排序
    visibleEntities.sort((a, b) => {
      const zA = a.getComponent<Sprite>('Sprite')!.zIndex;
      const zB = b.getComponent<Sprite>('Sprite')!.zIndex;
      return zA - zB;
    });
    
    // 3. 绘制
    visibleEntities.forEach(entity => this.renderEntity(entity));
  }
}
```

### 2.4 碰撞检测系统（serves: FR-4）

**职责**：
- 检测实体间碰撞
- 触发碰撞事件

**优化策略**：
- **四叉树空间分区**：将 O(n²) 降至 O(n log n)
- **AABB 快速检测**：轴对齐包围盒
- **分层过滤**：子弹只检测坦克层

**实现**：
```typescript
class CollisionSystem implements System {
  priority = 20;
  private quadTree: QuadTree;
  
  update(entities: Entity[], deltaTime: number): void {
    // 1. 清空四叉树
    this.quadTree.clear();
    
    // 2. 插入所有碰撞体
    entities
      .filter(e => e.getComponent<Collider>('Collider'))
      .forEach(e => this.quadTree.insert(e));
    
    // 3. 检测碰撞
    entities.forEach(entity => {
      const candidates = this.quadTree.retrieve(entity);
      candidates.forEach(other => {
        if (this.checkCollision(entity, other)) {
          this.handleCollision(entity, other);
        }
      });
    });
  }
}
```

---

## 三、状态管理（serves: FR-12）

### 3.1 状态机设计

```typescript
enum GameState {
  Boot,          // 启动加载
  MainMenu,      // 主菜单
  Playing,       // 游戏中
  Paused,        // 暂停
  LevelComplete, // 关卡完成
  GameOver       // 游戏结束
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
```

### 3.2 状态转移图

```
[Boot] → [MainMenu] ⇄ [Settings]
            ↓
        [Playing] ⇄ [Paused]
            ↓
      [LevelComplete] → [Playing] (下一关)
            ↓
       [GameOver] → [MainMenu]
```

---

## 四、性能优化架构（serves: FR-14）

### 4.1 对象池

**目标**：避免频繁创建/销毁对象（子弹、粒子）

```typescript
class ObjectPool<T> {
  private available: T[] = [];
  private inUse: Set<T> = new Set();
  
  acquire(): T {
    return this.available.pop() || this.factory();
  }
  
  release(obj: T): void {
    this.reset(obj);
    this.available.push(obj);
  }
}
```

### 4.2 四叉树空间分区

**目标**：减少碰撞检测复杂度

```
地图分区示例（26x26 格子）：

┌─────────────┬─────────────┐
│             │             │
│   Quadrant  │  Quadrant   │
│      0      │      1      │
│             │             │
├─────────────┼─────────────┤
│             │             │
│   Quadrant  │  Quadrant   │
│      2      │      3      │
│             │             │
└─────────────┴─────────────┘

每个象限可进一步细分，最多 5 层
```

---

## 五、模块依赖图

```
┌──────────────┐
│    main.ts   │ (入口)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ GameEngine   │
└──────┬───────┘
       │
       ├─→ EntityManager
       ├─→ SystemManager
       ├─→ StateManager
       └─→ ServiceLocator
              │
              ├─→ AssetLoader
              ├─→ AudioManager
              ├─→ InputManager
              ├─→ LevelLoader
              └─→ StorageManager
```

---

## 六、技术债务与未来改进

### 6.1 当前限制
- 单线程执行（JavaScript 限制）
- 无网络同步（单机游戏）
- Canvas 2D 渲染（非 WebGL）

### 6.2 未来可扩展点
- 迁移到 WebGL 渲染（更高性能）
- 使用 Web Workers 处理 AI 计算
- 添加网络对战（WebSocket 同步）

---

**文档版本**: 1.0  
**最后更新**: 2024-09-24
