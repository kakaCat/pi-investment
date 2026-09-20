/**
 * CreateTool 提示词（REQ-47939a t8）——从 host/agent-tools.ts 的 defineCreateTool description 原样搬入。
 * @module dsh-pmboard/tools/CreateTool/prompt
 */
export const CREATE_PROMPT = `创建即立项：识别到值得立项的新工作（feature/bug/doc/refactor/spike/chore）时直接创建需求。
首选 reqboard_capture（pm 专有立项弹框）：一次调用弹出「立项三问」并在同一次调用内完成
创建与窗口绑定——问题一【需求名称】（可经 title_options 传候选，最贴切一项置首推荐，允许自定义输入）；
问题二【需求类型】（feature/bug/doc/refactor/spike/chore）；
问题三【提示词难度】（simple=简单/standard=标准(Recommended)/advanced=进阶/expert=专家，
标准适合大多数场景，简单适合快速任务，进阶和专家适合复杂需求）。用户作答即立项确认，**不需要**再补调本工具。
本工具是**已明确取值**时的手工路径（弹框通道不可用，或用户在对话里已直接给出三值）：按用户确认值调用——
title=需求名称、category=需求类型、prompt_difficulty=难度级别、summary=工作摘要、reason=立项依据。
创建后 REQ 立即在看板 draft 泳道可见、本窗口绑定该需求。
调用前先 reqboard_status 自查：本窗口已绑定进行中需求或已有 pending 建议时不要重复立项。
仅闲聊、追问进度、或用户在自主回合（非直接消息）时不提议不立项。`
