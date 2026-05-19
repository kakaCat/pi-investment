# Database Info Display Design

**Date:** 2026-05-19  
**Status:** Approved  
**Author:** Claude (Kiro)

## Overview

Add database basic information display to the Welcome page system status section, showing database path, file size, and connection status in the same format as the backend API service display.

## Background

Currently, the Welcome page shows only a simple "✅ 已连接" or "❌ 未连接" status for the database connection. Users want to see more detailed information including the database file path and size, similar to how the backend API service displays its URL.

## Goals

1. Display database path in the system status section
2. Display database file size in human-readable format (KB/MB/GB)
3. Maintain consistent display format with existing "后端API服务" item
4. Keep implementation simple and minimal

## Non-Goals

- Displaying detailed statistics (stock count, K-line records, etc.)
- Showing table structure information
- Adding interactive features or drill-down capabilities
- Refactoring the health check architecture

## Design

### API Changes

**Endpoint:** `GET /api/health`

**Current Response:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "db_connected": true
}
```

**New Response:**
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

**Fields:**
- `db_info.path` (string): Absolute path to the database file
- `db_info.size_mb` (float): File size in megabytes (for programmatic use)
- `db_info.size_display` (string): Human-readable size with appropriate unit (KB/MB/GB)

**Error Handling:**
- If database is not connected, `db_info` will be `null`
- If file size cannot be determined, `size_display` will show "未知"

### Backend Implementation

**File:** `quant/api/server.py`

**Changes to `health_check()` function:**

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

**Key Points:**
- Use existing `db_path` global variable (already defined in `init_services()`)
- Use `pathlib.Path.stat().st_size` to get file size
- Format size with appropriate unit (KB for < 1MB, MB for < 1GB, GB for >= 1GB)
- Return `null` for `db_info` if database is not accessible

### Frontend Implementation

**File:** `quant-web/src/components/Welcome.tsx`

**Interface Changes:**

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

**State Update:**

```typescript
const response = await fetch('/api/health')
const data = await response.json()
setStatus({
  backend: data.status === 'ok',
  database: data.db_connected,
  model: data.model_loaded,
  db_info: data.db_info
})
```

**Display Update:**

Update the "数据库连接" step description to show multi-line information:

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

**Display Format:**
```
✅ 已连接
路径: /Users/mac/Documents/ai/pi-investment/.pi-invest/stock-db/stocks.db
大小: 2.5 GB
```

**Key Points:**
- Use newline characters (`\n`) to separate lines in the description
- Show detailed info only when both `database` is true and `db_info` is available
- Fallback to simple "✅ 已连接" if `db_info` is missing (backward compatibility)
- Maintain consistent format with "后端API服务" display style

### Error Handling

**Backend:**
- Wrap file operations in try-catch to prevent health check failures
- Return `null` for `db_info` if any error occurs
- Log errors for debugging but don't expose to frontend

**Frontend:**
- Check both `status.database` and `status.db_info` before displaying details
- Gracefully degrade to simple status message if detailed info is unavailable
- No error UI needed - absence of details is not an error state

### Testing Considerations

**Backend Testing:**
1. Verify health endpoint returns correct database path
2. Verify size calculation and formatting (test with different file sizes)
3. Verify `db_info` is `null` when database is not accessible
4. Verify backward compatibility (existing clients still work)

**Frontend Testing:**
1. Verify multi-line display renders correctly in Steps component
2. Verify display with and without `db_info` data
3. Verify refresh button updates database info
4. Verify layout doesn't break with long file paths

**Manual Testing:**
1. Start backend and frontend
2. Open Welcome page
3. Verify database info displays correctly
4. Click refresh button and verify info updates
5. Test with database file missing (should show "❌ 未连接")

## Implementation Order

1. **Backend changes** - Modify `health_check()` in `server.py`
2. **Frontend interface** - Update TypeScript interfaces
3. **Frontend display** - Update Steps component description
4. **Testing** - Verify both backend and frontend work correctly

## Risks and Mitigations

**Risk:** Long file paths may break UI layout  
**Mitigation:** Ant Design Steps component handles long descriptions well; test with actual path

**Risk:** File size calculation may fail on some systems  
**Mitigation:** Wrap in try-catch, return `null` on error, frontend handles gracefully

**Risk:** Backward compatibility with existing clients  
**Mitigation:** New field is optional, existing clients ignore it

## Success Criteria

- [ ] Database path displays correctly on Welcome page
- [ ] File size displays in human-readable format (KB/MB/GB)
- [ ] Display format matches "后端API服务" style
- [ ] Refresh button updates database info
- [ ] No errors when database is not accessible
- [ ] Backward compatible with existing health check consumers
