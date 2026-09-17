/**
 * CreateTool 提示词（REQ-47939a t8）——从 host/agent-tools.ts 的 defineCreateTool description 原样搬入。
 * @module dsh-pmboard/tools/CreateTool/prompt
 */
export const CREATE_PROMPT = '创建即立项：识别到值得立项的新工作（feature/bug/doc/refactor/spike/chore）时直接创建需求。'
      + '调用前必须先 ask_user_question 弹「两问确认」向用户确认：问题一需求名称（按对话/消息'
      + '上下文给出候选选项，最贴切一项置首标注 (Recommended)，允许用户自定义输入）；问题二需求'
      + '类型（选项 feature/bug/doc/refactor/spike/chore，(Recommended) 置首、可改选）。'
      + '用户作答 = 立项确认（无需任何待归类/建议卡中间态）——随后按用户确认值调用本工具：'
      + 'title=用户确认的需求名称、category=用户选择的需求类型、summary=工作摘要、reason=立项依据。'
      + '创建后 REQ 立即在看板 draft 泳道可见、本窗口绑定该需求。'
      + '调用前先 reqboard_status 自查：本窗口已绑定进行中需求或已有 pending 建议时不要重复立项。'
      + '仅闲聊、追问进度、或用户在自主回合（非直接消息）时不提议不立项。'
