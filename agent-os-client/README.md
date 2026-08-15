# @pi-investment/agent-os-client

TypeScript SDK for Agent OS - HTTP client for scheduler, memory, decision, notification, and resource management.

## Installation

```bash
npm install @pi-investment/agent-os-client
```

## Quick Start

```typescript
import { AgentOSClient } from '@pi-investment/agent-os-client';

const client = new AgentOSClient({
  baseURL: 'http://localhost:8080',
  agentId: 'fin-agent',
  timeout: 30000,
});

// Check health
const health = await client.health();
console.log(health); // { status: 'ok', version: '0.1.0' }
```

## Features

- ✅ **Scheduler Client** - Manage tasks and executions
- ✅ **Memory Client** - Store and search agent memories
- ✅ **Decision Client** - Record and track decisions
- ✅ **Notification Client** - Send notifications via Feishu/WeChat/Email
- ✅ **Resource Client** - Manage quotas and namespaces
- ✅ **Type-safe** - Full TypeScript support
- ✅ **Error handling** - Structured error responses
- ✅ **HTTP-based** - No CLI dependencies

## Usage

### Scheduler

```typescript
// Register a task
const task = await client.scheduler.registerTask({
  name: 'daily-pool-refresh',
  description: 'Refresh stock pools every day',
  owner: 'fin-agent',
  cron: '0 2 * * *',
  priority: 8,
  tags: ['pool', 'daily'],
  webhook_url: 'http://localhost:3000/api/webhook/trigger',
});

// List tasks
const tasks = await client.scheduler.listTasks({ owner: 'fin-agent' });

// Trigger a task manually
const execution = await client.scheduler.triggerTask(task.id);

// Update execution status (called by agent after task completion)
await client.scheduler.updateExecution(execution.id, {
  status: 'completed',
  result: { pools_refreshed: 5 },
});
```

### Memory

```typescript
// Write a memory
const memory = await client.memory.write({
  namespace: 'fin-agent',
  content: '600519.SH PE ratio dropped below 20, potential buy signal',
  category: 'signal',
  importance: 0.85,
  metadata: { symbol: '600519.SH', pe: 18.5 },
});

// Search memories
const results = await client.memory.search({
  namespace: 'fin-agent',
  query: '600519 buy signal',
  top_k: 10,
  min_importance: 0.7,
});

results.forEach((result) => {
  console.log(`Score: ${result.score}, Content: ${result.memory.content}`);
});

// List recent memories
const recentMemories = await client.memory.list({
  namespace: 'fin-agent',
  category: 'signal',
  limit: 50,
});
```

### Decision

```typescript
// Record a decision
const decision = await client.decision.record({
  namespace: 'fin-agent',
  action: 'buy',
  targets: ['600519.SH'],
  reasoning: 'PE ratio attractive + strong fundamentals',
  confidence: 0.85,
  metadata: { price: 1850, quantity: 100 },
});

// Track decision outcome
await client.decision.track({
  decision_id: decision.id,
  result: 'executed',
  outcome: { executed_price: 1845, profit_loss: 500 },
});

// Query decisions
const buyDecisions = await client.decision.query('buy', ['600519.SH'], 'fin-agent');

// Get statistics
const stats = await client.decision.stats('fin-agent');
console.log(`Success rate: ${stats.success_rate}%`);
```

### Notification

```typescript
// Send a notification
await client.notification.send({
  title: '交易信号',
  content: '600519.SH 出现买入信号，PE=18.5',
  urgency: 'high',
  metadata: { symbol: '600519.SH' },
});

// List channels
const channels = await client.notification.listChannels();

// Test a channel
await client.notification.testChannel(channels[0].id);
```

### Resource

```typescript
// Get quota
const quota = await client.resource.getQuota();
console.log(`Tokens: ${quota.token_used}/${quota.token_quota}`);
console.log(`Memory: ${quota.memory_used_mb}MB/${quota.memory_quota_mb}MB`);

// Check if quota is available
const check = await client.resource.checkQuota(undefined, 10000);
if (!check.available) {
  console.log('Insufficient quota');
}

// Get usage history
const usage = await client.resource.getUsage(undefined, 24); // Last 24 hours
```

## Error Handling

```typescript
import { AgentOSClient, AgentOSError } from '@pi-investment/agent-os-client';

try {
  await client.scheduler.getTask('non-existent-id');
} catch (error) {
  if (error instanceof AgentOSError) {
    console.error(`Error ${error.code}: ${error.message}`);
    console.error('Details:', error.details);
    console.error('Status:', error.statusCode);
  }
}
```

## Configuration

```typescript
const client = new AgentOSClient({
  baseURL: 'http://localhost:8080',    // Agent OS API URL
  agentId: 'fin-agent',                 // Your agent ID
  apiKey: 'your-api-key',               // Optional API key
  timeout: 30000,                       // Request timeout (ms)
});
```

## Environment Variables

```bash
# .env
AGENT_OS_API_URL=http://localhost:8080
AGENT_ID=fin-agent
AGENT_OS_API_KEY=your-api-key
```

```typescript
const client = new AgentOSClient({
  baseURL: process.env.AGENT_OS_API_URL || 'http://localhost:8080',
  agentId: process.env.AGENT_ID,
  apiKey: process.env.AGENT_OS_API_KEY,
});
```

## API Reference

### AgentOSClient

Main client class with sub-clients:

- `client.scheduler` - SchedulerClient
- `client.memory` - MemoryClient
- `client.decision` - DecisionClient
- `client.notification` - NotificationClient
- `client.resource` - ResourceClient

### Methods

#### SchedulerClient

- `listTasks(filters?)` - List tasks
- `registerTask(request)` - Register a new task
- `getTask(taskId)` - Get task details
- `updateTask(taskId, updates)` - Update task
- `deleteTask(taskId)` - Delete task
- `triggerTask(taskId, params?)` - Trigger task manually
- `pauseTask(taskId)` - Pause task
- `resumeTask(taskId)` - Resume task
- `listExecutions(filters?)` - List executions
- `getExecution(executionId)` - Get execution details
- `updateExecution(executionId, update)` - Update execution status
- `cancelExecution(executionId)` - Cancel execution

#### MemoryClient

- `write(request)` - Write a memory
- `search(request)` - Search memories
- `get(id)` - Get memory by ID
- `list(filters?)` - List memories
- `update(id, updates)` - Update memory
- `delete(id)` - Delete memory
- `stats(namespace?)` - Get statistics
- `recallAudit(namespace, context?)` - Trigger memory consolidation

#### DecisionClient

- `record(request)` - Record a decision
- `get(id)` - Get decision by ID
- `list(filters?)` - List decisions
- `track(request)` - Update decision result
- `stats(namespace?)` - Get statistics
- `query(action, targets?, namespace?)` - Query decisions

#### NotificationClient

- `send(request)` - Send notification
- `listChannels()` - List channels
- `getChannel(id)` - Get channel details
- `list(filters?)` - List notification history
- `get(id)` - Get notification by ID
- `testChannel(channelId, testMessage?)` - Test channel

#### ResourceClient

- `getQuota(agentId?)` - Get quota
- `listQuotas()` - List all quotas
- `getNamespace(name)` - Get namespace info
- `listNamespaces()` - List namespaces
- `getUsage(agentId?, hours?)` - Get usage history
- `checkQuota(agentId?, tokensNeeded?)` - Check quota availability

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Test
npm test
```

## License

MIT
