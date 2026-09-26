---
requirement_refs:
  - FR-1
  - FR-2
  - FR-6
  - FR-7
  - FR-8
  - FR-10
  - FR-12
---

# 用例设计文档

**需求ID**: REQ-260924162957-2cd3  
**文档类型**: 用例设计  
**版本**: 1.0  
**创建时间**: 2024-09-24

---

## 一、核心用例（serves: FR-1, FR-6, FR-7, FR-8）

### UC-1: 启动游戏

**参与者**：玩家

**前置条件**：
- 浏览器支持 Canvas 2D
- 网络连接正常（首次加载资源）

**主流程**：
1. 玩家访问游戏页面
2. 系统显示加载进度条
3. 系统加载核心资源（图片、音效）
4. 加载完成后显示主菜单
5. 主菜单显示选项：开始游戏、设置、关于

**后置条件**：
- 游戏进入主菜单状态
- 所有核心资源已加载

**异常流程**：
- 3a. 资源加载失败
  - 系统显示错误提示
  - 提供重试按钮

**实现要点**：
```typescript
// 入口：main.ts
async function bootstrap() {
  const game = new TankBattleGame('game-container');
  
  try {
    await game.start(); // 触发资源加载
  } catch (error) {
    showErrorDialog('加载失败，请刷新页面重试');
  }
}
```

---

### UC-2: 开始新游戏（serves: FR-8）

**参与者**：玩家

**前置条件**：
- 游戏在主菜单状态

**主流程**：
1. 玩家点击"开始游戏"
2. 系统加载第一关数据
3. 系统创建玩家坦克
4. 系统生成敌军坦克
5. 系统初始化关卡地形
6. 游戏开始，显示 HUD（生命、得分、关卡）

**后置条件**：
- 游戏进入 Playing 状态
- 玩家可以控制坦克

**异常流程**：
- 2a. 关卡数据加载失败
  - 系统返回主菜单
  - 显示错误提示

**实现要点**：
```typescript
// PlayingState.enter()
async enter(): void {
  // 加载关卡
  const levelData = await levelLoader.load(this.currentLevel);
  this.level = levelLoader.parse(levelData);
  
  // 创建玩家
  this.player = this.createPlayer(levelData.playerSpawn);
  
  // 生成敌军
  levelData.enemies.forEach(spawn => {
    this.spawnEnemy(spawn);
  });
  
  // 初始化 UI
  this.hud.show();
}
```

---

### UC-3: 玩家控制坦克（serves: FR-1）

**参与者**：玩家

**前置条件**：
- 游戏在 Playing 状态
- 玩家坦克存活

**主流程**：
1. 玩家按下 W/A/S/D 或方向键
2. 系统检测输入
3. 系统更新坦克速度
4. 系统检测边界碰撞
5. 系统更新坦克位置
6. 系统渲染坦克新位置

**扩展流程**：
- 2a. 玩家按下空格键
  - 系统检查武器冷却
  - 如果可以射击，创建子弹实体
  - 播放射击音效
  - 更新武器冷却时间

**后置条件**：
- 坦克位置已更新
- 或子弹已发射

**实现要点**：
```typescript
// PhysicsSystem.update()
update(entities: Entity[], deltaTime: number): void {
  entities.forEach(entity => {
    const transform = entity.getComponent<Transform>('Transform');
    const velocity = entity.getComponent<Velocity>('Velocity');
    
    if (transform && velocity) {
      // 更新位置
      transform.position.x += velocity.linear.x * deltaTime;
      transform.position.y += velocity.linear.y * deltaTime;
      
      // 边界限制
      this.clampToBounds(transform);
    }
  });
}
```

---

### UC-4: 击毁敌军坦克（serves: FR-2, FR-6, FR-7）

**参与者**：玩家、系统

**前置条件**：
- 游戏在 Playing 状态
- 玩家子弹与敌军坦克碰撞

**主流程**：
1. 碰撞系统检测到子弹命中敌军
2. 系统扣除敌军生命值
3. 如果敌军生命值归零：
   - 系统创建爆炸粒子特效
   - 系统播放爆炸音效
   - 系统移除敌军实体
   - 系统增加玩家得分
   - 系统检查连击状态
