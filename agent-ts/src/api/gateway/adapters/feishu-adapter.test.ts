import { normalizeFeishuMessage } from "./feishu-normalize.js";

describe("normalizeFeishuMessage", () => {
  it("文本消息 → InboundEvent", () => {
    const event = normalizeFeishuMessage({
      message_id: "om_123",
      chat_id: "oc_abc",
      message_type: "text",
      content: JSON.stringify({ text: "分析一下茅台" }),
    });
    expect(event).toEqual({
      channel: "feishu",
      peerId: "oc_abc",
      messageId: "om_123",
      text: "分析一下茅台",
    });
  });

  it("非文本消息返回 null", () => {
    expect(normalizeFeishuMessage({
      message_id: "om_1", chat_id: "oc_1", message_type: "image", content: "{}",
    })).toBeNull();
  });

  it("空文本或缺 chat_id 返回 null", () => {
    expect(normalizeFeishuMessage({
      message_id: "om_1", chat_id: "oc_1", message_type: "text", content: JSON.stringify({ text: "  " }),
    })).toBeNull();
    expect(normalizeFeishuMessage({
      message_id: "om_1", chat_id: "", message_type: "text", content: JSON.stringify({ text: "hi" }),
    })).toBeNull();
  });
});
