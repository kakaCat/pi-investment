# 删除 ML 残骸 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all disabled ML-related code including Python ML modules, ml-pipeline directory, and dependent TypeScript services.

**Architecture:** Direct deletion of unused code paths. The ML functionality has been replaced by pure TypeScript technical analysis in `quant-tools.ts`. No refactoring needed - just clean removal.

**Tech Stack:** Git, TypeScript, npm (for verification)

---

## File Structure

### Files to Delete
- `python/ml/signal_trainer.py`
- `python/ml/signal_predictor.py`
- `python/ml/__init__.py`
- `python/ml/__pycache__/` (directory)
- `ml-pipeline/` (entire directory with all subdirectories)
- `src/services/quant/quant-service.ts`
- `src/services/quant/quant-service.test.ts`

### Files to Keep (Verification)
- `src/infrastructure/tools/quant-tools.ts` - Pure TS implementation, no changes needed
- `src/services/quant/kelly-criterion.ts` - Independent module
- `src/services/quant/types.ts` - Type definitions

---

## Task 1: Delete Python ML Directory

**Files:**
- Delete: `python/ml/` (entire directory)

- [ ] **Step 1: Verify directory exists and check contents**

```bash
ls -la python/ml/
```

Expected output: Shows `signal_trainer.py`, `signal_predictor.py`, `__init__.py`, and `__pycache__/`

- [ ] **Step 2: Remove python/ml directory using git**

```bash
git rm -rf python/ml/
```

Expected output: 
```
rm 'python/ml/__init__.py'
rm 'python/ml/signal_predictor.py'
rm 'python/ml/signal_trainer.py'
```

- [ ] **Step 3: Verify deletion**

```bash
ls python/ml/ 2>&1
```

Expected output: `ls: python/ml/: No such file or directory`

- [ ] **Step 4: Check git status**

```bash
git status
```

Expected output: Shows `python/ml/` files as deleted

---

## Task 2: Delete ml-pipeline Directory

**Files:**
- Delete: `ml-pipeline/` (entire directory)

- [ ] **Step 1: Verify directory exists and check size**

```bash
du -sh ml-pipeline/
ls -la ml-pipeline/ | head -15
```

Expected output: Shows directory size and contents including `backtesting/`, `features/`, `training/`, `ml_pipeline.py`

- [ ] **Step 2: Remove ml-pipeline directory using git**

```bash
git rm -rf ml-pipeline/
```

Expected output: Multiple `rm 'ml-pipeline/...'` lines for all files in the directory

- [ ] **Step 3: Verify deletion**

```bash
ls ml-pipeline/ 2>&1
```

Expected output: `ls: ml-pipeline/: No such file or directory`

- [ ] **Step 4: Check git status**

```bash
git status
```

Expected output: Shows many `ml-pipeline/` files as deleted

---

## Task 3: Delete QuantService TypeScript Files

**Files:**
- Delete: `src/services/quant/quant-service.ts`
- Delete: `src/services/quant/quant-service.test.ts`

- [ ] **Step 1: Verify files exist**

```bash
ls -la src/services/quant/quant-service.ts src/services/quant/quant-service.test.ts
```

Expected output: Shows both files with their sizes

- [ ] **Step 2: Remove QuantService implementation**

```bash
git rm src/services/quant/quant-service.ts
```

Expected output: `rm 'src/services/quant/quant-service.ts'`

- [ ] **Step 3: Remove QuantService test**

```bash
git rm src/services/quant/quant-service.test.ts
```

Expected output: `rm 'src/services/quant/quant-service.test.ts'`

- [ ] **Step 4: Verify remaining files in quant directory**

```bash
ls -la src/services/quant/
```

Expected output: Should show only `kelly-criterion.ts` and `types.ts` (no quant-service files)

- [ ] **Step 5: Check git status**

```bash
git status
```

Expected output: Shows `quant-service.ts` and `quant-service.test.ts` as deleted

---

## Task 4: Search for Remaining References

**Files:**
- Check: All TypeScript files in `src/`

- [ ] **Step 1: Search for QuantService imports**

```bash
grep -r "QuantService" src/ --include="*.ts" --exclude-dir=node_modules
```

Expected output: No matches (empty output)

- [ ] **Step 2: Search for quant-service imports**

```bash
grep -r "quant-service" src/ --include="*.ts" --exclude-dir=node_modules
```

Expected output: No matches (empty output)

- [ ] **Step 3: Search for ml-pipeline references**

```bash
grep -r "ml-pipeline" src/ --include="*.ts" --exclude-dir=node_modules
```

Expected output: No matches (empty output)

- [ ] **Step 4: Search for python/ml references**

```bash
grep -r "python/ml" src/ --include="*.ts" --exclude-dir=node_modules
```

Expected output: No matches (empty output)

- [ ] **Step 5: Document findings**

If any references found in steps 1-4, note them here for manual review. Otherwise, proceed to next task.

---

## Task 5: Verify TypeScript Compilation

**Files:**
- Check: All TypeScript files compile without errors

- [ ] **Step 1: Run TypeScript type checking**

```bash
npm run typecheck
```

Expected output: No errors, clean compilation

- [ ] **Step 2: If errors occur, review and fix**

If typecheck fails:
1. Read the error messages
2. Identify which files reference deleted code
3. Remove or refactor those references
4. Re-run typecheck

Expected: All type errors resolved

