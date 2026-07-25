import { buildSessionKey, parseSessionKey } from "./session-key.js";

describe("buildSessionKey", () => {
  it("构造 canonical key", () => {
    expect(buildSessionKey("feishu", "oc_abc123")).toBe("agent:main:feishu:oc_abc123");
    expect(buildSessionKey("wake", "default")).toBe("agent:main:wake:default");
  });

  it("peerId 中的非法字符替换为下划线", () => {
    expect(buildSessionKey("feishu", "oc_xx/yy zz")).toBe("agent:main:feishu:oc_xx_yy_zz");
  });

  it("parseSessionKey 还原各部分", () => {
    expect(parseSessionKey("agent:main:feishu:oc_abc")).toEqual({
      agentId: "main",
      channel: "feishu",
      peerId: "oc_abc",
    });
  });
});