4. 系统检查关卡完成条件

**扩展流程**：
- 3a. 触发连击奖励
  - 如果距离上次击杀 < 5 秒
  - 连击数 +1
  - 额外得分 +50

**后置条件**：
- 敌军被移除
- 玩家得分增加
- 可能触发关卡完成

**实现要点**：
```typescript
// CollisionSystem.handleCollision()
handleCollision(bullet: Entity, tank: Entity): void {
  const health = tank.getComponent<Health>('Health');
  health.takeDamage(bullet.damage);
  
  if (health.isDead()) {
    // 爆炸特效
    this.particleSystem.createExplosion(tank.position);
    
    // 音效
    this.audio.play('explosion');
    
    // 得分
    this.addScore(100);
    this.checkCombo();
    
    // 移除
    this.entityManager.remove(tank);
    
    // 检查胜利
    if (this.allEnemiesDead()) {
      this.stateManager.transition(GameState.LevelComplete);
    }
  }
}
```

---

### UC-5: 收集道具（serves: FR-10）

**参与者**：玩家、系统

**前置条件**：
- 游戏在 Playing 状态
- 地图上存在道具
- 玩家坦克与道具碰撞

**主流程**：
1. 碰撞系统检测到玩家碰撞道具
2. 系统识别道具类型
3. 系统应用道具效果：
   - 生命补给：生命 +1
   - 护盾：5 秒无敌
   - 火力增强：子弹穿透
   - 时间冻结：敌军暂停 3 秒
4. 系统播放道具收集音效
5. 系统移除道具实体
6. 系统显示道具效果 UI 提示

**后置条件**：
- 道具效果已应用
- 道具已移除

**实现要点**：
```typescript
// PowerupSystem.applyPowerup()
applyPowerup(player: Entity, powerup: Entity): void {
  const type = powerup.getComponent<Powerup>('Powerup').type;
  
  switch (type) {
    case 'life':
      player.getComponent<Lives>('Lives').add(1);
      break;
    case 'shield':
      const health = player.getComponent<Health>('Health');
      health.invulnerable = true;
      health.invulnerableUntil = Date.now() + 5000;
      break;
    case 'power':
      player.getComponent<Weapon>('Weapon').bulletType = 'piercing';
      break;
    case 'freeze':
      this.freezeEnemies(3000);
      break;
  }
  
  this.audio.play('powerup');
  this.entityManager.remove(powerup);
}
```

---

## 二、UI 交互用例（serves: FR-12）

### UC-6: 暂停游戏

**参与者**：玩家

**前置条件**：
- 游戏在 Playing 状态

**主流程**：
1. 玩家按下 P 键或点击暂停按钮
2. 系统暂停游戏循环
3. 系统显示暂停菜单
4. 暂停菜单显示选项：继续、重新开始、返回主菜单

**后置条件**：
- 游戏进入 Paused 状态
- 游戏逻辑停止更新

**实现要点**：
```typescript
// StateManager.pause()
pause(): void {
  if (this.current !== GameState.Playing) return;
  
  this.previous = this.current;
  this.transition(GameState.Paused);
  
  // 停止游戏循环
  this.engine.pause();
  
  // 显示暂停菜单
  this.ui.showPauseMenu();
}
```

---

### UC-7: 关卡完成

**参与者**：系统

**前置条件**：
- 所有敌军已被消灭
- 或关卡目标已达成

**主流程**：
1. 系统检测到关卡完成条件
2. 系统计算关卡得分
3. 系统显示关卡完成界面
4. 界面显示：得分、用时、评级
5. 系统保存进度
6. 3 秒后自动进入下一关

**扩展流程**：
- 6a. 玩家点击"下一关"按钮
  - 立即进入下一关
- 6b. 玩家点击"返回主菜单"
  - 返回主菜单

**后置条件**：
- 进度已保存
- 下一关已解锁

