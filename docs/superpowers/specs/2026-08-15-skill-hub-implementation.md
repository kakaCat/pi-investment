# Skill Hub 实现方案

> **创建时间**: 2026-08-15  
> **状态**: Implementation Ready  
> **目标**: Agent OS Skill Hub + agent-os-client SDK + agent-ts 集成

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent OS (Go)                             │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Skill Hub Service                                 │    │
│  │                                                    │    │
│  │  GET  /api/v1/skills                              │    │
│  │    → 返回: [{ id, name, description, ... }]       │    │
│  │                                                    │    │
│  │  GET  /api/v1/skills/{id}                         │    │
│  │    → 返回: { id, name, content, version, ... }    │    │
│  │                                                    │    │
│  │  POST /api/v1/skills                              │    │
│  │  PUT  /api/v1/skills/{id}                         │    │
│  │  DELETE /api/v1/skills/{id}                       │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Database: skills, skill_versions 表                        │
└─────────────────────────────────────────────────────────────┘
                         ↑ HTTP
                         
┌─────────────────────────────────────────────────────────────┐
│               agent-os-client (TypeScript SDK)               │
│                                                              │
│  class SkillsClient {                                        │
│    async list(): Promise<SkillMetadata[]>                   │
│    async get(id: string): Promise<SkillDetail>              │
│    async create(data): Promise<Skill>                       │
│    async update(id, data): Promise<Skill>                   │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                         ↑ Import
                         
┌─────────────────────────────────────────────────────────────┐
│                     agent-ts                                 │
│                                                              │
│  启动时:                                                     │
│    skillRegistry = await client.skills.list()               │
│    → 缓存 [{ id, name, description }] 到内存                │
│                                                              │
│  运行时:                                                     │
│    skill = await client.skills.get(skillId)                 │
│    → 获取 skill.content                                     │
│    → 执行 skill                                             │
│                                                              │
│  工具:                                                       │
│    skill_list   - 列出所有 skills                           │
│    skill_get    - 获取 skill 内容                           │
│    skill_update - 更新 skill (进化系统用)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Agent OS 实现

### 2.1 数据库表结构

```sql
-- skills 表
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(100),
    owner VARCHAR(100) NOT NULL,
    current_version_id UUID,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_skills_name ON skills(name);
CREATE INDEX idx_skills_owner ON skills(owner);
CREATE INDEX idx_skills_status ON skills(status);

-- skill_versions 表
CREATE TABLE skill_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    author VARCHAR(100),
    commit_message TEXT,
    parent_version_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,
    UNIQUE(skill_id, version)
);

CREATE INDEX idx_skill_versions_skill_id ON skill_versions(skill_id);
CREATE INDEX idx_skill_versions_created_at ON skill_versions(created_at DESC);

-- 添加外键约束
ALTER TABLE skills 
    ADD CONSTRAINT fk_skills_current_version 
    FOREIGN KEY (current_version_id) 
    REFERENCES skill_versions(id);
```

### 2.2 Go Service 实现

**文件**: `agent-os/internal/services/skill_service.go`

```go
package services

import (
    "context"
    "crypto/sha256"
    "encoding/hex"
    "fmt"
    "time"

    "github.com/google/uuid"
    "github.com/jackc/pgx/v5/pgxpool"
)

type Skill struct {
    ID               string                 `json:"id"`
    Name             string                 `json:"name"`
    Description      string                 `json:"description"`
    Category         string                 `json:"category"`
    Owner            string                 `json:"owner"`
    CurrentVersionID *string                `json:"current_version_id"`
    Status           string                 `json:"status"`
    CreatedAt        time.Time              `json:"created_at"`
    UpdatedAt        time.Time              `json:"updated_at"`
    Metadata         map[string]interface{} `json:"metadata"`
}

type SkillVersion struct {
    ID              string                 `json:"id"`
    SkillID         string                 `json:"skill_id"`
    Version         string                 `json:"version"`
    Content         string                 `json:"content"`
    ContentHash     string                 `json:"content_hash"`
    Author          string                 `json:"author"`
    CommitMessage   string                 `json:"commit_message"`
    ParentVersionID *string                `json:"parent_version_id"`
    CreatedAt       time.Time              `json:"created_at"`
    Metadata        map[string]interface{} `json:"metadata"`
}

type SkillMetadata struct {
    ID          string                 `json:"id"`
    Name        string                 `json:"name"`
    Description string                 `json:"description"`
    Category    string                 `json:"category"`
    Owner       string                 `json:"owner"`
    Status      string                 `json:"status"`
    Metadata    map[string]interface{} `json:"metadata"`
}

type SkillDetail struct {
    Skill
    Content string `json:"content"`
    Version string `json:"version"`
}

type SkillService struct {
    db *pgxpool.Pool
}

func NewSkillService(db *pgxpool.Pool) *SkillService {
    return &SkillService{db: db}
}

// ListSkills 返回 skill 元数据列表（不含 content）
func (s *SkillService) ListSkills(ctx context.Context, owner string, status string) ([]SkillMetadata, error) {
    query := `
        SELECT id, name, description, category, owner, status, metadata
        FROM skills
        WHERE 1=1
    `
    args := []interface{}{}
    argIdx := 1

    if owner != "" {
        query += fmt.Sprintf(" AND owner = $%d", argIdx)
        args = append(args, owner)
        argIdx++
    }

    if status != "" {
        query += fmt.Sprintf(" AND status = $%d", argIdx)
        args = append(args, status)
        argIdx++
    }

    query += " ORDER BY name"

    rows, err := s.db.Query(ctx, query, args...)
    if err != nil {
        return nil, fmt.Errorf("query skills: %w", err)
    }
    defer rows.Close()

    var skills []SkillMetadata
    for rows.Next() {
        var skill SkillMetadata
        var metadataJSON []byte

        err := rows.Scan(
            &skill.ID,
            &skill.Name,
            &skill.Description,
            &skill.Category,
            &skill.Owner,
            &skill.Status,
            &metadataJSON,
        )
        if err != nil {
            return nil, fmt.Errorf("scan skill: %w", err)
        }

        // Parse JSONB metadata
        if metadataJSON != nil {
            // TODO: unmarshal metadataJSON into skill.Metadata
        }

        skills = append(skills, skill)
    }

    return skills, nil
}

// GetSkill 返回 skill 详情（含 content）
func (s *SkillService) GetSkill(ctx context.Context, id string) (*SkillDetail, error) {
    query := `
        SELECT 
            s.id, s.name, s.description, s.category, s.owner, 
            s.current_version_id, s.status, s.created_at, s.updated_at, s.metadata,
            sv.content, sv.version
        FROM skills s
        LEFT JOIN skill_versions sv ON s.current_version_id = sv.id
        WHERE s.id = $1
    `

    var detail SkillDetail
    var metadataJSON []byte
    var content *string
    var version *string

    err := s.db.QueryRow(ctx, query, id).Scan(
        &detail.ID,
        &detail.Name,
        &detail.Description,
        &detail.Category,
        &detail.Owner,
        &detail.CurrentVersionID,
        &detail.Status,
        &detail.CreatedAt,
        &detail.UpdatedAt,
        &metadataJSON,
        &content,
        &version,
    )
    if err != nil {
        return nil, fmt.Errorf("get skill: %w", err)
    }

    if content != nil {
        detail.Content = *content
    }
    if version != nil {
        detail.Version = *version
    }

    return &detail, nil
}

// CreateSkill 创建新 skill
func (s *SkillService) CreateSkill(ctx context.Context, name, description, category, owner, content, author string, metadata map[string]interface{}) (*Skill, error) {
    tx, err := s.db.Begin(ctx)
    if err != nil {
        return nil, fmt.Errorf("begin tx: %w", err)
    }
    defer tx.Rollback(ctx)

    // 1. 创建 skill 记录
    skillID := uuid.New().String()
    _, err = tx.Exec(ctx, `
        INSERT INTO skills (id, name, description, category, owner, status)
        VALUES ($1, $2, $3, $4, $5, 'active')
    `, skillID, name, description, category, owner)
    if err != nil {
        return nil, fmt.Errorf("insert skill: %w", err)
    }

    // 2. 创建第一个版本
    versionID := uuid.New().String()
    contentHash := hashContent(content)
    _, err = tx.Exec(ctx, `
        INSERT INTO skill_versions (id, skill_id, version, content, content_hash, author, commit_message)
        VALUES ($1, $2, 'v1.0.0', $3, $4, $5, 'Initial version')
    `, versionID, skillID, content, contentHash, author)
    if err != nil {
        return nil, fmt.Errorf("insert skill version: %w", err)
    }

    // 3. 更新 skill 的 current_version_id
    _, err = tx.Exec(ctx, `
        UPDATE skills SET current_version_id = $1 WHERE id = $2
    `, versionID, skillID)
    if err != nil {
        return nil, fmt.Errorf("update skill current_version_id: %w", err)
    }

    if err := tx.Commit(ctx); err != nil {
        return nil, fmt.Errorf("commit tx: %w", err)
    }

    // 4. 返回创建的 skill
    return s.getSkillByID(ctx, skillID)
}

// UpdateSkill 更新 skill（创建新版本）
func (s *SkillService) UpdateSkill(ctx context.Context, id, content, author, commitMessage string) (*SkillVersion, error) {
    tx, err := s.db.Begin(ctx)
    if err != nil {
        return nil, fmt.Errorf("begin tx: %w", err)
    }
    defer tx.Rollback(ctx)

    // 1. 获取当前版本号
    var currentVersion string
    err = tx.QueryRow(ctx, `
        SELECT sv.version 
        FROM skills s
        JOIN skill_versions sv ON s.current_version_id = sv.id
        WHERE s.id = $1
    `, id).Scan(&currentVersion)
    if err != nil {
        return nil, fmt.Errorf("get current version: %w", err)
    }

    // 2. 计算新版本号（简单递增）
    newVersion := incrementVersion(currentVersion)

    // 3. 创建新版本
    versionID := uuid.New().String()
    contentHash := hashContent(content)
    var currentVersionID string
    err = tx.QueryRow(ctx, `SELECT current_version_id FROM skills WHERE id = $1`, id).Scan(&currentVersionID)
    if err != nil {
        return nil, fmt.Errorf("get current_version_id: %w", err)
    }

    _, err = tx.Exec(ctx, `
        INSERT INTO skill_versions (id, skill_id, version, content, content_hash, author, commit_message, parent_version_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, versionID, id, newVersion, content, contentHash, author, commitMessage, currentVersionID)
    if err != nil {
        return nil, fmt.Errorf("insert skill version: %w", err)
    }

    // 4. 更新 skill 的 current_version_id
    _, err = tx.Exec(ctx, `
        UPDATE skills SET current_version_id = $1, updated_at = NOW() WHERE id = $2
    `, versionID, id)
    if err != nil {
        return nil, fmt.Errorf("update skill current_version_id: %w", err)
    }

    if err := tx.Commit(ctx); err != nil {
        return nil, fmt.Errorf("commit tx: %w", err)
    }

    // 5. 返回新版本
    return &SkillVersion{
        ID:            versionID,
        SkillID:       id,
        Version:       newVersion,
        Content:       content,
        ContentHash:   contentHash,
        Author:        author,
        CommitMessage: commitMessage,
        CreatedAt:     time.Now(),
    }, nil
}

