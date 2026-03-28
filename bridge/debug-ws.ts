// 直接测试 codex app-server WebSocket 协议
import WebSocket from "ws";

const ws = new WebSocket("ws://127.0.0.1:3100");
let counter = 0;

ws.on("open", () => {
  console.log("✅ Connected");

  // Step 1: initialize
  const initMsg = { id: ++counter, method: "initialize", params: { clientInfo: { name: "test", version: "1.0" } } };
  console.log("\n→ Sending:", JSON.stringify(initMsg));
  ws.send(JSON.stringify(initMsg));
});

let threadId = "";

ws.on("message", (raw) => {
  const msg = JSON.parse(raw.toString());
  console.log("\n← Received:", JSON.stringify(msg, null, 2));

  // After initialize → thread/start
  if (msg.id === 1 && msg.result) {
    const threadMsg = {
      id: ++counter,
      method: "thread/start",
      params: {
        initialPrompt: "Say hello in one sentence.",
        workdir: "/Users/mac/Documents/ai/pi-investment",
        approvalPolicy: "never",
      },
    };
    console.log("\n→ Sending thread/start");
    ws.send(JSON.stringify(threadMsg));
  }

  // After thread/start response → turn/start to actually run the agent
  if (msg.id === 2 && msg.result?.thread?.id) {
    threadId = msg.result.thread.id;
    const turnMsg = {
      id: ++counter,
      method: "turn/start",
      params: {
        threadId,
        input: [{ type: "text", text: "Say hello in one sentence." }],
      },
    };
    console.log("\n→ Sending turn/start with threadId:", threadId);
    ws.send(JSON.stringify(turnMsg));
  }

  // thread completed
  if (msg.method === "thread/status/changed" && msg.params?.thread?.status?.type === "completed") {
    console.log("\n✅ Thread completed!");
    setTimeout(() => { ws.close(); process.exit(0); }, 1000);
  }
});

ws.on("error", (e) => console.error("❌ WS error:", e.message));
ws.on("close", () => console.log("\n🔌 Closed"));

setTimeout(() => { console.log("\n⏰ Timeout"); process.exit(1); }, 20000);
