# Risk Bridge Migration Design

**Date:** 2026-05-21  
**Status:** Approved  
**Type:** Refactoring

## Problem

`python/risk_bridge.py` is a glue layer that operates entirely within the quant domain, but it's located in the project root directory. This causes:

1. **Incorrect module placement**: The file bridges `portfolio.db` and `quantsys.risk`, both quant-internal concerns, yet sits outside the quant module
2. **sys.path hacks**: `quant/quantsys/cli/risk_query.py` must manipulate sys.path to import from the parent project
3. **Code duplication**: A cleaner version already exists at `quant/quantsys/risk/bridge.py`

## Current State

### Files
- `python/risk_bridge.py` (500 lines) - Old version with `QUANT_AVAILABLE` fallback logic and sys.path manipulation
- `quant/quantsys/risk/bridge.py` (424 lines) - Clean version with proper imports

### References
1. `quant/quantsys/cli/risk_query.py:48` - Uses sys.path hack to import from `python/`
2. `python/akshare_bridge.py:39` - Direct import from `python/`

### Import Pattern (Current)

**risk_query.py:**
```python
# Lines 42-48
project_root = Path(__file__).resolve().parents[3]
python_dir = project_root / "python"
if str(python_dir) not in sys.path:
    sys.path.insert(0, str(python_dir))
from risk_bridge import RiskBridge
```

**akshare_bridge.py:**
```python
# Line 39
from risk_bridge import RiskBridge
```

## Solution

### Approach: Direct Migration (Chosen)

Delete `python/risk_bridge.py` and update all references to use `quant/quantsys/risk/bridge.py`.

**Why this approach:**
- `quant/quantsys/risk/bridge.py` already exists and is superior (no sys.path hacks, cleaner error handling)
- Only 2 reference points, impact is contained
- Eliminates code duplication immediately
- `akshare_bridge.py` is already the TS/Python boundary layer, no additional wrapper needed

**Alternatives considered:**
- **Soft link transition**: Keep `python/risk_bridge.py` as a re-export wrapper temporarily. Rejected: adds complexity for minimal risk reduction with only 2 references.
- **Keep python/ as boundary**: Make `python/risk_bridge.py` a thin wrapper. Rejected: `akshare_bridge.py` already serves as the boundary layer.

## Design

### File Changes

**Delete:**
- `python/risk_bridge.py`

**Modify:**
- `quant/quantsys/cli/risk_query.py` - Remove sys.path hack, use relative import
- `python/akshare_bridge.py` - Use absolute import

### Import Pattern (After Migration)

**risk_query.py:**
```python
from quantsys.risk.bridge import RiskBridge
```

**akshare_bridge.py:**
```python
from quantsys.risk.bridge import RiskBridge
```

### Implementation Steps

1. **Update risk_query.py**
   - Remove lines 42-47 (sys.path manipulation)
   - Change line 48 from `from risk_bridge import RiskBridge` to `from quantsys.risk.bridge import RiskBridge`
   - Update `_build_bridge()` function to use the new import

2. **Update akshare_bridge.py**
   - Change line 39 from `from risk_bridge import RiskBridge` to `from quantsys.risk.bridge import RiskBridge`

3. **Delete python/risk_bridge.py**
   - Remove the file entirely

4. **Verification**
   - Run risk query CLI commands to verify functionality
   - Test akshare_bridge.py integration
   - Ensure no import errors

## Risk Assessment

**Low Risk:**
- Only 2 files affected
- Target file (`quant/quantsys/risk/bridge.py`) already exists and is tested
- Changes are straightforward import path updates
- No logic changes required

**Rollback Plan:**
- Git revert if issues arise
- The old `python/risk_bridge.py` remains in git history

## Success Criteria

- [ ] `risk_query.py` imports from `quantsys.risk.bridge` without sys.path manipulation
- [ ] `akshare_bridge.py` imports from `quantsys.risk.bridge` successfully
- [ ] `python/risk_bridge.py` is deleted
- [ ] All risk-related CLI commands work correctly
- [ ] No import errors in any Python module
