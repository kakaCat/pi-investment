package repository

import (
	"strings"
	"testing"
	"time"
)

// 环境类噪声规则回归测试（2026-09-11，w-f4aa1f6a）
//
// 两个方向都要测：①该归档的确实命中；②**真代码缺陷/业务异常不得被误归档**
// ——后者比前者更重要，误归档等于把真问题静音。

func TestMatchEnvNoise_EastmoneyProxyTransient(t *testing.T) {
	cases := []struct {
		name   string
		msg    string
		detail string
	}{
		{"akshare 资金流 ProxyError", "东方财富数据源获取失败（已重试3次）: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))", ""},
		{"裸 ProxyError", "HTTP request failed: ProxyError(Unable to connect to proxy)", "Traceback ..."},
		{"ProxyError 只在 detail", "数据源获取失败", "requests.exceptions.ProxyError: Cannot connect to proxy"},
		{"显式本地代理不可达", "get https://x: ProxyError", "connection refused 127.0.0.1:7897"},
		{"多源全源失败+连接类错误（窄口径 AND 命中）", "❌ 所有数据源均失败，无法获取 600519 K线数据", "ConnectionError: HTTPSConnectionPool … Connection aborted."},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if rule := matchEnvNoise(c.msg, c.detail); rule == nil {
				t.Fatalf("期望命中环境类规则，实际未命中：msg=%q", c.msg)
			}
		})
	}
}

func TestMatchEnvNoise_DoesNotMaskRealBugs(t *testing.T) {
	cases := []struct {
		name   string
		msg    string
		detail string
	}{
		{"NoneType 属性错误（真缺陷）", "扫描抄底机会失败: 'NoneType' object has no attribute 'get_active_events'", "Traceback (most recent call last):\n  File \"manipulation_detector.py\""},
		{"akshare 签名断裂（真缺陷）", "AkShare 融资融券数据源获取失败: stock_margin_detail_sse() got an unexpected keyword argument 'symbol'", "TypeError"},
		{"调度任务不存在（真缺陷）", "Task 251 not found in scheduler_tasks", ""},
		{"未经网络层的通用失败", "检查成交量失败: 600519", ""},
		{"全源失败但无连接类错误（可能是配置/接口问题，不得归档）", "❌ 所有数据源均失败，无法获取 600519 K线数据", "KeyError: 'sina' 数据源未注册，provider chain 为空"},
		{"空消息", "", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if rule := matchEnvNoise(c.msg, c.detail); rule != nil {
				t.Fatalf("真缺陷被误判为环境类噪声（规则=%s），会掩盖问题：msg=%q", rule.Name, c.msg)
			}
		})
	}
}

func TestEnvNoiseEscalated_RateValve(t *testing.T) {
	now := time.Date(2026, 9, 11, 1, 0, 0, 0, time.UTC)
	t.Run("窗口内密集复发→升级", func(t *testing.T) {
		esc, reason := envNoiseEscalated(3, now.Add(-10*time.Minute), now)
		if !esc {
			t.Fatal("15 分钟内 3 次应触发速率安全阀")
		}
		if !strings.Contains(reason, "3") {
			t.Fatalf("原因应含次数，实际=%q", reason)
		}
	})
	t.Run("零星复发不升级", func(t *testing.T) {
		// 实证场景：事件 5b4f7a85 在 22:34 → 01:07（约 2.5h）内 5 次
		if esc, _ := envNoiseEscalated(5, now.Add(-150*time.Minute), now); esc {
			t.Fatal("跨 2.5h 的 5 次属零星复发，不应升级")
		}
	})
	t.Run("次数未达阈值不升级", func(t *testing.T) {
		if esc, _ := envNoiseEscalated(2, now.Add(-time.Minute), now); esc {
			t.Fatal("阈值 3 次以下不应升级")
		}
	})
}

func TestAutoArchiveNote_IsAuditable(t *testing.T) {
	rule := &envNoiseRule{Name: "demo-rule", Why: "实测依据：某站直连被封"}
	first := time.Date(2026, 9, 10, 22, 34, 0, 0, time.UTC)
	last := time.Date(2026, 9, 11, 1, 7, 0, 0, time.UTC)
	note := autoArchiveNote(rule, 5, first, last)
	for _, want := range []string{"demo-rule", "5", "2026-09-10 22:34:00", "reopen", "速率安全阀"} {
		if !strings.Contains(note, want) {
			t.Fatalf("归档说明应含 %q，实际=%q", want, note)
		}
	}
}