func (s *SkillService) getSkillByID(ctx context.Context, id string) (*Skill, error) {
    query := `SELECT id, name, description, category, owner, current_version_id, status, created_at, updated_at FROM skills WHERE id = $1`
    var skill Skill
    err := s.db.QueryRow(ctx, query, id).Scan(
        &skill.ID,
        &skill.Name,
        &skill.Description,
        &skill.Category,
        &skill.Owner,
        &skill.CurrentVersionID,
        &skill.Status,
        &skill.CreatedAt,
        &skill.UpdatedAt,
    )
    if err != nil {
        return nil, fmt.Errorf("get skill by id: %w", err)
    }
    return &skill, nil
}

func hashContent(content string) string {
    hash := sha256.Sum256([]byte(content))
    return hex.EncodeToString(hash[:])
}

func incrementVersion(version string) string {
    // 简单实现：v1.2.3 → v1.2.4
    // TODO: 使用 semver 库做更健壮的版本递增
    return version + "-next"
}
```

### 2.3 HTTP Handler

**文件**: `agent-os/internal/handlers/skill_handler.go`

```go
package handlers

import (
    "encoding/json"
    "net/http"

    "github.com/gorilla/mux"
    "your-project/internal/services"
)

type SkillHandler struct {
    service *services.SkillService
}

