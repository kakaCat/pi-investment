/**
 * 需求实体基础类型（REQ-47939a t2）。
 *
 * t2 只搬 domain 需要的**类型**（分类决定归档必填文档与流程画像，ArtifactSpec 依赖它）。
 * 实体的完整不变量守卫按 design/domain-model.md §1 在后续用例层落地时补齐；
 * 本文件当前只承载类型，避免 t2 提前改动行为。
 *
 * 纯类型文件，零 import。
 */

export type RequirementCategory = 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore'
