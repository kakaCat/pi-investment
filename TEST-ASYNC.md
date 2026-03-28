测试异步任务系统

启动 pi-investment agent，然后输入：

```
帮我并行获取这3只股票的信息：600519, 000858, 601318
```

Agent 应该：
1. 使用 plan_task 规划
2. 使用 task_create 创建3个任务
3. 使用 task_execute_async 并行执行
4. 等待后台任务完成
5. 收到 <background-results> 通知
6. 汇总结果

预期行为：
- 3个任务同时启动
- Agent 不阻塞，可以继续其他工作
- 几秒后自动收到结果通知
- Agent 汇总分析3只股票