func NewSkillHandler(service *services.SkillService) *SkillHandler {
    return &SkillHandler{service: service}
}

func (h *SkillHandler) RegisterRoutes(r *mux.Router) {
    r.HandleFunc("/api/v1/skills", h.ListSkills).Methods("GET")
    r.HandleFunc("/api/v1/skills/{id}", h.GetSkill).Methods("GET")
    r.HandleFunc("/api/v1/skills", h.CreateSkill).Methods("POST")
    r.HandleFunc("/api/v1/skills/{id}", h.UpdateSkill).Methods("PUT")
}

// GET /api/v1/skills
func (h *SkillHandler) ListSkills(w http.ResponseWriter, r *http.Request) {
    owner := r.URL.Query().Get("owner")
    status := r.URL.Query().Get("status")

    skills, err := h.service.ListSkills(r.Context(), owner, status)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]interface{}{
        "skills": skills,
    })
}

// GET /api/v1/skills/{id}
func (h *SkillHandler) GetSkill(w http.ResponseWriter, r *http.Request) {
    vars := mux.Vars(r)
    id := vars["id"]

    skill, err := h.service.GetSkill(r.Context(), id)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(skill)
}

// POST /api/v1/skills
func (h *SkillHandler) CreateSkill(w http.ResponseWriter, r *http.Request) {
    var req struct {
        Name        string                 `json:"name"`
        Description string                 `json:"description"`
        Category    string                 `json:"category"`
        Owner       string                 `json:"owner"`
        Content     string                 `json:"content"`
        Author      string                 `json:"author"`
        Metadata    map[string]interface{} `json:"metadata"`
    }

    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    skill, err := h.service.CreateSkill(
        r.Context(),
        req.Name,
        req.Description,
        req.Category,
        req.Owner,
        req.Content,
        req.Author,
        req.Metadata,
    )
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    w.WriteStatus(http.StatusCreated)
    json.NewEncoder(w).Encode(skill)
}

