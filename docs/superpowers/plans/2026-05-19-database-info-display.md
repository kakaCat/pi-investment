# Database Info Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display database path, file size, and connection status on the Welcome page system status section.

**Architecture:** Extend the existing `/api/health` endpoint to return database file information (path and size), then update the frontend Welcome component to display this information in the "数据库连接" step description using multi-line format.

**Tech Stack:** Python Flask (backend), React + TypeScript + Ant Design (frontend)

---

## File Structure

**Backend:**
- Modify: `quant/api/server.py` - Add database info to health check endpoint

**Frontend:**
- Modify: `quant-web/src/components/Welcome.tsx` - Add interface and display logic

**No new files needed** - this is a pure enhancement to existing components.

---

### Task 1: Backend - Add Database Info to Health Endpoint

**Files:**
- Modify: `quant/api/server.py:99-114`

- [ ] **Step 1: Modify health_check function to include database info**

Replace the existing `health_check()` function (lines 99-114) with:

```python
@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    db_connected = False
    db_info = None
    
    try:
        conn = get_db()
        conn.close()
        db_connected = True
        
        # Get database file info
        if db_path.exists():
            size_bytes = db_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            
            # Format size display
            if size_mb < 1:
                size_display = f"{size_bytes / 1024:.1f} KB"
            elif size_mb < 1024:
                size_display = f"{size_mb:.1f} MB"
            else:
                size_display = f"{size_mb / 1024:.1f} GB"
            
            db_info = {
                'path': str(db_path),
                'size_mb': round(size_mb, 2),
                'size_display': size_display
            }
    except Exception as e:
        print(f"Health check error: {e}")
    
    return jsonify({
        'status': 'ok',
        'model_loaded': model is not None,
        'db_connected': db_connected,
        'db_info': db_info
    })
```

- [ ] **Step 2: Test the endpoint manually**

Start the backend server:
```bash
cd quant
python api/server.py
```

In another terminal, test the endpoint:
```bash
curl http://localhost:3001/api/health | jq
```

Expected output:
```json
{
  "status": "ok",
  "model_loaded": true,
  "db_connected": true,
  "db_info": {
    "path": "/Users/mac/Documents/ai/pi-investment/.pi-invest/stock-db/stocks.db",
    "size_mb": 2500.5,
    "size_display": "2.5 GB"
  }
}
```

- [ ] **Step 3: Test with database not accessible**

Temporarily rename the database file:
```bash
mv .pi-invest/stock-db/stocks.db .pi-invest/stock-db/stocks.db.bak
```

Test the endpoint again:
```bash
curl http://localhost:3001/api/health | jq
```

Expected output:
```json
{
  "status": "ok",
  "model_loaded": false,
  "db_connected": false,
  "db_info": null
}
```

Restore the database:
```bash
mv .pi-invest/stock-db/stocks.db.bak .pi-invest/stock-db/stocks.db
```

- [ ] **Step 4: Commit backend changes**

```bash
git add quant/api/server.py
git commit -m "feat(api): add database info to health endpoint"
```

---

### Task 2: Frontend - Update TypeScript Interfaces

**Files:**
- Modify: `quant-web/src/components/Welcome.tsx:7-11`

- [ ] **Step 1: Add DbInfo interface**

Add the new interface after the imports (around line 6):

```typescript
interface DbInfo {
  path: string
  size_mb: number
  size_display: string
}

interface SystemStatus {
  backend: boolean
  database: boolean
  model: boolean
  db_info?: DbInfo | null
}
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd quant-web
npm run build
```

Expected: No TypeScript errors

- [ ] **Step 3: Commit interface changes**

```bash
git add quant-web/src/components/Welcome.tsx
git commit -m "feat(web): add DbInfo interface for database details"
```

---

### Task 3: Frontend - Update State Management

**Files:**
- Modify: `quant-web/src/components/Welcome.tsx:14-18,25-40`

- [ ] **Step 1: Update initial state to include db_info**

Modify the state initialization (around line 14):

```typescript
const [status, setStatus] = React.useState<SystemStatus>({
  backend: false,
  database: false,
  model: false,
  db_info: null
})
```

- [ ] **Step 2: Update checkStatus to parse db_info from API**

Modify the `checkStatus` function (around line 25-40):

