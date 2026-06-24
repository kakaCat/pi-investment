import { beforeAll, beforeEach, describe, expect, jest, test } from "@jest/globals";

const messageCreateMock = jest.fn();
const wsStartMock = jest.fn();
const cronStartMock = jest.fn();
const cronStopMock = jest.fn();
let cronHandler: ((payload: { kind: string; chatId?: string; message?: string }) => Promise<void>) | null = null;

let registeredHandlers: Record<string, (data: any) => Promise<void>> = {};
let sessionManagerInstance: {
  isDuplicate: jest.MockedFunction<() => boolean>;
  isProcessing: jest.MockedFunction<() => boolean>;
  processMessage: jest.MockedFunction<() => Promise<string>>;
  abort: jest.MockedFunction<() => Promise<boolean>>;
  shutdown: jest.Mock;
};

jest.unstable_mockModule("@larksuiteoapi/node-sdk", () => ({
  Client: class MockClient {
    public im = {
      message: {
        create: messageCreateMock,
      },
    };
  },
  EventDispatcher: class MockEventDispatcher {
    register(handlers: Record<string, (data: any) => Promise<void>>) {
      registeredHandlers = handlers;
      return this;
    }
  },
  WSClient: class MockWSClient {
    start(options: { eventDispatcher: unknown }) {
      wsStartMock(options);
    }
  },
  LoggerLevel: {
    info: "info",
  },
}));

jest.unstable_mockModule("@mariozechner/pi-coding-agent", () => ({
  SessionManager: {
    continueRecent: jest.fn(),
  },
  estimateTokens: jest.fn(() => 0),
  loadSkills: jest.fn(() => ({ skills: [] })),
}));

jest.unstable_mockModule("../infrastructure/logging/observable-logger.js", () => ({
  initSession: jest.fn(),
  logSessionEnd: jest.fn(),
}));

jest.unstable_mockModule("../infrastructure/session/session-factory.js", () => ({
  createTrackedSession: jest.fn(),
}));

jest.unstable_mockModule("../infrastructure/tools/index.js", () => ({
  allCustomTools: [],
  initMemoryTools: jest.fn(),
}));

jest.unstable_mockModule("../infrastructure/tools/plan-tool.js", () => ({
  setPlanToolContext: jest.fn(),
}));

jest.unstable_mockModule("../infrastructure/plugins/index.js", () => ({
  loadPlugins: jest.fn(async () => ({ tools: [], skills: [] })),
}));

jest.unstable_mockModule("../config/config.js", () => ({
  createDeepSeekModel: jest.fn(),
  paths: {
    root: "/tmp/pi-investment",
    piDir: "/tmp/pi-investment/.pi-invest",
    skillsDir: "/tmp/pi-investment/skills",
  },
}));

jest.unstable_mockModule("../core/agent/system-prompt.js", () => ({
  autoRecall: jest.fn(() => ""),
  buildAgentSystemPrompt: jest.fn(() => "system prompt"),
  initSkillsBlock: jest.fn(),
  readDailyMemory: jest.fn(() => ""),
}));

jest.unstable_mockModule("../services/compaction/compaction-service.js", () => ({
  microCompact: jest.fn(),
}));

jest.unstable_mockModule("../infrastructure/tools/skill-guard.js", () => ({
  initSkillGuard: jest.fn(),
}));

jest.unstable_mockModule("../services/intelligence/skill-router.js", () => ({
  initSkillRouter: jest.fn(),
}));

jest.unstable_mockModule("./feishu-session-manager.js", () => ({
  FeishuSessionManager: class MockFeishuSessionManager {
    constructor() {
      sessionManagerInstance = {
        isDuplicate: jest.fn(() => false),
        isProcessing: jest.fn(() => false),
        processMessage: jest.fn(async () => "默认回复"),
        abort: jest.fn(async () => false),
        shutdown: jest.fn(),
      };
      return sessionManagerInstance;
    }
  },
}));

jest.unstable_mockModule("../services/operations/cron-service.js", () => ({
  CronService: class MockCronService {
    constructor(
      _cronFile: string,
      _piDir: string,
      onJob: (payload: { kind: string; chatId?: string; message?: string }) => Promise<void>
    ) {
      cronHandler = onJob;
    }

    start() {
      cronStartMock();
    }

    stop() {
      cronStopMock();
    }
  },
}));