// PUT /api/v1/skills/{id}
func (h *SkillHandler) UpdateSkill(w http.ResponseWriter, r *http.Request) {
    vars := mux.Vars(r)
    id := vars["id"]

    var req struct {
        Content       string `json:"content"`
        Author        string `json:"author"`
        CommitMessage string `json:"commit_message"`
    }

    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    version, err := h.service.UpdateSkill(r.Context(), id, req.Content, req.Author, req.CommitMessage)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(version)
}
```

---

## 3. agent-os-client SDK 实现

**文件**: `agent-os-client/src/skills.ts`

```typescript
import { BaseClient } from './base-client.js';

export interface SkillMetadata {
  id: string;
  name: string;
  description: string;
  category: string;
  owner: string;
  status: string;
  metadata?: Record<string, any>;
}

export interface SkillDetail {
  id: string;
  name: string;
  description: string;
  category: string;
  owner: string;
  status: string;
  content: string;
  version: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface CreateSkillRequest {
  name: string;
  description: string;
  category: string;
  owner: string;
  content: string;
  author: string;
  metadata?: Record<string, any>;
}

export interface UpdateSkillRequest {
  content: string;
  author: string;
  commit_message: string;
}

export class SkillsClient extends BaseClient {
  /**
   * 列出所有 skills（仅元数据，不含 content）
   */
  async list(params?: {
    owner?: string;
    status?: string;
  }): Promise<SkillMetadata[]> {
    const queryParams = new URLSearchParams();
    if (params?.owner) queryParams.append('owner', params.owner);
    if (params?.status) queryParams.append('status', params.status);

    const response = await this.get(`/skills?${queryParams.toString()}`);
    return response.skills;
  }

  /**
   * 获取 skill 详情（含 content）
   */
  async get(id: string): Promise<SkillDetail> {
    return this.get(`/skills/${id}`);
  }

  /**
   * 创建新 skill
   */
  async create(data: CreateSkillRequest): Promise<SkillDetail> {
    return this.post('/skills', data);
  }

  /**
   * 更新 skill（创建新版本）
   */
  async update(id: string, data: UpdateSkillRequest): Promise<any> {
    return this.put(`/skills/${id}`, data);
  }

  /**
   * 通过 name 查找 skill（便捷方法）
   */
  async findByName(name: string): Promise<SkillMetadata | null> {
    const skills = await this.list();
    return skills.find(s => s.name === name) || null;
  }
}
```

**文件**: `agent-os-client/src/index.ts`

```typescript
import { SkillsClient } from './skills.js';
import { SchedulerClient } from './scheduler.js';
import { MemoryClient } from './memory.js';
// ... 其他 clients

export class AgentOSClient {
  public skills: SkillsClient;
  public scheduler: SchedulerClient;
  public memory: MemoryClient;
  // ... 其他 clients

