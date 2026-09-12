/**
 * MemoryKnowledgeAdapter - IKnowledgeService 实现
 * 
 * 使用现有的 memory_write 工具保存经验教训
 */

import type { IKnowledgeService, Lesson } from '../services/DecisionTrackingApplicationService';

/**
 * Memory Writer 接口（假设存在）
 */
export interface IMemoryWriter {
  write(params: {
    content: string;
    importance: number;
    namespace: string;
    tags: string[];
  }): Promise<{ success: boolean; memory_id?: string }>;
}

export class MemoryKnowledgeAdapter implements IKnowledgeService {
  constructor(private readonly memoryWriter: IMemoryWriter) {}
  
  async saveLesson(lesson: Lesson): Promise<void> {
    try {
      const result = await this.memoryWriter.write({
        content: lesson.content,
        importance: lesson.importance,
        namespace: lesson.namespace,
        tags: lesson.tags,
      });
      
      if (!result.success) {
        throw new Error('保存经验失败');
      }
      
      console.log(`📚 经验已保存: ${lesson.content.substring(0, 50)}...`);
    } catch (error: any) {
      console.error('保存经验失败:', error);
      throw error;
    }
  }
}
