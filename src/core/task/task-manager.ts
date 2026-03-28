import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync } from "fs";
import { join } from "path";

export interface Task {
  id: number;
  subject: string;
  description: string;
  status: "pending" | "in_progress" | "completed";
  blockedBy: number[];
  blocks: number[];
  owner: string;
}

export class TaskManager {
  private dir: string;
  private nextId: number;

  constructor(tasksDir: string) {
    this.dir = tasksDir;
    if (!existsSync(this.dir)) {
      mkdirSync(this.dir, { recursive: true });
    }
    this.nextId = this.maxId() + 1;
  }

  private maxId(): number {
    if (!existsSync(this.dir)) return 0;
    const files = readdirSync(this.dir).filter(f => f.startsWith("task_") && f.endsWith(".json"));
    if (files.length === 0) return 0;
    const ids = files
      .map(f => parseInt(f.replace("task_", "").replace(".json", ""), 10))
      .filter(id => !isNaN(id));
    return ids.length > 0 ? Math.max(...ids) : 0;
  }

  private load(taskId: number): Task {
    const path = join(this.dir, `task_${taskId}.json`);
    if (!existsSync(path)) {
      throw new Error(`Task ${taskId} not found`);
    }
    return JSON.parse(readFileSync(path, "utf-8"));
  }

  private save(task: Task): void {
    const path = join(this.dir, `task_${task.id}.json`);
    writeFileSync(path, JSON.stringify(task, null, 2));
  }

  create(subject: string, description: string = ""): string {
    if (!subject || subject.trim().length === 0) {
      throw new Error("Task subject cannot be empty");
    }
    const task: Task = {
      id: this.nextId,
      subject: subject.trim(),
      description: description.trim(),
      status: "pending",
      blockedBy: [],
      blocks: [],
      owner: "",
    };
    this.save(task);
    this.nextId++;
    return JSON.stringify(task, null, 2);
  }

  createBatch(items: Array<{ subject: string; description?: string }>): string {
    if (!items || items.length === 0) {
      throw new Error("tasks array cannot be empty");
    }
    const created: Task[] = [];
    for (const item of items) {
      if (!item.subject || item.subject.trim().length === 0) {
        throw new Error("Each task must have a non-empty subject");
      }
      const task: Task = {
        id: this.nextId,
        subject: item.subject.trim(),
        description: (item.description || "").trim(),
        status: "pending",
        blockedBy: [],
        blocks: [],
        owner: "",
      };
      this.save(task);
      this.nextId++;
      created.push(task);
    }
    return created.map(t => `#${t.id}: ${t.subject}`).join("\n");
  }

  get(taskId: number): string {
    return JSON.stringify(this.load(taskId), null, 2);
  }

  update(
    taskId: number,
    status?: "pending" | "in_progress" | "completed",
    addBlockedBy?: number[],
    addBlocks?: number[]
  ): string {
    const task = this.load(taskId);

    if (status) {
      task.status = status;
      if (status === "completed") {
        this.clearDependency(taskId);
      }
    }

    if (addBlockedBy && addBlockedBy.length > 0) {
      task.blockedBy = Array.from(new Set([...task.blockedBy, ...addBlockedBy]));
    }

    if (addBlocks && addBlocks.length > 0) {
      task.blocks = Array.from(new Set([...task.blocks, ...addBlocks]));
      for (const blockedId of addBlocks) {
        try {
          const blocked = this.load(blockedId);
          if (!blocked.blockedBy.includes(taskId)) {
            blocked.blockedBy.push(taskId);
            this.save(blocked);
          }
        } catch (error) {
          console.warn(`Warning: Failed to update blocked task ${blockedId}:`, error);
        }
      }
    }

    this.save(task);
    return JSON.stringify(task, null, 2);
  }

  updateBatch(updates: Array<{ task_id: number; status: "pending" | "in_progress" | "completed" }>): string {
    if (!updates || updates.length === 0) {
      throw new Error("updates array cannot be empty");
    }
    const results: string[] = [];
    for (const u of updates) {
      const task = this.load(u.task_id);
      task.status = u.status;
      if (u.status === "completed") {
        this.clearDependency(u.task_id);
      }
      this.save(task);
      results.push(`#${task.id} → ${u.status}`);
    }
    return results.join("\n");
  }

  private clearDependency(completedId: number): void {
    if (!existsSync(this.dir)) return;
    const files = readdirSync(this.dir).filter(f => f.startsWith("task_") && f.endsWith(".json"));
    for (const file of files) {
      const task = JSON.parse(readFileSync(join(this.dir, file), "utf-8"));
      if (task.blockedBy.includes(completedId)) {
        task.blockedBy = task.blockedBy.filter((id: number) => id !== completedId);
        this.save(task);
      }
    }
  }

  listAll(): string {
    if (!existsSync(this.dir)) return "No tasks.";
    const files = readdirSync(this.dir)
      .filter(f => f.startsWith("task_") && f.endsWith(".json"))
      .sort((a, b) => {
        const idA = parseInt(a.replace("task_", "").replace(".json", ""), 10);
        const idB = parseInt(b.replace("task_", "").replace(".json", ""), 10);
        return idA - idB;
      });

    if (files.length === 0) return "No tasks.";

    const tasks = files.map(f => JSON.parse(readFileSync(join(this.dir, f), "utf-8")) as Task);
    const lines = tasks.map(t => {
      const statusMarkers: Record<Task["status"], string> = {
        pending: "[ ]",
        in_progress: "[>]",
        completed: "[x]"
      };
      const marker = statusMarkers[t.status] || "[?]";
      const blocked = t.blockedBy.length > 0 ? ` (blocked by: ${t.blockedBy.join(", ")})` : "";
      return `${marker} #${t.id}: ${t.subject}${blocked}`;
    });

    return lines.join("\n");
  }
}
