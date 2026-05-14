# Evolution System Quick Start Guide

**Version**: v1.0  
**Last Updated**: 2026-05-14

---

## What is the Evolution System?

The Evolution System is an automated feedback loop that analyzes your Agent's investment performance and generates optimization suggestions. Think of it as a coach that reviews your Agent's decisions weekly and recommends improvements.

---

## Quick Start (3 Steps)

### 1. Run Evolution Analysis

```bash
npm run evolution
```

This will:
- Collect data from the past week (trades, portfolio, session logs)
- Calculate performance metrics (return, win rate, drawdown)
- Analyze what worked and what didn't
- Generate optimization suggestions

**Output**: `.pi-invest/evolution/YYYY-MM-DD-report.md`

### 2. Review the Report

Open the generated report and look for:

```markdown
## 优化建议

### 建议 #1: 新增工具 - analyze_sector_rotation
**类型**: 新增工具
**原因**: 发现3次买入时机不佳，买在板块轮动末期
**预期效果**: 提升买入时机准确率，预计+2%胜率
**置信度**: 0.78

### 建议 #2: 更新经验 - 避免追涨买入
**类型**: 经验更新
**原因**: 8次追涨买入中6次亏损，平均-3.5%
**预期效果**: 减少冲动买入，降低回撤
**置信度**: 0.85
```

### 3. Apply Suggestions (Optional)

If you agree with the suggestions, apply them:

```bash
# Apply specific suggestions by ID
npm run evolution -- --apply sug_001,sug_002

# Or apply all suggestions
npm run evolution -- --apply-all
```

**What happens**:
- New tools are registered in `src/infrastructure/tools/index.ts`
- Experience entries are added to `.pi-invest/experience/experience-base.json`
- System prompt is updated with new rules/parameters
- A new version is saved in `src/core/agent/versions/`

---

## How It Works (Simple Explanation)

```
Week 1: Agent makes decisions → Results recorded
Week 2: Evolution analyzes results → Finds patterns
Week 3: You apply suggestions → Agent improves
Week 4: Repeat...
```

**Example**:
1. Agent bought 5 stocks that were already up 8%+ that day
2. 4 out of 5 dropped the next day (bought at peak)
3. Evolution detects pattern: "追涨买入" (chasing rallies) → low win rate
4. Suggestion: Add experience entry "avoid buying stocks up >5% intraday"
5. Next week: Agent checks experience before buying, avoids this mistake

---

## Common Use Cases

### Use Case 1: Monthly Performance Review

```bash
# Run at end of month
npm run evolution

# Review report
cat .pi-invest/evolution/2026-05-31-report.md

# Apply improvements
npm run evolution -- --apply-all
```

### Use Case 2: After a Bad Week

```bash
# Immediate analysis
npm run evolution

# Look for what went wrong
# Apply defensive suggestions (risk management, stop loss)
npm run evolution -- --apply sug_003,sug_005
```

### Use Case 3: Check Experience Before Decision

When Agent is making a decision, it can query the experience base:

**Agent uses tool**: `query_experience`

```json
{
  "scenario": "MACD金叉，考虑买入",
  "symbol": "600519",
  "conditions": ["MACD金叉", "成交量放大"]
}
```

**Returns**:
```json
{
  "scenario": "MACD金叉+成交量确认",
  "outcomes": {
    "total_cases": 12,
    "win_rate": 0.75,
    "avg_return": 0.058
  },
  "recommendation": "moderate",
  "reason": "历史数据显示该模式胜率较高"
}
```

---

## Key Concepts

### 1. Performance Gap (性能差距)

```
Gap = Target Return - Actual Return
```

- **Small gap (<2%)**: Minor tweaks (update experience)
- **Medium gap (2-5%)**: Add/remove tools, update rules
- **Large gap (>5%)**: Major changes (new strategy, new tools)

### 2. Attribution Analysis (归因分析)

When there's a gap, the system asks: **Why?**

**Two possibilities**:
1. **Target problem**: Goal was unrealistic (e.g., expecting 10% in a -5% market)
2. **Capability problem**: Agent made poor decisions (e.g., bad stock picks, missed stop losses)

