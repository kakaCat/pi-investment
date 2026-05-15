# Feishu Notification System Design

**Date:** 2026-05-15  
**Status:** Approved  
**Goal:** Transform Feishu into a unified agent communication and notification module

---

## Overview

This design establishes Feishu as the primary input/output interface and notification system for the Pi Investment agent. The system provides a decoupled, extensible architecture that allows the agent to send rich notifications (trade signals, market briefs, risk warnings) while maintaining flexibility to add other notification channels in the future.

---

## Architecture

### Core Components

```
NotificationService (unified interface)
    ↓
NotificationChannel (abstract base class)
    ↓
FeishuChannel (Feishu implementation)
```

### Component Responsibilities

**NotificationService**
- Provides unified notification API (`send`, `sendCard`, `sendImage`)
- Manages multiple channel instances
- Handles notification retry and fallback logic
- Routes messages to appropriate channels

**NotificationChannel (abstract)**
- Defines interface that all channels must implement
- Standardizes message format conversion
- Provides availability checking

**FeishuChannel**
- Encapsulates Lark SDK calls
- Implements card, rich text, and image formats
- Handles Feishu-specific constraints (character limits, rate limits)
- Manages message queuing and batching

### Data Flow

```
Agent Tool → NotificationService.send() 
    → FeishuChannel.send() 
    → Lark SDK 
    → Feishu Server
```

---

## Interface Design

### NotificationService API

```typescript
interface NotificationMessage {
  title?: string;
  content: string;
  type: 'text' | 'markdown' | 'card';
  metadata?: Record<string, any>;
}

interface NotificationOptions {
  channel?: string;  // default 'feishu'
  chatId?: string;   // override default chatId
  priority?: 'low' | 'normal' | 'high';
}

class NotificationService {
  // Basic text message
  async send(message: string, options?: NotificationOptions): Promise<void>
  
  // Rich card (trade signals, market briefs, etc.)
  async sendCard(message: NotificationMessage, options?: NotificationOptions): Promise<void>
  
  // Image/chart
  async sendImage(imageUrl: string, caption?: string, options?: NotificationOptions): Promise<void>
  
  // Batch send (avoid rate limits)
  async sendBatch(messages: NotificationMessage[], options?: NotificationOptions): Promise<void>
}
```

### NotificationChannel Abstract Class

```typescript
abstract class NotificationChannel {
  abstract send(message: NotificationMessage): Promise<void>
  abstract sendImage(imageUrl: string, caption?: string): Promise<void>
  abstract isAvailable(): boolean  // check if configuration is complete
}
```

### Agent Tool Usage Examples

```typescript
// Trade signal
await notificationService.sendCard({
  title: '🟢 Buy Signal',
  content: '**Kweichow Moutai** (600519)\nPrice: ¥1850\n...',
  type: 'card',
  metadata: { signal_type: 'buy', symbol: '600519' }
})

// Simple text
await notificationService.send('Market monitoring started')
```

---

## FeishuChannel Implementation

### Feishu-Specific Features

**1. Card Message Format**
- Supports Markdown rendering
- Blue header (Pi Investment branding)
- Auto-handles 28000 character limit (split into multiple messages)

**2. Message Type Mapping**
```typescript
NotificationMessage.type → Feishu msg_type
  'text' → 'text'
  'markdown' → 'text' (plain text)
  'card' → 'interactive' (rich card)
```

**3. Error Handling**
- Feishu API failure → fallback to plain text
- Rate limit → auto-queue with delay
- Missing config → silent fail + warning log

### Configuration Management

```typescript
// Read from environment variables
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_DEFAULT_CHAT_ID  // default send target

// FeishuChannel initialization
const feishuChannel = new FeishuChannel({
  appId: process.env.FEISHU_APP_ID,
  appSecret: process.env.FEISHU_APP_SECRET,
  defaultChatId: process.env.FEISHU_DEFAULT_CHAT_ID
})
```

### Relationship with Existing Code

**Keep:**
- `src/api/feishu.ts` - WebSocket Bot (receive messages)
- `FeishuSessionManager` - session management

**Refactor:**
- `src/services/notification/feishu-service.ts` → rename to `FeishuChannel`
- `send_feishu_alert` tool → call `NotificationService`

**New:**
- `src/services/notification/notification-service.ts`
- `src/services/notification/notification-channel.ts`
- `src/services/notification/feishu-channel.ts`

---

## Agent Tool Integration

### Updated Existing Tools

**`send_feishu_alert` → `send_notification`**

```typescript
// New tool definition
{
  name: "send_notification",
  description: "Send notification message (trade signals, market alerts, etc.)",
  parameters: {
    type: 'text' | 'card',
    title?: string,
    content: string,
    metadata?: object
  }
}

// Implementation
execute: async (params) => {
  await notificationService.sendCard({
    title: params.title,
    content: params.content,
    type: params.type,
    metadata: params.metadata
  })
}
```

