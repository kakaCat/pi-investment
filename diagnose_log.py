#!/usr/bin/env python3
"""日志诊断工具 - 检测串行执行、上下文膨胀、性能瓶颈"""
import json
import sys
from collections import defaultdict

def diagnose_session(log_file):
    """诊断单个 session 日志"""

    # 数据收集
    llm_calls = []
    tool_calls_by_turn = defaultdict(list)
    tool_durations = []

    with open(log_file) as f:
        for line in f:
            e = json.loads(line)
            evt = e.get("event")
            turn = e.get("turn_index")

            if evt == "llm.end":
                llm_calls.append({
                    "turn": turn,
                    "input": e.get("input_tokens", 0),
                    "output": e.get("output_tokens", 0),
                    "total": e.get("total_tokens", 0),
                    "duration": e.get("duration_ms", 0),
                    "reasoning": e.get("reasoning_length", 0)
                })

            elif evt == "tool.call":
                tool_calls_by_turn[turn].append(e.get("tool_name"))

            elif evt == "tool.result":
                dur = e.get("duration_ms")
                if dur:
                    tool_durations.append({
                        "tool": e.get("tool_name"),
                        "duration": dur,
                        "turn": turn
                    })

    # 诊断报告
    print("=" * 60)
    print("📊 日志诊断报告")
    print("=" * 60)

    # 1. 串行执行检测
    serial_turns = [t for t, tools in tool_calls_by_turn.items() if len(tools) == 1]
    parallel_turns = [t for t, tools in tool_calls_by_turn.items() if len(tools) > 1]

    print(f"\n🔴 串行执行问题:")
    print(f"   串行轮次: {len(serial_turns)}/{len(tool_calls_by_turn)} ({len(serial_turns)/len(tool_calls_by_turn)*100:.0f}%)")
    print(f"   并行轮次: {len(parallel_turns)}")

    if serial_turns:
        print(f"   前5个串行轮次: {serial_turns[:5]}")

    # 2. Token 消耗分析
    if llm_calls:
        total_tokens = sum(c["total"] for c in llm_calls)
        max_input = max(llm_calls, key=lambda x: x["input"])
        avg_input = sum(c["input"] for c in llm_calls) / len(llm_calls)

        print(f"\n🔴 Token 消耗:")
        print(f"   总轮次: {len(llm_calls)}")
        print(f"   总消耗: {total_tokens:,} tokens")
        print(f"   平均输入: {avg_input:,.0f} tokens/轮")
        print(f"   最大输入: Turn {max_input['turn']} = {max_input['input']:,} tokens")

        # 上下文膨胀检测
        if max_input['input'] > 20000:
            print(f"   ⚠️  上下文膨胀: 超过 20k tokens")

    # 3. 性能瓶颈
    if llm_calls:
        avg_duration = sum(c["duration"] for c in llm_calls) / len(llm_calls)
        slow_calls = [c for c in llm_calls if c["duration"] > 10000]

        print(f"\n🔴 性能瓶颈:")
        print(f"   平均耗时: {avg_duration:.0f}ms/轮")
        print(f"   慢调用(>10s): {len(slow_calls)} 次")

        if slow_calls:
            print(f"   最慢: Turn {slow_calls[0]['turn']} = {slow_calls[0]['duration']}ms")

    # 4. 工具执行分析
    if tool_durations:
        avg_tool_dur = sum(t["duration"] for t in tool_durations) / len(tool_durations)
        slow_tools = [t for t in tool_durations if t["duration"] > 5000]

        print(f"\n🔴 工具执行:")
        print(f"   平均耗时: {avg_tool_dur:.0f}ms/工具")
        print(f"   慢工具(>5s): {len(slow_tools)} 次")

        if slow_tools:
            for t in slow_tools[:3]:
                print(f"   - {t['tool']}: {t['duration']}ms (Turn {t['turn']})")

    # 5. 思维链检测
    reasoning_count = sum(1 for c in llm_calls if c["reasoning"] > 0)
    print(f"\n✅ 思维链记录:")
    print(f"   有思维链: {reasoning_count}/{len(llm_calls)} 轮")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python diagnose_log.py <events.jsonl>")
        sys.exit(1)

    diagnose_session(sys.argv[1])
