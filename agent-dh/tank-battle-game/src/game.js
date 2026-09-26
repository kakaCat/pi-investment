// 坦克大作战游戏主逻辑
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

// 游戏状态
let gameState = {
    lives: 3,
    score: 0,
    level: 1,
    paused: false,
    gameOver: false
};

// 玩家坦克
class PlayerTank {
    constructor() {
        this.x = canvas.width / 2;
        this.y = canvas.height - 60;
        this.width = 40;
        this.height = 40;
        this.speed = 3;
        this.direction = 'up';
        this.color = '#4ecdc4';
        this.lastShot = 0;
        this.shootCooldown = 300;
    }

    draw() {
        ctx.save();
        ctx.translate(this.x, this.y);
        
        // 坦克主体
        ctx.fillStyle = this.color;
        ctx.fillRect(-this.width/2, -this.height/2, this.width, this.height);
        
        // 坦克轮廓
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.strokeRect(-this.width/2, -this.height/2, this.width, this.height);
        
        // 炮管
        ctx.fillStyle = '#2c3e50';
        if (this.direction === 'up') {
            ctx.fillRect(-3, -this.height/2 - 15, 6, 15);
        } else if (this.direction === 'down') {
            ctx.fillRect(-3, this.height/2, 6, 15);
        } else if (this.direction === 'left') {
            ctx.fillRect(-this.width/2 - 15, -3, 15, 6);
        } else if (this.direction === 'right') {
            ctx.fillRect(this.width/2, -3, 15, 6);
        }
        
        ctx.restore();
    }

    move(dx, dy) {
        this.x = Math.max(this.width/2, Math.min(canvas.width - this.width/2, this.x + dx));
        this.y = Math.max(this.height/2, Math.min(canvas.height - this.height/2, this.y + dy));
    }

    shoot() {
        const now = Date.now();
        if (now - this.lastShot > this.shootCooldown) {
            this.lastShot = now;
            const bullet = new Bullet(this.x, this.y, this.direction, true);
            bullets.push(bullet);
        }
    }
}

// 敌方坦克
class EnemyTank {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        this.width = 35;
        this.height = 35;
        this.speed = 1 + Math.random();
        this.direction = ['up', 'down', 'left', 'right'][Math.floor(Math.random() * 4)];
        this.color = '#e74c3c';
        this.lastShot = Date.now();
        this.shootCooldown = 2000 + Math.random() * 1000;
        this.changeDirectionTime = Date.now();
        this.directionDuration = 1000 + Math.random() * 2000;
    }

    draw() {
        ctx.save();
        ctx.translate(this.x, this.y);
        
        // 坦克主体
        ctx.fillStyle = this.color;
        ctx.fillRect(-this.width/2, -this.height/2, this.width, this.height);
        
        // 坦克轮廓
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.strokeRect(-this.width/2, -this.height/2, this.width, this.height);
        
        // 炮管
        ctx.fillStyle = '#c0392b';
        if (this.direction === 'up') {
            ctx.fillRect(-2, -this.height/2 - 12, 4, 12);
        } else if (this.direction === 'down') {
            ctx.fillRect(-2, this.height/2, 4, 12);
        } else if (this.direction === 'left') {
            ctx.fillRect(-this.width/2 - 12, -2, 12, 4);
        } else if (this.direction === 'right') {
            ctx.fillRect(this.width/2, -2, 12, 4);
        }
        
        ctx.restore();
    }

    update() {
        const now = Date.now();
        
        // 改变移动方向
        if (now - this.changeDirectionTime > this.directionDuration) {
            this.direction = ['up', 'down', 'left', 'right'][Math.floor(Math.random() * 4)];
            this.changeDirectionTime = now;
            this.directionDuration = 1000 + Math.random() * 2000;
        }

        // 移动
        let dx = 0, dy = 0;
        if (this.direction === 'up') dy = -this.speed;
        else if (this.direction === 'down') dy = this.speed;
        else if (this.direction === 'left') dx = -this.speed;
        else if (this.direction === 'right') dx = this.speed;

        this.x += dx;
        this.y += dy;

        // 边界检测
        if (this.x < this.width/2 || this.x > canvas.width - this.width/2) {
            this.x -= dx;
            this.direction = this.direction === 'left' ? 'right' : 'left';
        }
        if (this.y < this.height/2 || this.y > canvas.height - this.height/2) {
            this.y -= dy;
            this.direction = this.direction === 'up' ? 'down' : 'up';
        }

        // 射击
        if (now - this.lastShot > this.shootCooldown) {
            this.lastShot = now;
            const bullet = new Bullet(this.x, this.y, this.direction, false);
            bullets.push(bullet);
        }
    }
}

// 子弹类
class Bullet {
    constructor(x, y, direction, isPlayerBullet) {
        this.x = x;
        this.y = y;
        this.width = 5;
        this.height = 10;
        this.speed = 6;
        this.direction = direction;
        this.isPlayerBullet = isPlayerBullet;
        this.color = isPlayerBullet ? '#f1c40f' : '#e67e22';
    }

    draw() {
        ctx.fillStyle = this.color;
        ctx.fillRect(this.x - this.width/2, this.y - this.height/2, this.width, this.height);
    }

    update() {
        if (this.direction === 'up') this.y -= this.speed;
        else if (this.direction === 'down') this.y += this.speed;
        else if (this.direction === 'left') this.x -= this.speed;
        else if (this.direction === 'right') this.x += this.speed;
    }