### New Convenience Tools

**1. `send_trade_signal`** - Specialized for trade signals
```typescript
parameters: {
  action: 'buy' | 'sell',
  symbol: string,
  price: number,
  reason: string,
  confidence: number
}
// Internally formats as standard card
```

**2. `send_market_brief`** - Market summary
```typescript
parameters: {
  summary: string,
  highlights: string[],
  risks?: string[]
}
```

**3. `send_risk_warning`** - Risk alerts
```typescript
parameters: {
  level: 'low' | 'medium' | 'high',
  message: string
}
```

### Tool Registration

```typescript
// src/tools/notification-tools.ts
export const notificationTools = [
  sendNotificationTool,
  sendTradeSignalTool,
  sendMarketBriefTool,
  sendRiskWarningTool
]

// src/infrastructure/tools/index.ts
import { notificationTools } from '../tools/notification-tools.js'
export const allCustomTools = [
  ...notificationTools,
  // ... other tools
]
```

---

## Error Handling

### Strategy

**1. Missing Configuration**
```typescript
// FeishuChannel.isAvailable() returns false
// NotificationService silently skips, logs warning
console.warn('[Notification] Feishu channel not configured, skipping')
```

**2. Send Failure**
```typescript
// Retry 3 times with exponential backoff (1s, 2s, 4s)
// Final failure → log error, don't block agent execution
console.error('[Notification] Failed to send after 3 retries:', error)
```

**3. Rate Limiting**
```typescript
// Feishu limit: 20 messages/minute
// Built-in queue, auto-delay sending
// Queue overflow → drop old messages, keep newest
```

---

## Testing Strategy

### Unit Tests

- `NotificationService` - mock channel, verify routing logic
- `FeishuChannel` - mock Lark SDK, verify message format conversion
- Tool functions - verify parameter validation and formatting

### Integration Tests

```typescript
// src/services/notification/feishu-channel.test.ts
// Use real Feishu test group
describe('FeishuChannel', () => {
  it('should send card message', async () => {
    const channel = new FeishuChannel({...testConfig})
    await channel.send({
      title: 'Test',
      content: 'Integration test',
      type: 'card'
    })
  })
})
```

### Manual Test Script

```typescript
// src/scripts/test-notification.ts
// Quick validation of Feishu config and message formats
```

---

## Implementation Files

### New Files

1. `src/services/notification/notification-channel.ts` - Abstract base class
2. `src/services/notification/notification-service.ts` - Unified service
3. `src/services/notification/feishu-channel.ts` - Feishu implementation
4. `src/tools/notification-tools.ts` - Agent tools
5. `src/scripts/test-notification.ts` - Manual test script

### Modified Files

1. `src/services/notification/feishu-service.ts` - Refactor into FeishuChannel
2. `src/tools/monitor-tools.ts` - Update to use NotificationService
3. `src/infrastructure/tools/index.ts` - Register notification tools

### Preserved Files

1. `src/api/feishu.ts` - WebSocket Bot (unchanged)
2. `src/api/feishu-session-manager.ts` - Session management (unchanged)

---

## Migration Path

### Phase 1: Core Infrastructure
1. Create `NotificationChannel` abstract class
2. Create `NotificationService` with basic send methods
3. Implement `FeishuChannel` with text and card support

### Phase 2: Tool Integration
1. Create new notification tools
2. Update existing `send_feishu_alert` to use NotificationService
3. Register tools in tool registry

### Phase 3: Testing & Validation
1. Write unit tests for all components
2. Create integration tests with real Feishu
3. Build manual test script
4. Validate with real agent workflows

### Phase 4: Cleanup
1. Remove old `FeishuService` if fully replaced
2. Update documentation
3. Add usage examples to README

---

## Future Extensions

### Additional Channels
- DingTalk channel
- WeChat Work channel
- Email channel
- SMS channel

### Enhanced Features
- Message templates
- Scheduled notifications
- Notification history/audit log
- User preference management (per-user notification settings)

### Advanced Capabilities
- Interactive cards with buttons
- File attachments
- Voice messages
- Video notifications

---

## Success Criteria

1. ✅ Agent can send text, card, and image notifications via unified API
2. ✅ Feishu integration works without blocking agent execution on failures
3. ✅ System handles rate limits gracefully
4. ✅ Code is decoupled from specific notification provider
5. ✅ All existing notification use cases continue to work
6. ✅ Test coverage ≥ 80% for new code
7. ✅ Manual test script validates end-to-end flow

---

## Non-Goals

- Real-time bidirectional communication (already handled by WebSocket Bot)
- Message threading/conversation management
- User authentication/authorization
- Analytics/metrics collection (can be added later)
