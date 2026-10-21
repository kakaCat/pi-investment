package cmd

import (
	"fmt"

	"github.com/pi-investment/agent-os/internal/config"
)

// buildPostgresConnStr 组装 lib/pq 关键字式连接串（2026-10-20 修复）。
//
// 背景事故：旧写法 fmt.Sprintf("... password=%s dbname=%s ...") 在密码为空时
// 产出裸 `password=` 标记——libpq/pq 的关键字解析会把后面的 dbname 吞掉，
// 连接静默落到用户同名库（或 PGDATABASE 环境变量指向的库），表全部"不存在"。
// agent-ts 决策日志上传失败的底层根因之一。
// 口径：密码为空则不写 password 键（本机 trust 认证）；非空时单引号包裹。
func buildPostgresConnStr(db config.DatabaseConfig) string {
	s := fmt.Sprintf("host=%s port=%d user=%s dbname=%s sslmode=%s",
		db.Host, db.Port, db.User, db.DBName, db.SSLMode)
	if db.Password != "" {
		s = fmt.Sprintf("host=%s port=%d user=%s password='%s' dbname=%s sslmode=%s",
			db.Host, db.Port, db.User, db.Password, db.DBName, db.SSLMode)
	}
	return s
}