    isOutOfBounds() {
        return this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height;
    }
}

// 爆炸效果
class Explosion {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        this.radius = 5;
        this.maxRadius = 30;
        this.alpha = 1;
    }

    draw() {
        ctx.save();
        ctx.globalAlpha = this.alpha;
        ctx.fillStyle = '#ff6b6b';
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#feca57';
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.restore();
    }

    update() {
        this.radius += 2;
        this.alpha -= 0.05;
    }

    isDone() {
        return this.alpha <= 0;
    }
}

// 游戏对象
const player = new PlayerTank();
let enemies = [];
let bullets = [];
let explosions = [];

// 键盘控制
const keys = {};
window.addEventListener('keydown', (e) => {
    keys[e.key.toLowerCase()] = true;
    
    if (e.key === ' ') {
        e.preventDefault();
        if (!gameState.paused && !gameState.gameOver) {
            player.shoot();
        }
    }
    
    if (e.key.toLowerCase() === 'p') {
        e.preventDefault();
        if (!gameState.gameOver) {
            gameState.paused = !gameState.paused;
        }
    }
});

window.addEventListener('keyup', (e) => {
    keys[e.key.toLowerCase()] = false;
});

// 碰撞检测
function checkCollision(obj1, obj2) {
    return obj1.x < obj2.x + obj2.width/2 &&
           obj1.x + obj1.width/2 > obj2.x &&
           obj1.y < obj2.y + obj2.height/2 &&
           obj1.y + obj1.height/2 > obj2.y;
}

// 生成敌方坦克
function spawnEnemies() {
    const count = 3 + gameState.level;
    for (let i = 0; i < count; i++) {
        const x = Math.random() * (canvas.width - 50) + 25;
        const y = Math.random() * (canvas.height / 2);
        enemies.push(new EnemyTank(x, y));
    }
}

// 更新游戏
function update() {
    if (gameState.paused || gameState.gameOver) return;

    // 玩家移动
    if (keys['w'] || keys['arrowup']) {
        player.move(0, -player.speed);
        player.direction = 'up';
    }
    if (keys['s'] || keys['arrowdown']) {
        player.move(0, player.speed);
        player.direction = 'down';
    }
    if (keys['a'] || keys['arrowleft']) {
        player.move(-player.speed, 0);
        player.direction = 'left';
    }
    if (keys['d'] || keys['arrowright']) {
        player.move(player.speed, 0);
        player.direction = 'right';
    }

    // 更新敌方坦克
    enemies.forEach(enemy => enemy.update());

    // 更新子弹
    bullets = bullets.filter(bullet => {
        bullet.update();
        
        if (bullet.isOutOfBounds()) return false;

        // 玩家子弹击中敌方坦克
        if (bullet.isPlayerBullet) {
            for (let i = enemies.length - 1; i >= 0; i--) {
                if (checkCollision(bullet, enemies[i])) {
                    explosions.push(new Explosion(enemies[i].x, enemies[i].y));
                    enemies.splice(i, 1);
                    gameState.score += 100;
                    updateUI();
                    return false;
                }
            }
        } else {
            // 敌方子弹击中玩家
            if (checkCollision(bullet, player)) {
                explosions.push(new Explosion(player.x, player.y));
                gameState.lives--;
                updateUI();
                player.x = canvas.width / 2;
                player.y = canvas.height - 60;
                
                if (gameState.lives <= 0) {
                    endGame();
                }
                return false;
            }
        }

        return true;
    });

    // 更新爆炸效果
    explosions = explosions.filter(explosion => {
        explosion.update();
        return !explosion.isDone();
    });

    // 检查关卡完成
    if (enemies.length === 0) {
        gameState.level++;
        updateUI();
        setTimeout(() => spawnEnemies(), 1000);
    }
}

// 渲染游戏
function render() {
    // 清空画布
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 绘制网格背景
    ctx.strokeStyle = '#2a2a2a';
    ctx.lineWidth = 1;
    for (let i = 0; i < canvas.width; i += 40) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i, canvas.height);
        ctx.stroke();
    }
    for (let i = 0; i < canvas.height; i += 40) {
        ctx.beginPath();
        ctx.moveTo(0, i);
        ctx.lineTo(canvas.width, i);
        ctx.stroke();
    }

    // 绘制游戏对象
    player.draw();
    enemies.forEach(enemy => enemy.draw());
    bullets.forEach(bullet => bullet.draw());
    explosions.forEach(explosion => explosion.draw());

    // 暂停提示
    if (gameState.paused) {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#fff';
        ctx.font = '48px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('游戏暂停', canvas.width / 2, canvas.height / 2);
        ctx.font = '24px Arial';
        ctx.fillText('按 P 继续', canvas.width / 2, canvas.height / 2 + 40);
    }
}

// 更新UI
function updateUI() {
    document.getElementById('lives').textContent = gameState.lives;
    document.getElementById('score').textContent = gameState.score;
    document.getElementById('level').textContent = gameState.level;
}

// 游戏结束
function endGame() {
    gameState.gameOver = true;
    document.getElementById('finalScore').textContent = `最终得分: ${gameState.score} | 关卡: ${gameState.level}`;
    document.getElementById('gameOver').style.display = 'block';
}

// 游戏主循环
function gameLoop() {
    update();
    render();
    requestAnimationFrame(gameLoop);
}

// 初始化游戏
function init() {
    spawnEnemies();
    updateUI();
    gameLoop();
}

// 启动游戏
init();
