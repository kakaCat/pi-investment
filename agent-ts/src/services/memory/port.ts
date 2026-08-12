/**
 * MemoryProvider Port - 记忆提供者接口（参照 Hermes memory_provider.py）
 *
 * 设计要点：
 * - prefetch: 会话开始时根据上下文召回 top-K 记忆（双缓冲模式）
 * - query: 主动查询记忆（对应 memory_search 工具）
 * - sync_turn: 异步写入完成的轮次（对应 memory_write 工具）
 * - validate: 更新记忆的召回时间戳和验证计数
 * - system_prompt_block: 返回静态提示词块（provider 状态说明）
 *
 * W1.4 实现两个 adapter：
 * - v2-client: 通过 quantsys-v2 的 /api/memory/* 接口
 * - file-fallback: 包装现有 memory-store.ts（降级）
 */

export interface MemorySearchResult {
  id?: number;
  title: string;
  content: string;
  score: number;
  kind?: string;
  scope?: string;
  source?: string; // 'bm25' | 'vector' | 'both'
}

export interface MemorySearchResponse {
  items: MemorySearchResult[];
  total: number;
  degraded?: boolean; // true = ollama 不可达，已降级纯 BM25
  strategy?: string; // 'hybrid' | 'bm25' | 'vector' | 'filter'
}

export interface MemoryWriteParams {
  kind?: string; // 'rule' | 'episode' | 'experience' | 'stock_note'
  scope?: string; // 'global' | 'stock:X' | 'strategy:Y'
  title?: string;
  content: string;
  payload?: Record<string, any>;
  evidence?: Record<string, any>;
  status?: string; // 'testing' | 'active' | 'deprecated' | 'archived'
  confidence?: number;
  provenance?: {
    session_kind?: string; // 'user' | 'cron' | 'wake' | 'distiller'
    channel?: string; // 'terminal' | 'api' | 'feishu'
    session_id?: string;
  };
  source?: string; // 'agent' | 'distiller' | 'manual' | 'recall'
}

export interface ExperienceWriteParams {
  scenario: string;
  conditions: string[];
  action: 'buy' | 'sell' | 'hold';
  total_cases: number;
  win_rate: number;
  avg_return: number;
  max_gain?: number;
  max_loss?: number;
  recommendation: 'aggressive' | 'moderate' | 'cautious' | 'avoid';
  reason: string;
  confidence: number;
  examples?: Array<{
    date: string;
    symbol: string;
    session_id: string;
    result: number;
  }>;
  symbol?: string;
}

/**
 * MemoryProvider Port
 *
 * 参照 Hermes agent/memory_provider.py 设计
 */
export interface MemoryProvider {
  /** Provider 名称 */
  readonly name: string;

  /** 检查 provider 是否可用（配置检查，不做网络调用）*/
  isAvailable(): boolean;

  /** 初始化 provider（会话开始时调用一次）*/
  initialize(sessionId: string, context: {
    sessionKind?: string; // 'user' | 'cron' | 'wake' | 'distiller'
    channel?: string; // 'terminal' | 'api' | 'feishu'
    workspace?: string;
  }): Promise<void>;

  /** 返回静态提示词块（描述 provider 状态，不含召回内容）*/
  systemPromptBlock(): string;

  /**
   * Prefetch - 根据上下文召回相关记忆（会话开始/每轮前台调用）
   *
   * 返回格式化文本，注入到系统提示词的 Memory 层
   * 字符预算：默认 2000（maxTotalRecallChars，参照腾讯设计）
   *
   * @param query 当前上下文查询（用户最近消息 + 任务上下文）
   * @param sessionId 会话 ID（多会话 provider 需要，单会话可忽略）
   * @param limit 召回数量上限（默认 3）
   * @param maxChars 字符预算上限（默认 2000）
   */
  prefetch(
    query: string,
    sessionId?: string,
    limit?: number,
    maxChars?: number
  ): Promise<string>;

  /**
   * Query - 主动查询记忆（对应 memory_search 工具）
   *
   * @param query 查询文本
   * @param options 过滤选项（scope/kind/status）
   * @param limit 返回数量上限
   */
  query(
    query: string,
    options?: {
      scope?: string;
      kind?: string;
      status?: string;
      limit?: number;
    }
  ): Promise<MemorySearchResponse>;

  /**
   * Sync Turn - 轮次钩子（回合后调用）
   *
   * 设计决策（2026-08-12 修补）：本系统**不做**轮次级自动写入——
   * 自动抽取写入会绕过证据链与质量门禁（Hermes 的 sync_turn 配后台 review，我们没有）。
   * 所有持久化写入走 write() / writeExperience()（由 memory_write / experience_write 工具触发）。
   * 本方法仅用于：记录本轮 recalledIds，供后续防 recall 循环过滤使用。
   *
   * @param userContent 用户消息
   * @param assistantContent 助手回复
   * @param sessionId 会话 ID
   * @param metadata 元数据（provenance 等）
   */
  syncTurn(
    userContent: string,
    assistantContent: string,
    sessionId?: string,
    metadata?: {
      sessionKind?: string;
      channel?: string;
      recalledIds?: number[]; // 本轮被召回注入的记忆 ID，写入时排除
    }
  ): Promise<void>;

  /**
   * Write - 写入记忆条目（memory_write 工具的真实写入路径）
   *
   * 防 recall 循环：实现方必须拒绝/标记从召回内容直接复制的写入
   * （source !== 'recall' 且内容不与本轮召回条目重复）。
   */
  write(params: MemoryWriteParams): Promise<{ id?: number; path?: string }>;

  /**
   * Validate - 更新记忆的召回时间戳和验证计数
   *
   * @param entryId 记忆条目 ID
   * @param success 本次验证是否成功
   */
  validate(entryId: number, success: boolean): Promise<void>;

  /**
   * Search (legacy) - 兼容旧 memory_search 工具调用
   * 内部转发到 query
   */
  search(
    query: string,
    topK?: number
  ): Promise<MemorySearchResult[]>;

  /**
   * Write Experience - 写入经验（对应 experience_write 工具）
   */
  writeExperience(params: ExperienceWriteParams): Promise<{ success: boolean; id?: number; message: string }>;

  /**
   * Query Experience - 查询经验（对应 query_experience 工具）
   */
  queryExperience(params: {
    scenario?: string;
    symbol?: string;
    conditions?: string[];
    limit?: number;
    include_deprecated?: boolean;
  }): Promise<string>;

  /** 关闭清理 */
  shutdown(): Promise<void>;
}
