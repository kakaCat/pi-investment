/**
 * CaptureTool 提示词（REQ-e3b6a0 t8 / FR-7）——立项四问 pm 专有弹框的触发纪律。
 *
 * 口径事实源：四问（需求名称 / 需求类型 / 提示词难度 / 文档位置）以本工具的 schema 与三处注入文案
 * （capture-section.ts / QueryState.ts / CreateTool/prompt.ts）为同一份口径，改一处必改全部。
 *
 * @module dsh-pmboard/tools/CaptureTool/prompt
 */
export const CAPTURE_PROMPT = `立项弹框（pm 专有）：识别到值得立项的新工作（feature/bug/doc/refactor/spike/chore）时，
用本工具一次完成「立项四问 + 创建 + 绑定窗口」——用户作答即立项，不需要再调别的工具补建。
弹框四问（选项顺序即推荐顺序）：
问题一【需求名称】可直接选候选、自定义输入，或选择"✖️ 不需要立项"取消立项（候选经 title_options 传入，最贴切一项放首位）；
问题二【需求类型】feature/bug/doc/refactor/spike/chore；
问题三【提示词难度】simple=简单/standard=标准(Recommended)/advanced=进阶/expert=专家（标准适合大多数场景）；
问题四【需求文档位置】选择预设路径（docs/requirements/<REQ>/推荐 / docs/rfcs/ / docs/architecture/ / docs/guides/）或自定义输入。
何时用：用户在本窗口提出新工作意图且值得立项时（尤其在收到「项目捕获」引导段后）立即调用。
不要这样做：不要先调宿主通用弹框再另调 reqboard_create（两段式会在答案与创建之间断链）；
本工具自带弹框，作答后同一次调用内即完成立项与绑定。
弹框通道不可用时本工具返回 fallback=board 且不伪造立项；此时改为文字向用户取值，再调 reqboard_create。
调用前先 reqboard_status 自查：本窗口已绑定进行中需求或已有 pending 建议时不要重复立项。
仅闲聊、追问进度、或用户在自主回合（非直接消息）时不弹框不立项。`