  constructor(baseURL: string, apiKey?: string) {
    const config = { baseURL, apiKey };
    
    this.skills = new SkillsClient(config);
    this.scheduler = new SchedulerClient(config);
    this.memory = new MemoryClient(config);
    // ...
  }
}

// Singleton
let clientInstance: AgentOSClient | null = null;

export function initAgentOSClient(baseURL: string, apiKey?: string): AgentOSClient {
  clientInstance = new AgentOSClient(baseURL, apiKey);
  return clientInstance;
}

export function getAgentOSClient(): AgentOSClient {
  if (!clientInstance) {
    throw new Error('AgentOSClient not initialized. Call initAgentOSClient() first.');
  }
  return clientInstance;
}
```

---

## 4. agent-ts 集成

### 4.1 启动时加载 Skill Registry

**文件**: `agent-ts/src/core/bootstrap/skill-registry.ts`

```typescript
import { getAgentOSClient } from 'agent-os-client';
import type { SkillMetadata } from 'agent-os-client';
import { logger } from '../../infrastructure/logging/index.js';

/**
 * 内存中的 skill 注册表（仅元数据）
 */
let skillRegistry: SkillMetadata[] = [];

/**
 * 从 Agent OS 加载 skill 注册表
 */
export async function loadSkillRegistry(): Promise<void> {
  logger.info('[SkillRegistry] Loading skills from Agent OS...');
  
  const client = getAgentOSClient();
  
  try {
    skillRegistry = await client.skills.list({
      owner: 'fin-agent',
      status: 'active'
    });
    
    logger.info(`[SkillRegistry] ✅ Loaded ${skillRegistry.length} skills`);
    
    // 打印所有 skills（便于调试）
    skillRegistry.forEach(skill => {
      logger.info(`  - ${skill.name}: ${skill.description} (id: ${skill.id})`);
    });
  } catch (error) {
    logger.error('[SkillRegistry] ❌ Failed to load skills:', error);
    throw error;
  }
}

/**
 * 获取 skill 注册表
 */
export function getSkillRegistry(): SkillMetadata[] {
  return skillRegistry;
}

/**
 * 通过 name 查找 skill 元数据
 */
export function findSkillByName(name: string): SkillMetadata | undefined {
  return skillRegistry.find(s => s.name === name);
}

/**
 * 通过 ID 查找 skill 元数据
 */
export function findSkillById(id: string): SkillMetadata | undefined {
  return skillRegistry.find(s => s.id === id);
}

/**
 * 模糊搜索 skill（通过 name 或 description）
 */
export function searchSkills(query: string): SkillMetadata[] {
  const lowerQuery = query.toLowerCase();
  return skillRegistry.filter(s => 
    s.name.toLowerCase().includes(lowerQuery) ||
    s.description.toLowerCase().includes(lowerQuery)
  );
}
```

### 4.2 运行时获取 Skill Content

**文件**: `agent-ts/src/core/skills/skill-executor.ts`

```typescript
import { getAgentOSClient } from 'agent-os-client';
import { logger } from '../../infrastructure/logging/index.js';

/**
 * 从 Agent OS 获取 skill 完整内容并执行
 */
export async function executeSkillById(skillId: string, context?: any): Promise<any> {
  logger.info(`[SkillExecutor] Executing skill: ${skillId}`);
  
  const client = getAgentOSClient();
  
  // 1. 从 Agent OS 获取 skill 详情（含 content）
  const skill = await client.skills.get(skillId);
  
  logger.info(`[SkillExecutor] Loaded skill: ${skill.name} (version: ${skill.version})`);
  
  // 2. 解析 skill content（markdown frontmatter + body）
  const parsed = parseSkillContent(skill.content);
  
  // 3. 执行 skill（传给 LLM）
  const result = await executeParsedSkill(parsed, context);
  
  logger.info(`[SkillExecutor] ✅ Skill executed: ${skill.name}`);
  
  return result;
}

/**
 * 通过 name 执行 skill（便捷方法）
 */
export async function executeSkillByName(skillName: string, context?: any): Promise<any> {
  const { findSkillByName } = await import('./bootstrap/skill-registry.js');
  
  const metadata = findSkillByName(skillName);
  if (!metadata) {
    throw new Error(`Skill not found: ${skillName}`);
  }
  
  return executeSkillById(metadata.id, context);
}

function parseSkillContent(content: string): any {
  // TODO: 解析 markdown frontmatter 和 body
  // 返回: { name, schedule, description, instructions, ... }
  return { content };
}

async function executeParsedSkill(parsed: any, context: any): Promise<any> {
  // TODO: 调用 LLM，传入 skill instructions + context
  return { success: true };
}
```

### 4.3 Webhook 集成

**文件**: `agent-ts/src/api/webhook/trigger.ts`

```typescript
import express from 'express';
import { executeSkillById } from '../../core/skills/skill-executor.js';
import { createSchedulerSession } from '../../services/scheduler/scheduler-session.js';
import { logger } from '../../infrastructure/logging/index.js';

const router = express.Router();

/**
 * Webhook endpoint for Agent OS Scheduler
 */
router.post('/trigger', async (req, res) => {
  const { task_id, task_name, run_id, params } = req.body;
  
  logger.info(`[Webhook] Task triggered: ${task_name} (run: ${run_id})`);
  
  try {
    // params.skill_id 是 Agent OS 传来的 skill UUID
    const { skill_id } = params;
    
    if (!skill_id) {
      return res.status(400).json({
        success: false,
        error: 'Missing skill_id in params'
      });
    }
    
    // 创建 session
    const { session } = await createSchedulerSession('fin');
    
    // 通过 ID 获取并执行 skill
    executeSkillById(skill_id, { 
      source: 'agent-os-scheduler',
      taskId: task_id,
      runId: run_id,
      session
    }).then(() => {
      logger.info(`[Webhook] ✅ Task completed: ${task_name}`);
    }).catch((error) => {
      logger.error(`[Webhook] ❌ Task failed: ${task_name}`, error);
    });
    
    // 立即返回成功（不等待 LLM）
    res.json({ success: true, run_id });
    
  } catch (error) {
    logger.error('[Webhook] Task execution failed:', error);
    res.status(500).json({ 
      success: false, 
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

export default router;
```

### 4.4 修改 Task Registration

**文件**: `agent-ts/src/core/bootstrap/task-registration.ts`

```typescript
import { getAgentOSClient } from 'agent-os-client';
import { getSkillRegistry } from './skill-registry.js';
import { logger } from '../../infrastructure/logging/index.js';

/**
 * 注册所有带 schedule 的 skills 到 Agent OS Scheduler
 */
export async function registerScheduledTasks(): Promise<void> {
  logger.info('[TaskRegistry] Registering scheduled tasks...');
  
  const client = getAgentOSClient();
  const registry = getSkillRegistry();
  
  // 筛选出有 schedule 的 skills
  const scheduledSkills = registry.filter(s => s.metadata?.schedule);
  
  logger.info(`[TaskRegistry] Found ${scheduledSkills.length} scheduled skills`);
  
  for (const skill of scheduledSkills) {
    try {
      await client.scheduler.registerTask({
        name: skill.name,
        owner: 'fin-agent',
        cron: skill.metadata.schedule,
        webhook_url: 'http://localhost:3002/api/webhook/trigger',
        params: {
          skill_id: skill.id  // 传 ID，不是 name
        },
        metadata: {
          description: skill.description,
          category: skill.category
        }
      });
      
      logger.info(`[TaskRegistry] ✅ Registered: ${skill.name} (${skill.metadata.schedule})`);
    } catch (error) {
      logger.error(`[TaskRegistry] ❌ Failed to register ${skill.name}:`, error);
    }
  }
  
  logger.info('[TaskRegistry] Task registration complete');
}
```

### 4.5 启动流程集成

**文件**: `agent-ts/src/index.ts`

```typescript
import { initAgentOSClient } from 'agent-os-client';
import { loadSkillRegistry } from './core/bootstrap/skill-registry.js';
import { registerScheduledTasks } from './core/bootstrap/task-registration.js';

async function bootstrap() {
  // 1. 初始化 Agent OS Client
  const agentOSURL = process.env.AGENT_OS_BASE_URL || 'http://localhost:8080';
  initAgentOSClient(agentOSURL);
  console.log('✅ Agent OS Client initialized');
  
  // 2. 加载 Skill Registry（仅元数据）
  await loadSkillRegistry();
  console.log('✅ Skill Registry loaded');
  
  // 3. 注册 scheduled tasks 到 Agent OS
  await registerScheduledTasks();
  console.log('✅ Scheduled tasks registered');
  
  // 4. 启动 Gateway API（接收 webhook）
  // ... 现有代码
}

bootstrap().catch(console.error);
```

---

## 5. 新增 Agent Tools

### 5.1 skill_list 工具

**文件**: `agent-ts/src/infrastructure/tools/skill/skill-list-tool.ts`

```typescript
import { tool } from 'ai';
import { z } from 'zod';
import { getSkillRegistry, searchSkills } from '../../../core/bootstrap/skill-registry.js';

export const skillListTool = tool({
  description: `
列出所有可用的 skills。可以通过关键词搜索。

用途：
- 查看系统有哪些 skills
- 搜索特定功能的 skill
- 了解 skill 的用途和分类
`,
  parameters: z.object({
    query: z.string().optional().describe('搜索关键词（可选）'),
    category: z.string().optional().describe('分类过滤（可选）')
  }),
  
  execute: async ({ query, category }) => {
    let skills = getSkillRegistry();
    
    // 搜索过滤
    if (query) {
      skills = searchSkills(query);
    }
    
    // 分类过滤
    if (category) {
      skills = skills.filter(s => s.category === category);
    }
    
    return {
      total: skills.length,
      skills: skills.map(s => ({
        id: s.id,
        name: s.name,
        description: s.description,
        category: s.category,
        schedule: s.metadata?.schedule
      }))
    };
  }
});
```

### 5.2 skill_get 工具

**文件**: `agent-ts/src/infrastructure/tools/skill/skill-get-tool.ts`

```typescript
import { tool } from 'ai';
import { z } from 'zod';
import { getAgentOSClient } from 'agent-os-client';
import { findSkillByName } from '../../../core/bootstrap/skill-registry.js';

export const skillGetTool = tool({
  description: `
获取 skill 的完整内容。

用途：
- 查看 skill 的详细指令
- 了解 skill 的执行逻辑
- 调试 skill 内容
`,
  parameters: z.object({
    name: z.string().describe('Skill 名称'),
  }),
  
  execute: async ({ name }) => {
    const client = getAgentOSClient();
    
    // 1. 从注册表找到 ID
    const metadata = findSkillByName(name);
    if (!metadata) {
      return { error: `Skill not found: ${name}` };
    }
    
    // 2. 从 Agent OS 获取完整内容
    const skill = await client.skills.get(metadata.id);
    
    return {
      id: skill.id,
      name: skill.name,
      description: skill.description,
      version: skill.version,
      content: skill.content,
      updated_at: skill.updated_at
    };
  }
});
```

### 5.3 skill_update 工具

**文件**: `agent-ts/src/infrastructure/tools/skill/skill-update-tool.ts`

```typescript
import { tool } from 'ai';
import { z } from 'zod';
import { getAgentOSClient } from 'agent-os-client';
import { findSkillByName } from '../../../core/bootstrap/skill-registry.js';

export const skillUpdateTool = tool({
  description: `
更新 skill 内容（进化系统使用）。

⚠️ 注意：此操作会创建新版本，需谨慎使用。

用途：
- 进化系统改进 skill
- 修复 skill 的 bug
- 优化 skill 的逻辑
`,
  parameters: z.object({
    name: z.string().describe('Skill 名称'),
    new_content: z.string().describe('新的 skill 内容（完整 markdown）'),
    reason: z.string().describe('修改原因'),
    author: z.string().default('evolution-system').describe('作者')
  }),
  
  execute: async ({ name, new_content, reason, author }) => {
    const client = getAgentOSClient();
    
    // 1. 从注册表找到 ID
    const metadata = findSkillByName(name);
    if (!metadata) {
      return { error: `Skill not found: ${name}` };
    }
    
    // 2. 更新 skill（创建新版本）
    const newVersion = await client.skills.update(metadata.id, {
      content: new_content,
      author,
      commit_message: reason
    });
    
    return {
      success: true,
      skill_id: metadata.id,
      skill_name: name,
      new_version: newVersion.version,
      message: `Skill updated: ${name} → ${newVersion.version}`
    };
  }
});
```

### 5.4 注册工具

**文件**: `agent-ts/src/infrastructure/tools/index.ts`

```typescript
import { skillListTool } from './skill/skill-list-tool.js';
import { skillGetTool } from './skill/skill-get-tool.js';
import { skillUpdateTool } from './skill/skill-update-tool.js';

export const SKILL_TOOLS = {
  skill_list: skillListTool,
  skill_get: skillGetTool,
  skill_update: skillUpdateTool,
};

// 合并到总工具集
export const ALL_TOOLS = {
  ...EXISTING_TOOLS,
  ...SKILL_TOOLS,
};
```

---

## 6. 数据迁移

### 6.1 迁移现有 Skills 到 Agent OS

**文件**: `agent-ts/scripts/migrate-skills-to-os.ts`

```typescript
import fs from 'fs';
import path from 'path';
import { initAgentOSClient } from 'agent-os-client';

async function migrateSkills() {
  // 1. 初始化 client
  const client = initAgentOSClient('http://localhost:8080');
  
  // 2. 读取本地 skills 目录
  const skillsDir = path.join(process.cwd(), 'skills');
  const files = fs.readdirSync(skillsDir).filter(f => f.endsWith('.md'));
  
  console.log(`Found ${files.length} skill files`);
  
  for (const file of files) {
    const skillName = path.basename(file, '.md');
    const content = fs.readFileSync(path.join(skillsDir, file), 'utf-8');
    
    // 3. 解析 frontmatter
    const frontmatterMatch = content.match(/^---\n([\s\S]+?)\n---/);
    let description = '';
    let category = 'general';
    let metadata: any = {};
    
    if (frontmatterMatch) {
      const frontmatter = frontmatterMatch[1];
      const descMatch = frontmatter.match(/description:\s*"(.+)"/);
      const scheduleMatch = frontmatter.match(/schedule:\s*"(.+)"/);
      const categoryMatch = frontmatter.match(/category:\s*"(.+)"/);
      
      if (descMatch) description = descMatch[1];
      if (categoryMatch) category = categoryMatch[1];
      if (scheduleMatch) metadata.schedule = scheduleMatch[1];
    }
    
    // 4. 创建 skill 到 Agent OS
    try {
      const skill = await client.skills.create({
        name: skillName,
        description,
        category,
        owner: 'fin-agent',
        content,
        author: 'migration-script',
        metadata
      });
      
      console.log(`✅ Migrated: ${skillName} (id: ${skill.id})`);
    } catch (error) {
      console.error(`❌ Failed to migrate ${skillName}:`, error);
    }
  }
  
  console.log('Migration complete');
}

migrateSkills().catch(console.error);
```

**运行迁移**：
```bash
cd agent-ts
npm run migrate:skills
```

---

## 7. 测试

### 7.1 Agent OS API 测试

```bash
# 1. 创建 skill
curl -X POST http://localhost:8080/api/v1/skills \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_skill",
    "description": "测试 skill",
    "category": "test",
    "owner": "fin-agent",
    "content": "---\nname: test_skill\n---\n\n# Test Skill\n\nThis is a test.",
    "author": "test-user"
  }'

# 2. 列出所有 skills
curl http://localhost:8080/api/v1/skills?owner=fin-agent

# 3. 获取 skill 详情
curl http://localhost:8080/api/v1/skills/{skill_id}

# 4. 更新 skill
curl -X PUT http://localhost:8080/api/v1/skills/{skill_id} \
  -H "Content-Type: application/json" \
  -d '{
    "content": "---\nname: test_skill\n---\n\n# Test Skill (Updated)\n\nThis is updated.",
    "author": "test-user",
    "commit_message": "Updated instructions"
  }'
```

### 7.2 agent-ts 集成测试

```typescript
// agent-ts/src/core/skills/__tests__/skill-executor.test.ts

import { executeSkillById } from '../skill-executor.js';
import { loadSkillRegistry } from '../../bootstrap/skill-registry.js';

describe('Skill Executor', () => {
  beforeAll(async () => {
    await loadSkillRegistry();
  });
  
  it('should execute skill by ID', async () => {
    const result = await executeSkillById('test-skill-id');
    expect(result).toBeDefined();
  });
  
  it('should throw if skill not found', async () => {
    await expect(executeSkillById('invalid-id')).rejects.toThrow();
  });
});
```

---

## 8. 部署清单

### 8.1 Agent OS 部署

```bash
# 1. 创建数据库表
psql -d quant_investment -f agent-os/migrations/009_create_skills.sql

# 2. 重新编译 Agent OS
cd agent-os
go build -o bin/agent-os ./cmd/server

# 3. 重启 Agent OS
docker-compose restart agent-os
# 或
./scripts/deploy.sh

# 4. 验证 API
curl http://localhost:8080/api/v1/skills
```

### 8.2 agent-ts 部署

```bash
# 1. 更新 agent-os-client
cd agent-os-client
npm run build
npm link

# 2. 安装到 agent-ts
cd agent-ts
npm link agent-os-client
npm install

# 3. 迁移现有 skills 到 Agent OS
npm run migrate:skills

# 4. 重启 agent-ts
npm run build
npm run start

# 5. 验证 skill 加载
# 查看日志：
# [SkillRegistry] ✅ Loaded 15 skills
#   - morning_ai_analysis: 工作日早盘分析 (id: ...)
#   - pool_maintenance: 股票池维护 (id: ...)
#   ...
```

---

## 9. 成功标准

### 功能完整性
- [ ] Agent OS 实现 skills 表和 API
- [ ] agent-os-client 实现 SkillsClient
- [ ] agent-ts 启动时加载 skill registry
- [ ] agent-ts 运行时从 Agent OS 获取 skill content
- [ ] Webhook 通过 skill_id 触发执行
- [ ] 新增 3 个 skill 工具（list/get/update）
- [ ] 迁移脚本成功迁移现有 skills

### 性能指标
- Skill registry 加载时间 < 500ms
- Skill content 获取延迟 < 100ms
- 支持 100+ skills

### 测试覆盖
- Agent OS API 单元测试
- agent-os-client SDK 测试
- agent-ts 集成测试

---

**状态**: ✅ 设计完成，Ready for Implementation  
**预计工作量**: 
- Agent OS 实现: 2 天
- agent-os-client SDK: 1 天
- agent-ts 集成: 1 天
- 测试 & 部署: 1 天
- **总计**: 5 天
