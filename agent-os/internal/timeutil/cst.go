// Package timeutil 统一项目时间口径：**北京时间（UTC+8）**。
//
// 2026-09-11（w-f4aa1f6a）：项目所有对外时间以北京时间为准。此前
// internal/repository/{board_web,error_event}_repository.go 等写入用 time.Now().UTC()，
// 与日志（zap, +0800）、数据库（timestamptz / Asia-Shanghai）、launchd 口径不一致，
// 前端展示与排障都要额外换算，且极易误读（本次会话就因 v2 日志用 UTC 而把
// 13:07 读成 05:07Z 误判时间线）。
package timeutil

import "time"

// CST 北京时间（UTC+8）。中国不实行夏令时，故用固定偏移即可。
var CST = time.FixedZone("CST", 8*3600)

// Now 返回北京时间的当前时刻。
func Now() time.Time { return time.Now().In(CST) }

// RFC3339Nano 返回北京时间的 RFC3339Nano 字符串（带 +08:00 偏移）。
func RFC3339Nano(t time.Time) string { return t.In(CST).Format(time.RFC3339Nano) }
