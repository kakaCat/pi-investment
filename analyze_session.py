#!/usr/bin/env python3
import json
from collections import defaultdict

log_file = ".pi-invest/sessions/20260322T16375_7e647c50/events.jsonl"

llm_turns = []
tool_calls_per_turn = defaultdict(list)
large_outputs = []

with open(log_file) as f:
    for line in f:
        e = json.loads(line)
        evt = e.get("event")
        turn = e.get("turn_index")

        if evt == "llm.end":
            llm_turns.append({
                "turn": turn,
                "input_tokens": e.get("input_tokens", 0),
                "output_tokens": e.get("output_tokens", 0),
                "total_tokens": e.get("total_tokens", 0),
                "duration_ms": e.get("duration_ms", 0)
            })
        elif evt == "tool.call":
            tool_calls_per_turn[turn].append(e.get("tool_name"))
        elif evt == "tool.result":
            result = e.get("result", "")
            if len(str(result)) > 10000:
                large_outputs.append({
                    "turn": turn,
                    "tool": e.get("tool_name"),
                    "size": len(str(result))
                })

# 问题1: 串行调用
single_tool_turns = [t for t, tools in tool_calls_per_turn.items() if len(tools) == 1]
print(f"## 问题1: 串行工具调用")
print(f"单工具轮次: {len(single_tool_turns)}/{len(tool_calls_per_turn)}")
if tool_calls_per_turn:
    print(f"串行率: {len(single_tool_turns)/len(tool_calls_per_turn)*100:.1f}%")
print(f"前10个串行轮次: {sorted(single_tool_turns)[:10]}\n")

# 问题2: Token消耗
print(f"## 问题2: Token消耗")
if llm_turns:
    total = sum(t["total_tokens"] for t in llm_turns)
    max_turn = max(llm_turns, key=lambda x: x["input_tokens"])
    avg_duration = sum(t["duration_ms"] for t in llm_turns) / len(llm_turns)
    print(f"总轮次: {len(llm_turns)}")
    print(f"总tokens: {total:,}")
    print(f"平均耗时: {avg_duration:.0f}ms/轮")
    print(f"最大输入: Turn {max_turn['turn']} = {max_turn['input_tokens']:,} tokens\n")

# 问题3: 并行情况
multi_tool_turns = [t for t, tools in tool_calls_per_turn.items() if len(tools) > 1]
print(f"## 问题3: 并行执行情况")
print(f"并行轮次: {len(multi_tool_turns)}/{len(tool_calls_per_turn)}")
if multi_tool_turns:
    for t in sorted(multi_tool_turns)[:3]:
        print(f"  Turn {t}: {len(tool_calls_per_turn[t])} 工具 - {tool_calls_per_turn[t][:3]}")
print()

# 问题4: 大输出
if large_outputs:
    print(f"## 问题4: 超大工具输出 (>10KB)")
    for item in large_outputs[:5]:
        print(f"Turn {item['turn']}: {item['tool']} = {item['size']:,} 字符")
