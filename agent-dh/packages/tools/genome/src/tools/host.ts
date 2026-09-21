/**
 * 写工具宿主接口：由 GenomePlugin 实现，向写工具提供
 * ①热替换 systemPrompt 段注册 ②渲染金丝雀（真实试渲染，失败抛错）
 * 使 genome_update / genome_rollback 与原始实现语义一致（更新即时生效 + 失败自动还原）。
 */
export interface GenomeWriteHost {
  /** 热替换段注册：dispose 旧段，以新内容/新版本号注册新段 */
  hotSwapSection(
    section: string,
    genomeVersion: string,
    sectionVersion: number,
    order: number,
    content: string
  ): void;
  /** 渲染金丝雀：assemble + renderPrompt 真实试渲染，失败抛错 */
  canaryRender(): Promise<void>;
}
