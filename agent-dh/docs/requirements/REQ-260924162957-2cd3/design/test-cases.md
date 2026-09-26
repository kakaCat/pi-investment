---
requirement_refs:
  - FR-1
  - FR-2
  - FR-3
  - FR-4
  - FR-13
  - FR-14
---

# 测试用例设计文档

**需求ID**: REQ-260924162957-2cd3  
**文档类型**: 测试用例设计  
**版本**: 1.0  
**创建时间**: 2024-09-24

---

## 一、测试策略（serves: FR-13）

### 1.1 测试层次

```
┌─────────────────────────────────┐
│   E2E 测试（端到端）             │  5%
│   • 完整游戏流程                 │
└─────────────────────────────────┘
           ↓
┌─────────────────────────────────┐
│   集成测试                       │  15%
│   • 系统间协作                   │
│   • 碰撞检测 + 生命值            │
└─────────────────────────────────┘
           ↓
┌─────────────────────────────────┐
│   单元测试                       │  80%
│   • 纯函数、类方法               │
│   • 工具类、数据结构             │
└─────────────────────────────────┘
```

### 1.2 覆盖率目标

- **整体覆盖率**：≥ 80%
- **核心引擎**：≥ 90%（Engine、EntityManager、SystemManager）
- **系统层**：≥ 85%（PhysicsSystem、CollisionSystem 等）
- **工具类**：≥ 80%（Vector2D、QuadTree、ObjectPool）
- **UI 层**：≥ 60%（渲染逻辑难测）

---

## 二、单元测试用例（serves: FR-1, FR-3, FR-4）

### TC-1: Vector2D 数学运算

**测试类**：`Vector2D`  
**功能点**：FR-1（移动计算依赖向量）

**测试用例 1.1：向量加法**
```typescript
describe('Vector2D.add', () => {
  it('should add two vectors correctly', () => {
    const v1 = new Vector2D(3, 4);
    const v2 = new Vector2D(1, 2);
    const result = v1.add(v2);
    
    expect(result.x).toBe(4);
    expect(result.y).toBe(6);
  });
  
  it('should not mutate original vector', () => {
    const v1 = new Vector2D(3, 4);
    const v2 = new Vector2D(1, 2);
    v1.add(v2);
    
    expect(v1.x).toBe(3);
    expect(v1.y).toBe(4);
  });
});
```

**测试用例 1.2：向量归一化**
```typescript
describe('Vector2D.normalize', () => {
  it('should return unit vector', () => {
    const v = new Vector2D(3, 4);
    const normalized = v.normalize();
    
    expect(normalized.length()).toBeCloseTo(1.0, 5);
  });
  
  it('should maintain direction', () => {
    const v = new Vector2D(3, 4);
    const normalized = v.normalize();
    const angle1 = v.angle();
    const angle2 = normalized.angle();
    
    expect(angle1).toBeCloseTo(angle2, 5);
  });
});
```

---

### TC-2: ObjectPool 对象复用（serves: FR-14）

**测试类**：`ObjectPool`  
**功能点**：FR-14（性能优化）

**测试用例 2.1：对象复用**
```typescript
describe('ObjectPool', () => {
  it('should reuse released objects', () => {
    const pool = new ObjectPool(
      () => ({ id: Math.random() }),
      (obj) => {}
    );
    
    const obj1 = pool.acquire();
    const id1 = obj1.id;
    
    pool.release(obj1);
    
    const obj2 = pool.acquire();
    const id2 = obj2.id;
    
    expect(id1).toBe(id2); // 同一个对象
  });
  
  it('should create new object when pool is empty', () => {
    const pool = new ObjectPool(
      () => ({ id: Math.random() }),
      (obj) => {}
    );
    
    const obj1 = pool.acquire();
    const obj2 = pool.acquire();
    
    expect(obj1).not.toBe(obj2);
  });
  
  it('should reset object on release', () => {
    const pool = new ObjectPool(
      () => ({ value: 0 }),
      (obj) => { obj.value = 0; }
    );
    
    const obj = pool.acquire();
    obj.value = 100;
    pool.release(obj);
    
    const obj2 = pool.acquire();
    expect(obj2.value).toBe(0);
  });
});
```

---

### TC-3: QuadTree 空间分区（serves: FR-4）

**测试类**：`QuadTree`  
**功能点**：FR-4（碰撞检测优化）

**测试用例 3.1：插入与检索**
```typescript
describe('QuadTree', () => {
  it('should insert entities correctly', () => {
    const tree = new QuadTree(0, new Rectangle(0, 0, 800, 600));
    const entity = createMockEntity(100, 100);
    
    tree.insert(entity);
    const retrieved = tree.retrieve(entity);
    
    expect(retrieved).toContain(entity);
  });
  
  it('should split when max objects exceeded', () => {
    const tree = new QuadTree(0, new Rectangle(0, 0, 800, 600));
    
    // 插入超过 maxObjects 数量的实体
    for (let i = 0; i < 15; i++) {
      tree.insert(createMockEntity(i * 50, i * 50));
    }
    
    // 验证已分裂（有子节点）
    expect(tree.getNodes().length).toBeGreaterThan(0);
  });
  
  it('should only retrieve nearby entities', () => {
    const tree = new QuadTree(0, new Rectangle(0, 0, 800, 600));
    
    const entity1 = createMockEntity(100, 100);
    const entity2 = createMockEntity(700, 500); // 远离 entity1
    
    tree.insert(entity1);
    tree.insert(entity2);
    
    const retrieved = tree.retrieve(entity1);
    
    expect(retrieved).toContain(entity1);
    expect(retrieved).not.toContain(entity2);
  });
});
```