**Example**:
- Market returned -2%, you returned -8% → **Capability problem** (you underperformed)
- Market returned +5%, you returned +3% → **Capability problem** (you underperformed)
- Market returned +2%, you returned +1% → **Target problem** (expecting +10% was unrealistic)

### 3. Experience Base (经验库)

A database of "what worked" and "what didn't":

```json
{
  "scenario": "追涨买入",
  "outcomes": {
    "total_cases": 8,
    "win_rate": 0.25,
    "avg_return": -0.035
  },
  "recommendation": "avoid"
}
```

Agent checks this before making decisions to avoid repeating mistakes.

---

## Configuration

### Set Performance Target

Edit `.pi-invest/config.json`:

```json
{
  "evolution": {
    "target_weekly_return": 0.02,  // 2% per week
    "target_monthly_return": 0.08  // 8% per month
  }
}
```

**How to set realistic targets**:
- Check market average (e.g., CSI 300 returned +1.5% last month)
- Add alpha (your edge): +1% to +3%
- Result: Target = Market + Alpha = 1.5% + 2% = 3.5%

### Automatic Weekly Run

The system runs automatically every Sunday at 23:00.

**To disable**:
Edit `src/services/operations/cron-service.ts` and comment out:

```typescript
// cron.schedule('0 23 * * 0', async () => {
//   await evolutionService.runWeeklyEvolution();
// });
```

---

## Troubleshooting

### Problem: "No data to analyze"

**Cause**: Not enough trades or sessions in the period

**Solution**: 
- Wait until you have at least 3 trades
- Or manually specify a longer period: `npm run evolution -- --days 14`

### Problem: "All suggestions have low confidence"

**Cause**: Not enough data to identify clear patterns

**Solution**:
- Continue trading for another week
- Don't apply low-confidence suggestions (<0.5)

### Problem: "Applied suggestion but performance didn't improve"

**Cause**: 
- Suggestion was wrong (happens ~20% of time)
- Not enough time to see effect (need 1-2 weeks)

**Solution**:
- Rollback: `npm run evolution -- --rollback v6`
- Wait longer before judging
- Check if market conditions changed

---

## Best Practices

### ✅ Do

- Run evolution weekly (consistency matters)
- Review reports carefully before applying
- Apply 2-3 suggestions at a time (not all at once)
- Give suggestions 1-2 weeks to show effect
- Keep notes on what you applied and why

### ❌ Don't

- Apply suggestions blindly without reading
- Apply low-confidence suggestions (<0.5)
- Change too many things at once (can't tell what worked)
- Expect immediate results (need time to validate)
- Ignore rollback when things get worse

---

## Example Workflow

**Week 1** (May 1-7):
- Agent makes 5 trades
- 2 wins, 3 losses
- Weekly return: -2%

**Week 2** (May 8):
- Run: `npm run evolution`
- Report shows: "追涨买入" pattern → low win rate
- Apply: `npm run evolution -- --apply sug_002` (add experience: avoid chasing)

**Week 3** (May 8-14):
- Agent makes 4 trades
- Checks experience before each trade
- Avoids 2 "chasing" opportunities
- 3 wins, 1 loss
- Weekly return: +3%

**Week 4** (May 15):
- Run: `npm run evolution`
- Report shows: improvement confirmed
- Continue with current configuration

---

## Next Steps

1. **Read full documentation**: `docs/evolution-system-usage.md`
2. **Check design specs**: `docs/superpowers/specs/2026-05-14-agent-evolution-system-design.md`
3. **Run your first analysis**: `npm run evolution`
4. **Join the feedback loop**: Apply → Observe → Improve

---

## FAQ

**Q: How often should I run evolution?**  
A: Weekly is recommended. Monthly works too, but you'll iterate slower.

**Q: Can I manually add experiences?**  
A: Yes, edit `.pi-invest/experience/experience-base.json` directly. Set confidence to 0.5 for manual entries.

**Q: What if I disagree with a suggestion?**  
A: Don't apply it. The system makes recommendations, you make decisions.

**Q: Can I undo applied suggestions?**  
A: Yes, use rollback: `npm run evolution -- --rollback v6`

**Q: Does this work for crypto/forex/futures?**  
A: Currently optimized for A-shares. Adaptable to other markets with minor changes.

---

**Ready to start?** Run `npm run evolution` now!