- [ ] **Step 3: Verify typecheck passes**

```bash
npm run typecheck
```

Expected output: Clean compilation with no errors

---

## Task 6: Run Test Suite

**Files:**
- Check: All tests pass

- [ ] **Step 1: Run full test suite**

```bash
npm run test
```

Expected output: All tests pass (note: quant-service tests are deleted, so they won't run)

- [ ] **Step 2: If test failures occur, investigate**

If tests fail:
1. Read the failure messages
2. Check if failures are related to deleted ML code
3. Fix or remove failing tests
4. Re-run tests

Expected: All tests pass

- [ ] **Step 3: Verify test suite passes**

```bash
npm run test
```

Expected output: All tests pass with no failures

---

## Task 7: Verify Build

**Files:**
- Check: Project builds successfully

- [ ] **Step 1: Clean previous build artifacts**

```bash
rm -rf dist/
```

Expected output: No output (silent success)

- [ ] **Step 2: Run build**

```bash
npm run build
```

Expected output: Build completes successfully with no errors

- [ ] **Step 3: Verify dist directory created**

```bash
ls -la dist/ | head -10
```

Expected output: Shows compiled JavaScript files in dist/

- [ ] **Step 4: Verify quant-service not in build output**

```bash
ls dist/services/quant/quant-service.* 2>&1
```

Expected output: `ls: dist/services/quant/quant-service.*: No such file or directory`

---

## Task 8: Verify quant-tools Still Works

**Files:**
- Check: `src/infrastructure/tools/quant-tools.ts`

- [ ] **Step 1: Read quant-tools to verify it's pure TS**

```bash
head -30 src/infrastructure/tools/quant-tools.ts
```

Expected output: Shows file header with comment "纯 TypeScript 技术评分工具，不依赖 ML 模型"

- [ ] **Step 2: Verify no ML imports**

```bash
grep -E "ml-pipeline|python/ml|QuantService" src/infrastructure/tools/quant-tools.ts
```

Expected output: No matches (empty output)

- [ ] **Step 3: Verify predictStockSignalTool is exported**

```bash
grep "export.*predictStockSignalTool" src/infrastructure/tools/quant-tools.ts
```

Expected output: Shows the export line for predictStockSignalTool

---

## Task 9: Commit Changes

**Files:**
- Commit: All deleted files

- [ ] **Step 1: Review git status**

```bash
git status
```

Expected output: Shows all deleted files (python/ml/, ml-pipeline/, quant-service files)

- [ ] **Step 2: Review diff summary**

```bash
git diff --stat --cached
```

Expected output: Shows deletion statistics for all removed files

- [ ] **Step 3: Commit the changes**

```bash
git commit -m "chore: 删除 ML 残骸 - 移除 ml-pipeline、python/ml 和 QuantService

- 删除 python/ml/ 目录（signal_trainer, signal_predictor）
- 删除 ml-pipeline/ 目录（完整的回测引擎和训练模块）
- 删除 src/services/quant/quant-service.ts 及其测试
- 保留 quant-tools.ts 的纯 TS 技术评分实现
- 保留 kelly-criterion.ts 独立模块

ML 功能已被纯 TypeScript 技术分析方案替代。"
```

Expected output: Commit hash and summary showing files changed

- [ ] **Step 4: Verify commit**

```bash
git log -1 --stat
```

Expected output: Shows the commit with all deleted files listed

---

## Task 10: Final Verification

**Files:**
- Verify: Complete system integrity

- [ ] **Step 1: Run all checks in sequence**

```bash
npm run typecheck && npm run test && npm run build
```

Expected output: All three commands succeed with no errors

- [ ] **Step 2: Verify deleted directories don't exist**

```bash
test ! -d python/ml && test ! -d ml-pipeline && echo "✅ Directories successfully deleted" || echo "❌ Directories still exist"
```

Expected output: `✅ Directories successfully deleted`

- [ ] **Step 3: Verify deleted TS files don't exist**

```bash
test ! -f src/services/quant/quant-service.ts && test ! -f src/services/quant/quant-service.test.ts && echo "✅ QuantService files successfully deleted" || echo "❌ Files still exist"
```

Expected output: `✅ QuantService files successfully deleted`

- [ ] **Step 4: Count total files deleted**

```bash
git show --stat | grep "files changed"
```

Expected output: Shows approximately 15-20 files deleted

- [ ] **Step 5: Document completion**

All ML remnants successfully removed. The codebase now uses pure TypeScript technical analysis via `quant-tools.ts`.

---

## Rollback Plan

If issues are discovered after completion:

```bash
# View the deletion commit
git log --oneline -1

# Revert the entire commit
git revert HEAD

# Or restore specific files
git checkout HEAD^ -- python/ml/
git checkout HEAD^ -- ml-pipeline/
git checkout HEAD^ -- src/services/quant/quant-service.ts
git checkout HEAD^ -- src/services/quant/quant-service.test.ts
```

---

## Success Criteria

- ✅ `python/ml/` directory deleted
- ✅ `ml-pipeline/` directory deleted  
- ✅ `src/services/quant/quant-service.ts` deleted
- ✅ `src/services/quant/quant-service.test.ts` deleted
- ✅ No remaining references to deleted code
- ✅ TypeScript compilation passes
- ✅ All tests pass
- ✅ Build succeeds
- ✅ `quant-tools.ts` still functional (pure TS implementation)
- ✅ Changes committed to git