---

### TC-4: Entity 组件管理

**测试类**：`Entity`  
**功能点**：FR-1, FR-2, FR-3（实体基础）

**测试用例 4.1：组件添加与获取**
```typescript
describe('Entity', () => {
  it('should add and get component', () => {
    const entity = new Entity('test-1');
    const transform = new Transform(100, 100);
    
    entity.addComponent(transform);
    
    const retrieved = entity.getComponent<Transform>('Transform');
    expect(retrieved).toBe(transform);
  });
  
  it('should return null for non-existent component', () => {
    const entity = new Entity('test-1');
    const retrieved = entity.getComponent<Transform>('Transform');
    
    expect(retrieved).toBeNull();
  });
  
  it('should remove component', () => {
    const entity = new Entity('test-1');
    entity.addComponent(new Transform(100, 100));
    
    const removed = entity.removeComponent('Transform');
    expect(removed).toBe(true);
    
    const retrieved = entity.getComponent<Transform>('Transform');
    expect(retrieved).toBeNull();
  });
  
  it('should throw error when adding duplicate component type', () => {
    const entity = new Entity('test-1');
    entity.addComponent(new Transform(100, 100));
    
    expect(() => {
      entity.addComponent(new Transform(200, 200));
    }).toThrow('Component type Transform already exists');
  });
});
```

---

## 三、集成测试用例（serves: FR-1, FR-3, FR-4）

### TC-5: 碰撞检测 + 生命值系统

**测试场景**：子弹击中坦克 → 扣除生命值

**测试用例 5.1：子弹击中敌军**
```typescript
describe('Collision + Health Integration', () => {
  it('should damage enemy when bullet hits', () => {
    const engine = new GameEngine(testConfig);
    
    // 创建敌军坦克
    const enemy = createTank('enemy', 200, 200);
    enemy.addComponent(new Health(3));
    engine.addEntity(enemy);
    
    // 创建子弹
    const bullet = createBullet(200, 150, { damage: 1 });
    bullet.addComponent(new Velocity());
    bullet.getComponent<Velocity>('Velocity')!.linear.y = 100; // 向下移动
    engine.addEntity(bullet);
    
    // 模拟 1 秒（子弹应该击中）
    for (let i = 0; i < 60; i++) {
      engine.update(1/60);
    }
    
    // 验证敌军受损
    const health = enemy.getComponent<Health>('Health');
    expect(health!.current).toBe(2);
    
    // 验证子弹已销毁
    expect(bullet.active).toBe(false);
  });
  
  it('should destroy enemy when health reaches zero', () => {
    const engine = new GameEngine(testConfig);
    
    const enemy = createTank('enemy', 200, 200);
    enemy.addComponent(new Health(1)); // 只有 1 点生命
    engine.addEntity(enemy);
    
    const bullet = createBullet(200, 150, { damage: 1 });
    engine.addEntity(bullet);
    
    engine.update(1);
    
    // 验证敌军已被移除
    expect(enemy.active).toBe(false);
  });
});
```

---

### TC-6: AI 系统 + 物理系统

**测试场景**：追击型 AI 追踪玩家

**测试用例 6.1：AI 向玩家移动**
```typescript
describe('AI + Physics Integration', () => {
  it('should chase player when in range', () => {
    const engine = new GameEngine(testConfig);
    
    // 创建玩家
    const player = createTank('player', 200, 200);
    player.tags.add('player');
    engine.addEntity(player);
    
    // 创建追击型敌军
    const enemy = createTank('enemy', 400, 200);
    enemy.addComponent(new AIBehavior('chase'));
    engine.addEntity(enemy);
    
    const initialX = enemy.getComponent<Transform>('Transform')!.position.x;
    
    // 模拟 5 秒
    for (let i = 0; i < 300; i++) {
      engine.update(1/60);
    }
    
    const finalX = enemy.getComponent<Transform>('Transform')!.position.x;
    
    // 验证敌军向玩家移动（x 坐标减小）
    expect(finalX).toBeLessThan(initialX);
  });
});
```

---

## 四、性能测试用例（serves: FR-14）

### TC-7: 帧率性能测试

**测试目标**：50 个实体下维持 60 FPS

