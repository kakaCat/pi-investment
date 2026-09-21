/**
 * MoveTool 提示词（REQ-47939a t8）——从 host/agent-tools.ts 的 defineMoveTool description 原样搬入。
 * @module dsh-pmboard/tools/MoveTool/prompt
 */
export const MOVE_PROMPT = '推进本窗口已绑定需求的状态（项目看板泳道）——状态由执行窗口自己维护，不要等用户手动点。'
      + '仅能推进本窗口绑定的需求；在途状态（需求分析→拆分→实施→验收）都可自行推进，'
      + '只有「取消需求」「归档」是人工闸门（调用会被代码级拒绝并提示）。'
      + '用法：里程碑处调用（方案定 → decomposing，开工 → implementing，交付 → accepting），'
      + 'reason 写清做了什么（进需求留痕供验收与复盘）；先 reqboard_status 可查当前状态与可选动作。'
