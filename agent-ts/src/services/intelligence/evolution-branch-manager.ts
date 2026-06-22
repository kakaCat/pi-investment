/**
 * Evolution Branch Manager - Git 分支管理器
 *
 * 管理进化分支的创建、提交和合并。
 * 每次进化在独立分支上工作，验证通过后自动合并到 main。
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface BranchInfo {
  name: string;
  created: boolean;
  commits: string[];
}

/**
 * 创建进化分支
 */
export async function createEvolutionBranch(evolutionId: string): Promise<string> {
  const branchName = `evolution/${evolutionId}`;

  console.log(`🌿 创建进化分支: ${branchName}`);

  try {
    // 检查分支是否已存在
    const { stdout: existingBranches } = await execAsync('git branch --list');
    if (existingBranches.includes(branchName)) {
      console.log(`  ⚠️  分支已存在，切换到该分支`);
      await execAsync(`git checkout ${branchName}`);
      return branchName;
    }

    // 创建并切换到新分支
    await execAsync(`git checkout -b ${branchName}`);
    console.log(`  ✅ 分支创建成功`);

    return branchName;
  } catch (error: any) {
    throw new Error(`创建分支失败: ${error.message}`);
  }
}

/**
 * 提交更改到当前分支
 */
export async function commitChanges(
  message: string,
  files: string[]
): Promise<string> {
  console.log(`📝 提交更改: ${files.length} 个文件`);

  try {
    // 添加文件到暂存区
    for (const file of files) {
      await execAsync(`git add "${file}"`);
      console.log(`  + ${file}`);
    }

    // 提交
    const { stdout } = await execAsync(`git commit -m "${message}"`);

    // 提取 commit hash
    const commitMatch = stdout.match(/\[.*?([a-f0-9]{7})\]/);
    const commitHash = commitMatch ? commitMatch[1] : 'unknown';

    console.log(`  ✅ 提交成功: ${commitHash}`);
    return commitHash;
  } catch (error: any) {
    throw new Error(`提交失败: ${error.message}`);
  }
}

/**
 * 合并分支到目标分支
 */
export async function mergeToBranch(
  sourceBranch: string,
  targetBranch: string = 'main'
): Promise<void> {
  console.log(`🔀 合并 ${sourceBranch} → ${targetBranch}`);

  try {
    // 切换到目标分支
    await execAsync(`git checkout ${targetBranch}`);

    // 合并源分支
    const { stdout } = await execAsync(`git merge ${sourceBranch} --no-edit`);

    if (stdout.includes('Already up to date')) {
      console.log(`  ℹ️  已是最新，无需合并`);
    } else if (stdout.includes('CONFLICT')) {
      throw new Error('合并冲突，需要手动解决');
    } else {
      console.log(`  ✅ 合并成功`);
    }
  } catch (error: any) {
    // 如果合并失败，尝试中止合并
    try {
      await execAsync('git merge --abort');
    } catch {
      // 忽略中止失败
    }
    throw new Error(`合并失败: ${error.message}`);
  }
}

/**
 * 回滚到指定分支（放弃当前分支的更改）
 */
export async function rollbackToBranch(targetBranch: string = 'main'): Promise<void> {
  console.log(`↩️  回滚到 ${targetBranch}`);

  try {
    // 获取当前分支名
    const { stdout: currentBranch } = await execAsync('git branch --show-current');
    const branchToDelete = currentBranch.trim();

    // 切换到目标分支
    await execAsync(`git checkout ${targetBranch}`);

    // 删除进化分支（如果不是目标分支）
    if (branchToDelete && branchToDelete !== targetBranch) {
      await execAsync(`git branch -D ${branchToDelete}`);
      console.log(`  ✅ 已删除分支: ${branchToDelete}`);
    }
  } catch (error: any) {
    throw new Error(`回滚失败: ${error.message}`);
  }
}

/**
 * 删除指定分支
 */
export async function deleteBranch(branchName: string): Promise<void> {
  console.log(`🗑️  删除分支: ${branchName}`);

  try {
    // 确保不在要删除的分支上
    const { stdout: currentBranch } = await execAsync('git branch --show-current');
    if (currentBranch.trim() === branchName) {
      await execAsync('git checkout main');
    }

    // 删除分支
    await execAsync(`git branch -D ${branchName}`);
    console.log(`  ✅ 分支已删除`);
  } catch (error: any) {
    throw new Error(`删除分支失败: ${error.message}`);
  }
}

/**
 * 获取当前分支名
 */
export async function getCurrentBranch(): Promise<string> {
  try {
    const { stdout } = await execAsync('git branch --show-current');
    return stdout.trim();
  } catch (error: any) {
    throw new Error(`获取当前分支失败: ${error.message}`);
  }
}

/**
 * 检查是否有未提交的更改
 */
export async function hasUncommittedChanges(): Promise<boolean> {
  try {
    const { stdout } = await execAsync('git status --porcelain');
    return stdout.trim().length > 0;
  } catch (error: any) {
    throw new Error(`检查状态失败: ${error.message}`);
  }
}

/**
 * 获取分支的提交历史
 */
export async function getBranchCommits(branchName: string, limit: number = 10): Promise<string[]> {
  try {
    const { stdout } = await execAsync(
      `git log ${branchName} --oneline -n ${limit}`
    );
    return stdout.trim().split('\n').filter(line => line.length > 0);
  } catch (error: any) {
    throw new Error(`获取提交历史失败: ${error.message}`);
  }
}

/**
 * 创建备份标签（用于回滚）
 */
export async function createBackupTag(tagName: string): Promise<void> {
  console.log(`🏷️  创建备份标签: ${tagName}`);

  try {
    await execAsync(`git tag ${tagName}`);
    console.log(`  ✅ 标签创建成功`);
  } catch (error: any) {
    throw new Error(`创建标签失败: ${error.message}`);
  }
}

/**
 * 恢复到备份标签
 */
export async function restoreFromTag(tagName: string): Promise<void> {
  console.log(`🔄 恢复到标签: ${tagName}`);

  try {
    await execAsync(`git reset --hard ${tagName}`);
    console.log(`  ✅ 恢复成功`);
  } catch (error: any) {
    throw new Error(`恢复失败: ${error.message}`);
  }
}