**测试用例 7.1：大量实体性能**
```typescript
describe('Performance Tests', () => {
  it('should maintain 60 FPS with 50 entities', () => {
    const engine = new GameEngine(testConfig);
    
    // 创建 50 个实体
    for (let i = 0; i < 50; i++) {
      const entity = createTank(`tank-${i}`, 
        Math.random() * 800, 
        Math.random() * 600
      );
      entity.addComponent(new Velocity());
      engine.addEntity(entity);
    }
    
    // 测量 100 帧的平均帧时间
    const frameTimes: number[] = [];
    
    for (let i = 0; i < 100; i++) {
      const start = performance.now();
      engine.update(1/60);
      const end = performance.now();
      
      frameTimes.push(end - start);
    }
    
    const avgFrameTime = frameTimes.reduce((a, b) => a + b) / frameTimes.length;
    
    // 16.67ms = 60 FPS
    expect(avgFrameTime).toBeLessThan(16.67);
  });
  
  it('should handle 1000 particles efficiently', () => {
    const particleSystem = new ParticleSystem();
    const pool = new ObjectPool(
      () => new Particle(),
      (p) => p.reset()
    );
    
    // 创建 1000 个粒子
    for (let i = 0; i < 1000; i++) {
      const particle = pool.acquire();
      particleSystem.addParticle(particle);
    }
    
    // 测量更新时间
    const start = performance.now();
    particleSystem.update(1/60);
    const end = performance.now();
    
    // 1000 个粒子更新应 < 5ms
    expect(end - start).toBeLessThan(5);
  });
});
```

---

## 五、端到端测试用例

### TC-8: 完整游戏流程

**测试场景**：启动 → 游戏 → 完成第一关

**测试用例 8.1：完整流程**
```typescript
describe('E2E: Complete Game Flow', () => {
  it('should complete level 1', async () => {
    const game = new TankBattleGame('test-container');
    
    // 启动游戏
    await game.start();
    expect(game.getState().currentState).toBe(GameState.MainMenu);
    
    // 开始游戏
    game.startNewGame();
    await waitForState(game, GameState.Playing);
    
    // 模拟击杀所有敌军
    const enemies = game.getEntitiesByTag('enemy');
    enemies.forEach(enemy => {
      const health = enemy.getComponent<Health>('Health');
      health!.current = 0;
    });
    
    // 触发检查
    game.checkLevelComplete();
    
    // 验证关卡完成
    await waitForState(game, GameState.LevelComplete);
    expect(game.getState().currentLevel).toBe(1);
  });
});
```

---

## 六、测试辅助工具

### 6.1 Mock 工厂函数

```typescript
// tests/helpers/factories.ts

/**
 * 创建测试用实体
 */
export function createMockEntity(x: number, y: number): Entity {
  const entity = new Entity(`mock-${Math.random()}`);
  entity.addComponent(new Transform(x, y));
  entity.addComponent(new Collider('box', 32));
  return entity;
}

/**
 * 创建测试用坦克
 */
export function createTank(id: string, x: number, y: number): Entity {
  const entity = new Entity(id);
  entity.addComponent(new Transform(x, y));
  entity.addComponent(new Sprite('tank', 32, 32));
  entity.addComponent(new Velocity());
  entity.addComponent(new Collider('box', 32));
  entity.addComponent(new Weapon(500, 400));
  return entity;
}

/**
 * 创建测试用子弹
 */
export function createBullet(x: number, y: number, options?: {
  damage?: number;
}): Entity {
  const entity = new Entity(`bullet-${Math.random()}`);
  entity.addComponent(new Transform(x, y));
  entity.addComponent(new Sprite('bullet', 8, 8));
  entity.addComponent(new Collider('circle', 4));
  
  const velocity = new Velocity();
  entity.addComponent(velocity);
  
  entity.damage = options?.damage || 1;
  
  return entity;
}
```

### 6.2 测试配置

```typescript
// tests/helpers/config.ts

export const testConfig: GameConfig = {
  canvas: {
    width: 800,
    height: 600,
    backgroundColor: '#000000'
  },
  physics: {
    maxVelocity: 300,
    friction: 0.98
  },
  player: {
    speed: 150,
    rotationSpeed: Math.PI,
    fireRate: 500,
    maxLives: 3,
    bulletSpeed: 400,
    bulletDamage: 1
  },
  enemy: {
    types: {
      patrol: {
        speed: 100,
        fireRate: 1000,
        health: 1,
        bulletSpeed: 300,
        detectionRange: 300,
        score: 100
      }
    }
  },
  scoring: {
    enemyKill: 100,
    comboBonus: 50,
    comboWindow: 5000,
    levelComplete: 500
  }
};
```

---

## 七、持续集成测试

### 7.1 GitHub Actions 配置

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: npm install
      
      - name: Run tests
        run: npm test
      
      - name: Check coverage
        run: npm run test:coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/lcov.info
```

---

## 八、测试执行计划

### 8.1 开发阶段测试

```bash
# 单元测试（快速反馈）
npm run test:unit

# 监听模式（开发时）
npm run test:watch

# 覆盖率报告
npm run test:coverage
```

### 8.2 提交前测试

```bash
# 完整测试套件
npm test

# 检查覆盖率
npm run test:coverage

# ESLint 检查
npm run lint
```

### 8.3 发布前测试

```bash
# 完整测试 + E2E
npm run test:all

# 性能测试
npm run test:performance

# 构建验证
npm run build
```

---

**文档版本**: 1.0  
**最后更新**: 2024-09-24
