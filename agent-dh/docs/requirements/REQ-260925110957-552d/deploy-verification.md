# 部署验证文档

**任务**: t-97f31d 部署验证  
**需求**: REQ-260925110957-552d  
**日期**: 2026-09-25

## 验收标准

1. 重启后工具表出现 reqboard_run_status
2. 调用 reqboard_task_run 返回结构化结果（dispatched + jobId）
3. 原生 job_list 可见 kind=reqboard 的 job
4. 跑完后收到原生 completion notice
5. reqboard_run_status 查询返回运行态快照
6. A11: 原生 job_kill 能终止链

## 验证步骤

### 1. 重启 Profile

```bash
cd agent-dh
./scripts/restart-with-build.sh
```

或手动：
```bash
# 符号链接检查与修复
python3 scripts/relink-profile.py

# 重启服务
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh
```

### 2. 验证工具注册

在 DSH Web UI (http://localhost:13080) 中：

1. 打开新会话
2. 输入：请列出所有 reqboard 工具
3. 预期结果：应包含 `reqboard_run_status`

### 3. 验证投递式调用

创建测试需求并调用：

```
请创建一个测试需求，然后调用 reqboard_task_run
```

预期结果：
- 返回时间 <1s
- 返回结构：`{status: 'dispatched', job_id: '...', run_id: '...'}`

### 4. 验证后台任务

调用原生工具：

```
请调用 job_list 查看当前后台任务
```

预期结果：
- 可见 `kind: 'reqboard'` 的任务
- 状态为 `running` 或 `completed`

### 5. 验证运行态查询

```
请使用 reqboard_run_status 查询刚才的运行态
```

预期结果：
- 返回 `{runId, stepIndex, jobStatus, ...}`
- 包含当前进度信息

### 6. 验证完成通知

等待任务完成后：

预期结果：
- 收到原生 completion notice（form=notice）
- 通知内容包含完成信息

### 7. A11 验证：job_kill 终止链

```
请调用 job_kill 终止正在运行的链
```

预期结果：
- 链在下一步停下
- checkpoint 落台账
- 状态可查询

## 验证结果

### ✅ 已验证项

- [ ] 工具表包含 reqboard_run_status
- [ ] reqboard_task_run 返回 dispatched
- [ ] job_list 可见 reqboard 任务
- [ ] 完成后收到通知
- [ ] reqboard_run_status 返回快照
- [ ] job_kill 能终止链

### ❌ 失败项

（记录失败的验证项和原因）

### 📝 备注

（记录验证过程中的观察和问题）

## 验证结论

**状态**: 待验证

**建议**: 
- 本验证需要真实运行时环境
- 需要用户在 DSH Web UI 中手动执行验证步骤
- 每项验证通过后勾选复选框
- 所有项通过后任务可标记为完成
