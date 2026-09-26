import * as fs from 'fs/promises';
import * as path from 'path';
import {
  RtmAccepting,
  TestCase,
  TestingCoverage,
  TaskToTestsMap,
  RtmMetadata,
  TaskItem,
} from '../types/rtm';

/**
 * 测试用例解析结果
 */
interface ParsedTestCase {
  id: string;
  title: string;
  covers: string[]; // 任务 ID 列表
  validates: string[]; // FR ID 列表
  source: string; // 源文件路径
}

/**
 * 解析测试文档，提取 covers 和 validates 标注
 */
async function parseTestDocument(filePath: string): Promise<ParsedTestCase[]> {
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    const lines = content.split('\n');
    
    const testCases: ParsedTestCase[] = [];
    let currentTestCase: Partial<ParsedTestCase> | null = null;
    let testCaseCounter = 1;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      // 识别测试用例标题（## TC-1: ... 或 ### 测试用例 1）
      if (line.match(/^##\s+(TC-\d+):/)) {
        const match = line.match(/^##\s+(TC-\d+):\s*(.+)/);
        if (match) {
          if (currentTestCase && currentTestCase.id) {
            testCases.push(currentTestCase as ParsedTestCase);
          }
          currentTestCase = {
            id: match[1],
            title: match[2],
            covers: [],
            validates: [],
            source: `${filePath}#${i + 1}`,
          };
        }
      } else if (line.match(/^###\s+测试用例\s+(\d+)/)) {
        const match = line.match(/^###\s+测试用例\s+(\d+)/);
        if (match) {
          if (currentTestCase && currentTestCase.id) {
            testCases.push(currentTestCase as ParsedTestCase);
          }
          currentTestCase = {
            id: `TC-${match[1]}`,
            title: `测试用例 ${match[1]}`,
            covers: [],
            validates: [],
            source: `${filePath}#${i + 1}`,
          };
        }
      }

      // 提取 covers: 标注
      if (line.includes('covers:') && currentTestCase) {
        const match = line.match(/covers:\s*([\w\-,\s]+)/i);
        if (match) {
          const taskIds = match[1].split(',').map(id => id.trim()).filter(Boolean);
          currentTestCase.covers = [...(currentTestCase.covers || []), ...taskIds];
        }
      }

      // 提取 validates: 标注
      if (line.includes('validates:') && currentTestCase) {
        const match = line.match(/validates:\s*([\w\-,\s]+)/i);
        if (match) {
          const frIds = match[1].split(',').map(id => id.trim()).filter(Boolean);
          currentTestCase.validates = [...(currentTestCase.validates || []), ...frIds];
        }
      }
    }

    // 添加最后一个测试用例
    if (currentTestCase && currentTestCase.id) {
      testCases.push(currentTestCase as ParsedTestCase);
    }

    return testCases;
  } catch (error: any) {
    if (error.code === 'ENOENT') {
      return [];
    }
    throw new Error(`Failed to parse test document ${filePath}: ${error.message}`);
  }
}

/**
 * 扫描需求目录，查找所有测试文档
 */
async function findTestDocuments(requirementDir: string): Promise<string[]> {
  const testDocs: string[] = [];

  // 1. 查找根目录的 test-cases.md
  const testCasesPath = path.join(requirementDir, 'test-cases.md');
  try {
    await fs.access(testCasesPath);
    testDocs.push(testCasesPath);
  } catch {
    // 文件不存在，忽略
  }

  // 2. 查找 tasks/ 目录下的 test.md
  const tasksDir = path.join(requirementDir, 'tasks');
  try {
    const taskFiles = await fs.readdir(tasksDir);
    for (const file of taskFiles) {
      if (file === 'test.md' || file.endsWith('-test.md')) {
        testDocs.push(path.join(tasksDir, file));
      }
    }
  } catch {
    // 目录不存在，忽略
  }

  // 3. 查找 tasks/t-xxx/ 子目录下的 test.md
  try {
    const taskDirs = await fs.readdir(tasksDir);
    for (const dir of taskDirs) {
      if (dir.startsWith('t-')) {
        const testPath = path.join(tasksDir, dir, 'test.md');
        try {
          await fs.access(testPath);
          testDocs.push(testPath);
        } catch {
          // 文件不存在，忽略
        }
      }
    }
  } catch {
    // 目录不存在，忽略
  }

  return testDocs;
}

/**
 * 构建任务到测试的追溯映射
 */
function buildTaskToTestsMap(testCases: ParsedTestCase[]): TaskToTestsMap {
  const map: TaskToTestsMap = {};

  for (const testCase of testCases) {
    for (const taskId of testCase.covers) {
      if (!map[taskId]) {
        map[taskId] = [];
      }
      if (!map[taskId].includes(testCase.id)) {
        map[taskId].push(testCase.id);
      }
    }
  }

  return map;
}

/**
 * 计算测试覆盖度
 */
function calculateTestingCoverage(
  tasks: TaskItem[],
  taskToTests: TaskToTestsMap
): TestingCoverage {
  const totalTasks = tasks.length;
  const testedTasks = tasks.filter(task => taskToTests[task.id]?.length > 0);
  const untested = tasks
    .filter(task => !taskToTests[task.id] || taskToTests[task.id].length === 0)
    .map(task => task.id);

  return {
    total_tasks: totalTasks,
    tested_tasks: testedTasks.length,
    untested,
    rate: totalTasks > 0 ? Math.round((testedTasks.length / totalTasks) * 100) : 100,
  };
}

/**
 * 生成 rtm-accepting.yml
 */
export async function generateAcceptingRtm(
  requirementId: string,
  requirementDir: string,
  tasks: TaskItem[]
): Promise<RtmAccepting> {
  // 1. 扫描测试文档
  const testDocPaths = await findTestDocuments(requirementDir);

  // 2. 解析所有测试用例
  const allTestCases: ParsedTestCase[] = [];
  for (const docPath of testDocPaths) {
    const testCases = await parseTestDocument(docPath);
    allTestCases.push(...testCases);
  }

  // 3. 构建追溯映射
  const taskToTests = buildTaskToTestsMap(allTestCases);

  // 4. 计算覆盖度
  const coverage = calculateTestingCoverage(tasks, taskToTests);

  // 5. 生成 RTM
  const rtm: RtmAccepting = {
    metadata: {
      stage: 'accepting',
      requirement_id: requirementId,
      generated_at: new Date().toISOString(),
      version: 1,
      generated_by: 'dsh-pmboard',
    },
    outputs: {
      test_cases: allTestCases.map(tc => ({
        id: tc.id,
        title: tc.title,
        covers: tc.covers,
        validates: tc.validates,
      })),
    },
    traceability: {
      task_to_tests: taskToTests,
    },
    coverage: {
      testing: coverage,
    },
  };

  return rtm;
}

/**
 * 验收门禁检查
 */
export function checkAcceptanceGate(coverage: TestingCoverage): {
  passed: boolean;
  message: string;
  uncovered?: string[];
} {
  const MINIMUM_COVERAGE = 80; // 最低 80% 测试覆盖度

  if (coverage.rate >= MINIMUM_COVERAGE) {
    return {
      passed: true,
      message: `测试覆盖度 ${coverage.rate}% (${coverage.tested_tasks}/${coverage.total_tasks})，通过门禁`,
    };
  } else {
    return {
      passed: false,
      message: `测试覆盖度不足 ${coverage.rate}% (${coverage.tested_tasks}/${coverage.total_tasks})，需要 ≥${MINIMUM_COVERAGE}%`,
      uncovered: coverage.untested,
    };
  }
}
