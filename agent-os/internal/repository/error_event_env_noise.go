package repository

import (
	"fmt"
	"regexp"
	"time"
)

// 环境类噪声自动归档（2026-09-11 立，窗口 w-f4aa1f6a，REQ-a42aa4）
//
// 背景：error_events 的 open 队列应当只承载"需要人/agent 动手"的问题。但有些
// 事件根因在外网/本机网络层，本机无法根治，且会长期反复复发——每次复发都会按
// Upsert 的"复现即复开"语义把已归档事件顶回 open（实证：事件 5b4f7a85 在
// 2026-09-10 22:34 → 09-11 01:07 内复发 5 次，第 5 次把 ignored 顶回 open）。
//
// 设计（保守优先，宁可少归档也不掩盖真问题）：
//  1. 只归档**显式枚举**的规则命中项，规则必须带实测依据注释；不做"看起来像
//     网络问题就归档"的模糊匹配。
//  2. 归档不等于隐藏：状态置 ignored 并写入带规则名+复发次数的 resolution_note，
//     台账可查、可 reopen。
//  3. 安全阀：同一指纹在 escalationWindow 内达到 escalationCount 次（速率异常，
//     可能是真退化而非抖动）→ 不再归档，强制保持/升为 open 并写明速率。
type envNoiseRule struct {
	Name string         // 规则名（写入 note，便于回溯）
	Re   *regexp.Regexp // 命中 msg 或 detail
	Why  string         // 为什么判为环境类（实测依据）
}

const (
	// 速率安全阀：同一指纹在 15 分钟窗口内累计 >=3 次即视为"速率异常"。
	envNoiseEscalationWindow    = 15 * time.Minute
	envNoiseEscalationThreshold = 3
)

// envNoiseRules 已知环境类噪声规则（每条都要求有实测依据）
var envNoiseRules = []envNoiseRule{
	{
		Name: "eastmoney-proxy-unreachable",
		Re: regexp.MustCompile("(?i)(ProxyError|Unable to connect to proxy|RemoteDisconnected|Connection aborted)" +
			"|东方财富数据源获取失败"),
		Why: "本机对 push2his.eastmoney.com 直连被网络封锁，必须经系统代理 127.0.0.1:7897；" +
			"代理出口到该站间歇不可达（实测：同刻经代理访问百度 200/0.1s 证明代理进程健康，" +
			"东财经代理 ProxyError、直连 RemoteDisconnected）。属外部网络层，本机无法根治。",
	},
	{
		Name: "local-proxy-down",
		Re:   regexp.MustCompile("(?i)(ProxyError|Cannot connect to proxy|connection refused.{0,40}(7897|7890|1087|8888))"),
		Why:  "本机代理进程重启/未监听时的瞬时失败，链路恢复后自愈，非我方缺陷。",
	},
}

// matchEnvNoise 返回命中的环境类规则（未命中返回 nil）
func matchEnvNoise(msg, detail string) *envNoiseRule {
	hay := msg + "\n" + detail
	for i := range envNoiseRules {
		if envNoiseRules[i].Re.MatchString(hay) {
			return &envNoiseRules[i]
		}
	}
	return nil
}

// envNoiseEscalated 速率安全阀：窗口内次数超阈值 → 不归档（返回 true + 原因）
func envNoiseEscalated(occurrenceCount int, firstSeen, lastSeen time.Time) (bool, string) {
	if occurrenceCount < envNoiseEscalationThreshold {
		return false, ""
	}
	span := lastSeen.Sub(firstSeen)
	if span <= envNoiseEscalationWindow {
		return true, fmt.Sprintf("同指纹在 %s 内累计 %d 次（阈值 %d 次/%s）",
			span.Round(time.Second), occurrenceCount, envNoiseEscalationThreshold, envNoiseEscalationWindow)
	}
	return false, ""
}

// autoArchiveNote 归档说明（含规则名、实测依据、复发统计与人工恢复方式）
func autoArchiveNote(rule *envNoiseRule, occurrenceCount int, firstSeen, lastSeen time.Time) string {
	return fmt.Sprintf("【自动归档·环境类噪声】规则=%s；复发 %d 次（%s → %s）；判据：%s "+
		"本机无法根治，链路恢复后自愈；如需人工处理请 reopen 或 resolve 并补注。"+
		"注意：15 分钟内复发 >=%d 次会自动升级为 open（速率安全阀）。",
		rule.Name, occurrenceCount,
		firstSeen.Format("2006-01-02 15:04:05"), lastSeen.Format("2006-01-02 15:04:05"),
		rule.Why, envNoiseEscalationThreshold)
}

// escalationNote 速率超阈说明
func escalationNote(rule *envNoiseRule, reason string) string {
	return fmt.Sprintf("【环境类噪声·速率异常，未自动归档】规则=%s；%s。判据：%s "+
		"环境抖动通常零星复发，短时间内密集复发可能意味着链路真退化或依赖方持续不可用，故保持 open 待人工核查。",
		rule.Name, reason, rule.Why)
}