**实现要点**：
```typescript
// LevelCompleteState.enter()
enter(): void {
  const score = this.calculateLevelScore();
  const time = Date.now() - this.levelStartTime;
  const rating = this.calculateRating(score, time);
  
  // 保存进度
  const save = storageManager.load();
  save.unlockedLevels.push(this.currentLevel + 1);
  save.completedLevels.push(this.currentLevel);
  if (score > save.highScore) {
    save.highScore = score;
  }
  storageManager.save(save);
  
  // 显示界面
  this.ui.showLevelComplete({
    score,
    time,
    rating,
    onNext: () => this.nextLevel(),
    onMenu: () => this.returnToMenu()
  });
  
  // 3 秒后自动下一关
  setTimeout(() => this.nextLevel(), 3000);
}
```

---

### UC-8: 游戏结束

**参与者**：系统

**前置条件**：
- 玩家生命值归零
- 或基地被摧毁

**主流程**：
1. 系统检测到失败条件
2. 系统停止游戏循环
3. 系统显示游戏结束界面
4. 界面显示：最终得分、最高分、失败原因
5. 界面显示选项：重新开始、返回主菜单

**后置条件**：
- 游戏进入 GameOver 状态

**实现要点**：
```typescript
// GameOverState.enter()
enter(): void {
  const finalScore = this.gameState.score;
  const highScore = storageManager.load().highScore;
  
  // 显示界面
  this.ui.showGameOver({
    finalScore,
    highScore,
    reason: this.gameState.failReason,
    onRestart: () => this.restart(),
    onMenu: () => this.returnToMenu()
  });
  
  // 触发事件
  this.eventEmitter.emit(GameEvent.GameOver, finalScore);
}
```

---

## 三、AI 用例（serves: FR-2）

### UC-9: 敌军 AI 决策

**参与者**：系统

**前置条件**：
- 游戏在 Playing 状态
- 敌军坦克存活

**主流程**：
1. AISystem 每 500ms 为每个敌军做决策
2. 系统检测玩家位置
3. 根据 AI 类型执行不同行为：
   - **巡逻型**：
     - 随机选择方向移动
     - 遇到障碍物改变方向
     - 定期射击
   - **追击型**：
     - 如果检测到玩家（< 300px）
     - 计算到玩家的路径（A*）
     - 向玩家移动
     - 瞄准玩家射击
   - **狙击型**：
     - 如果检测到玩家
     - 保持安全距离（> 200px）
     - 预判玩家移动方向
     - 精确射击

**后置条件**：
- 敌军行为已更新

**实现要点**：
```typescript
// AISystem.update()
update(entities: Entity[], deltaTime: number): void {
  const player = this.findPlayer(entities);
  const enemies = this.findEnemies(entities);
  
  enemies.forEach(enemy => {
    const ai = enemy.getComponent<AIBehavior>('AIBehavior');
    const now = Date.now();
    
    if (now - ai.lastDecisionTime < ai.decisionInterval) {
      return;
    }
    
    ai.lastDecisionTime = now;
    
    switch (ai.behaviorType) {
      case 'patrol':
        this.patrolBehavior(enemy);
        break;
      case 'chase':
        this.chaseBehavior(enemy, player);
        break;
      case 'sniper':
        this.sniperBehavior(enemy, player);
        break;
    }
  });
}
```

---

## 四、时序图

### 时序图：玩家射击击中敌军

```
Player    Input     Weapon    Bullet    Collision    Enemy    Particle    Score
  |         |         |         |           |           |         |         |
  |--按空格->|         |         |           |           |         |         |
  |         |--检查冷却->|       |           |           |         |         |
  |         |         |--创建子弹->|         |           |         |         |
  |         |         |         |--移动---->|           |         |         |
  |         |         |         |           |--检测碰撞->|         |         |
  |         |         |         |           |           |--扣血   |         |
  |         |         |         |           |           |--死亡-->|         |
  |         |         |         |           |           |         |--爆炸  |
  |         |         |         |           |           |         |         |--+100
  |<--------得分更新事件----------------------------------------------------|
```

---

**文档版本**: 1.0  
**最后更新**: 2024-09-24