function flushPromises(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

process.env.FEISHU_APP_ID = "app-id";
process.env.FEISHU_APP_SECRET = "app-secret";

beforeAll(async () => {
  await import("./feishu.js");
  await flushPromises();
});

beforeEach(() => {
  jest.clearAllMocks();
  sessionManagerInstance.isDuplicate.mockReturnValue(false);
  sessionManagerInstance.isProcessing.mockReturnValue(false);
  sessionManagerInstance.processMessage.mockResolvedValue("默认回复");
  sessionManagerInstance.abort.mockResolvedValue(false);
});

describe("feishu api", () => {
  test("sends the final agent reply as an interactive card", async () => {
    sessionManagerInstance.processMessage.mockResolvedValueOnce("分析完成");

    await registeredHandlers["im.message.receive_v1"]({
      message: {
        message_type: "text",
        message_id: "msg-1",
        chat_id: "chat-1",
        content: JSON.stringify({ text: "你好" }),
      },
    });

    expect(sessionManagerInstance.processMessage).toHaveBeenCalledWith("chat-1", "msg-1", "你好");
    expect(messageCreateMock).toHaveBeenCalledTimes(2); // 1st: confirmation, 2nd: final reply
    expect(messageCreateMock).toHaveBeenNthCalledWith(2, expect.objectContaining({
      params: { receive_id_type: "chat_id" },
      data: {
        receive_id: "chat-1",
        msg_type: "interactive",
        content: expect.any(String),
      },
    }));

    const secondCall = messageCreateMock.mock.calls[1]?.[0] as {
      data: { content: string };
    };
    expect(JSON.parse((secondCall as any).data.content)).toEqual({
      config: {
        wide_screen_mode: true,
      },
      elements: [
        {
          tag: "markdown",
          content: "分析完成",
        },
      ],
      header: {
        template: "blue",
        title: {
          tag: "plain_text",
          content: "Pi Investment",
        },
      },
    });
  });

  test("sends stop replies as plain text", async () => {
    sessionManagerInstance.abort.mockResolvedValueOnce(true);

    await registeredHandlers["im.message.receive_v1"]({
      message: {
        message_type: "text",
        message_id: "msg-stop",
        chat_id: "chat-2",
        content: JSON.stringify({ text: "stop" }),
      },
    });

    expect(sessionManagerInstance.abort).toHaveBeenCalledWith("chat-2");
    expect(messageCreateMock).toHaveBeenCalledTimes(1);
    expect(messageCreateMock).toHaveBeenCalledWith({
      params: { receive_id_type: "chat_id" },
      data: {
        receive_id: "chat-2",
        msg_type: "text",
        content: JSON.stringify({ text: "已取消当前任务" }),
      },
    });
  });

  test("sends queue notices as plain text before the final interactive card reply", async () => {
    sessionManagerInstance.isProcessing.mockReturnValueOnce(true);
    sessionManagerInstance.processMessage.mockResolvedValueOnce("排队后的结果");

    await registeredHandlers["im.message.receive_v1"]({
      message: {
        message_type: "text",
        message_id: "msg-queue",
        chat_id: "chat-3",
        content: JSON.stringify({ text: "继续分析" }),
      },
    });

    expect(messageCreateMock).toHaveBeenCalledTimes(2);
    expect(messageCreateMock).toHaveBeenNthCalledWith(1, {
      params: { receive_id_type: "chat_id" },
      data: {
        receive_id: "chat-3",
        msg_type: "text",
        content: JSON.stringify({ text: "任务处理中，消息已排队" }),
      },
    });

    expect(messageCreateMock).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        data: expect.objectContaining({
          receive_id: "chat-3",
          msg_type: "interactive",
          content: expect.any(String),
        }),
      })
    );
  });

  test("sends cron replies as interactive cards", async () => {
    sessionManagerInstance.processMessage.mockResolvedValueOnce("定时复盘完成");

    expect(cronHandler).not.toBeNull();
    await cronHandler!({
      kind: "agent_turn",
      chatId: "chat-cron",
      message: "cron-task",
    });

    expect(sessionManagerInstance.processMessage).toHaveBeenCalledWith(
      "chat-cron",
      expect.stringMatching(/^cron-\d+$/),
      "cron-task"
    );
    expect(messageCreateMock).toHaveBeenCalledTimes(1);
    expect(messageCreateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          receive_id: "chat-cron",
          msg_type: "interactive",
          content: expect.any(String),
        }),
      })
    );
  });

  test("sends processing errors as plain text", async () => {
    sessionManagerInstance.processMessage.mockRejectedValueOnce(new Error("boom"));

    await registeredHandlers["im.message.receive_v1"]({
      message: {
        message_type: "text",
        message_id: "msg-error",
        chat_id: "chat-4",
        content: JSON.stringify({ text: "触发异常" }),
      },
    });

    expect(messageCreateMock).toHaveBeenCalledTimes(2); // 1st: confirmation, 2nd: error message
    expect(messageCreateMock).toHaveBeenNthCalledWith(2, {
      params: { receive_id_type: "chat_id" },
      data: {
        receive_id: "chat-4",
        msg_type: "text",
        content: JSON.stringify({ text: "抱歉，处理消息时出现错误，请稍后重试。" }),
      },
    });
  });
});