```typescript
const checkStatus = async () => {
  setLoading(true)
  try {
    const response = await fetch('/api/health')
    const data = await response.json()
    setStatus({
      backend: data.status === 'ok',
      database: data.db_connected,
      model: data.model_loaded,
      db_info: data.db_info
    })
  } catch (error) {
    console.error('Failed to check status:', error)
  } finally {
    setLoading(false)
  }
}
```

- [ ] **Step 3: Verify TypeScript compilation**

```bash
cd quant-web
npm run build
```

Expected: No TypeScript errors

- [ ] **Step 4: Commit state management changes**

```bash
git add quant-web/src/components/Welcome.tsx
git commit -m "feat(web): update state to include database info"
```

---

### Task 4: Frontend - Update Display Logic

**Files:**
- Modify: `quant-web/src/components/Welcome.tsx:67-72`

- [ ] **Step 1: Update database connection step description**

Modify the "数据库连接" step in the Steps component (around line 67-72):

```typescript
{
  title: '数据库连接',
  status: status.database ? 'finish' : 'error',
  icon: getStatusIcon(status.database),
  description: status.database && status.db_info
    ? `✅ 已连接\n路径: ${status.db_info.path}\n大小: ${status.db_info.size_display}`
    : status.database
    ? '✅ 已连接'
    : '❌ 未连接'
}
```

- [ ] **Step 2: Build the frontend**

```bash
cd quant-web
npm run build
```

Expected: Build succeeds with no errors

- [ ] **Step 3: Commit display changes**

```bash
git add quant-web/src/components/Welcome.tsx
git commit -m "feat(web): display database path and size in Welcome page"
```

---

### Task 5: Integration Testing

**Files:**
- Test: Manual testing in browser

- [ ] **Step 1: Start backend server**

```bash
cd quant
python api/server.py
```

Expected: Server starts on port 3001

- [ ] **Step 2: Start frontend dev server**

```bash
cd quant-web
npm run dev
```

Expected: Dev server starts on port 5173

- [ ] **Step 3: Test normal display**

Open browser to `http://localhost:5173`

Expected display in "数据库连接" step:
```
✅ 已连接
路径: /Users/mac/Documents/ai/pi-investment/.pi-invest/stock-db/stocks.db
大小: 2.5 GB
```

- [ ] **Step 4: Test refresh button**

Click the "刷新" button in the system status card.

Expected: Database info updates (loading spinner shows, then info reappears)

- [ ] **Step 5: Test with long path (visual check)**

Verify that long file paths don't break the layout. The Ant Design Steps component should handle text wrapping automatically.

Expected: Path wraps to multiple lines if needed, no horizontal overflow

- [ ] **Step 6: Test error state**

Stop the backend server (Ctrl+C), then click refresh.

Expected: "❌ 未连接" displays (no database info shown)

- [ ] **Step 7: Document testing completion**

Create a simple test report:

```bash
echo "# Database Info Display - Manual Test Report

Date: $(date +%Y-%m-%d)

## Test Results

- [x] Database info displays correctly (path + size)
- [x] Refresh button updates info
- [x] Long paths wrap correctly
- [x] Error state shows correctly when backend is down
- [x] No console errors
- [x] Layout remains intact

## Browser Tested
- Chrome/Safari/Firefox (specify which you used)

All tests passed ✅
" > docs/test-reports/2026-05-19-database-info-display.md
```

- [ ] **Step 8: Commit test report**

```bash
git add docs/test-reports/2026-05-19-database-info-display.md
git commit -m "docs: add manual test report for database info display"
```

---

## Success Criteria Checklist

After completing all tasks, verify:

- [ ] Database path displays correctly on Welcome page
- [ ] File size displays in human-readable format (KB/MB/GB)
- [ ] Display format matches "后端API服务" style (multi-line description)
- [ ] Refresh button updates database info
- [ ] No errors when database is not accessible (shows "❌ 未连接")
- [ ] Backward compatible (API returns db_info as optional field)
- [ ] No TypeScript compilation errors
- [ ] No console errors in browser
- [ ] Layout remains intact with long file paths

---

## Rollback Plan

If issues are found after deployment:

1. **Backend rollback:**
   ```bash
   git revert <commit-hash-of-backend-change>
   git push
   ```

2. **Frontend rollback:**
   ```bash
   git revert <commit-hash-of-frontend-change>
   cd quant-web && npm run build
   ```

The changes are backward compatible - old frontend will ignore the new `db_info` field.
