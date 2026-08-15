package main

import (
	"database/sql"
	"fmt"
	_ "github.com/lib/pq"
)

func main() {
	// 测试不同的连接字符串格式
	connStrings := []string{
		"host=127.0.0.1 port=5432 user=yunpeng password= dbname=agent_os sslmode=disable",
		"host=127.0.0.1 port=5432 user=yunpeng dbname=agent_os sslmode=disable",
		"postgres://yunpeng@127.0.0.1:5432/agent_os?sslmode=disable",
	}

	for i, connStr := range connStrings {
		fmt.Printf("\n--- Test %d ---\n", i+1)
		fmt.Printf("Connecting with: %s\n", connStr)

		db, err := sql.Open("postgres", connStr)
		if err != nil {
			fmt.Printf("Error opening: %v\n", err)
			continue
		}

		if err := db.Ping(); err != nil {
			fmt.Printf("Error pinging: %v\n", err)
			db.Close()
			continue
		}

		var dbname string
		err = db.QueryRow("SELECT current_database()").Scan(&dbname)
		if err != nil {
			fmt.Printf("Error querying: %v\n", err)
			db.Close()
			continue
		}

		fmt.Printf("✓ Connected to database: %s\n", dbname)
		db.Close()
	}
}
