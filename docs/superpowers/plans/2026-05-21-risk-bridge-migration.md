# Risk Bridge Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all references from `python/risk_bridge.py` to `quant/quantsys/risk/bridge.py` and delete the old file.

**Architecture:** Direct import path updates in two files, followed by deletion of the obsolete file. No logic changes required.

**Tech Stack:** Python 3.x, quantsys module

---

## File Structure

**Modify:**
- `quant/quantsys/cli/risk_query.py` - Remove sys.path hack, update import
- `python/akshare_bridge.py` - Update import path

**Delete:**
- `python/risk_bridge.py` - Obsolete file

---

### Task 1: Update risk_query.py Import

**Files:**
- Modify: `quant/quantsys/cli/risk_query.py:42-52`

- [ ] **Step 1: Read current file to verify line numbers**

Run:
```bash
head -60 quant/quantsys/cli/risk_query.py
```

Expected: Lines 42-48 contain sys.path manipulation and import

- [ ] **Step 2: Update _build_bridge function**

Replace lines 42-52 with:

```python
def _build_bridge():
    from quantsys.risk.bridge import RiskBridge
    
    project_root = Path(__file__).resolve().parents[3]
    portfolio_db = project_root / ".pi-invest" / "portfolio.db"
    quant_db = project_root / ".pi-invest" / "stock-db" / "stocks.db"
    return RiskBridge(str(portfolio_db), str(quant_db))
```

- [ ] **Step 3: Verify syntax**

Run:
```bash
python -m py_compile quant/quantsys/cli/risk_query.py
```

Expected: No output (successful compilation)

- [ ] **Step 4: Test import works**

Run:
```bash
cd quant && python -c "from quantsys.cli.risk_query import check_trade_risk; print('Import successful')"
```

Expected: "Import successful"

- [ ] **Step 5: Commit**

```bash
git add quant/quantsys/cli/risk_query.py
git commit -m "refactor(risk): remove sys.path hack from risk_query.py

- Replace sys.path manipulation with direct import from quantsys.risk.bridge
- Simplify _build_bridge() function
- Part of risk_bridge migration"
```

---

### Task 2: Update akshare_bridge.py Import

**Files:**
- Modify: `python/akshare_bridge.py:39`

- [ ] **Step 1: Read current import line**

Run:
```bash
sed -n '35,45p' python/akshare_bridge.py
```

Expected: Line 39 shows `from risk_bridge import RiskBridge`

- [ ] **Step 2: Update import statement**

Replace line 39:

```python
from quantsys.risk.bridge import RiskBridge
```

- [ ] **Step 3: Verify syntax**

Run:
```bash
python -m py_compile python/akshare_bridge.py
```

Expected: No output (successful compilation)

- [ ] **Step 4: Test import works**

Run:
```bash
python -c "import sys; sys.path.insert(0, 'quant'); exec(open('python/akshare_bridge.py').read().split('# Setup logger')[0]); print('Import successful')"
```

Expected: "Import successful" (or no import errors)

- [ ] **Step 5: Commit**

```bash
git add python/akshare_bridge.py
git commit -m "refactor(risk): update akshare_bridge to use quantsys.risk.bridge

- Change import from python/risk_bridge to quantsys.risk.bridge
- Part of risk_bridge migration"
```

---

### Task 3: Delete Obsolete risk_bridge.py

**Files:**
- Delete: `python/risk_bridge.py`

- [ ] **Step 1: Verify no other references exist**

Run:
```bash
grep -r "from risk_bridge" --include="*.py" --include="*.ts" . 2>/dev/null | grep -v ".git"
```

Expected: No output (all references updated)

- [ ] **Step 2: Verify no direct imports exist**

Run:
```bash
grep -r "import risk_bridge" --include="*.py" --include="*.ts" . 2>/dev/null | grep -v ".git"
```

Expected: No output

- [ ] **Step 3: Delete the file**

Run:
```bash
git rm python/risk_bridge.py
```

Expected: "rm 'python/risk_bridge.py'"

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(risk): remove obsolete python/risk_bridge.py

- All references migrated to quant/quantsys/risk/bridge.py
- Eliminates code duplication and sys.path hacks
- Completes risk_bridge migration"
```

---

### Task 4: Integration Verification

**Files:**
- Test: `quant/quantsys/cli/risk_query.py`
- Test: `python/akshare_bridge.py`

- [ ] **Step 1: Test risk_query functions**

Run:
```bash
cd quant && python -c "
from quantsys.cli.risk_query import check_trade_risk, calculate_position_size, calculate_stop_loss
print('✓ All risk_query functions imported successfully')
"
```

Expected: "✓ All risk_query functions imported successfully"

- [ ] **Step 2: Test akshare_bridge can import RiskBridge**

Run:
```bash
python -c "
import sys
sys.path.insert(0, 'quant')
from quantsys.risk.bridge import RiskBridge
print('✓ RiskBridge imported successfully from quantsys.risk.bridge')
"
```

Expected: "✓ RiskBridge imported successfully from quantsys.risk.bridge"

- [ ] **Step 3: Verify no import errors in full module**

Run:
```bash
cd quant && python -c "import quantsys.cli.risk_query; print('✓ risk_query module loads without errors')"
```

Expected: "✓ risk_query module loads without errors"

- [ ] **Step 4: Check git status**

Run:
```bash
git status
```

Expected: Clean working tree (all changes committed)

- [ ] **Step 5: Document completion**

Create verification summary:

```bash
echo "Risk Bridge Migration Complete

✓ risk_query.py updated - sys.path hack removed
✓ akshare_bridge.py updated - import path corrected  
✓ python/risk_bridge.py deleted - code duplication eliminated
✓ All imports verified - no errors

Migration successful." > /tmp/risk-bridge-migration-complete.txt
cat /tmp/risk-bridge-migration-complete.txt
```

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ Update risk_query.py (Task 1)
- ✅ Update akshare_bridge.py (Task 2)
- ✅ Delete python/risk_bridge.py (Task 3)
- ✅ Verification (Task 4)

**Placeholder Scan:**
- ✅ No TBD/TODO markers
- ✅ All code blocks complete
- ✅ All commands have expected output

**Type Consistency:**
- ✅ RiskBridge class name consistent across all tasks
- ✅ Import paths consistent: `quantsys.risk.bridge`
- ✅ File paths exact and consistent
