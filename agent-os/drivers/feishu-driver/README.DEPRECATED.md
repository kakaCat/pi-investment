# Feishu Driver (DEPRECATED)

⚠️ **This Python driver is deprecated as of 2026-08-14.**

**Please use the new Go-based notification system instead.**

## New Way (Recommended)

```bash
# Send notification
agent-os notify send --channel trading --title "Test" --content "Hello"

# List channels
agent-os notify list

# View logs
agent-os notify logs
```

## Old Way (Deprecated)

```bash
python main.py send --user yunpeng --title "Test" --message "Hello"
python main.py send --channel general --title "Alert" --message "..."
```

---

## Why Deprecated?

The new notification system provides:

- ✅ **Database-driven configuration** (no hardcoded mappings)
- ✅ **Complete logging** (track all notifications)
- ✅ **Unified interface** (consistent with Agent OS)
- ✅ **Easy to extend** (add Slack, Email, etc.)
- ✅ **No Python dependency** (integrated into agent-os binary)

---

## Migration Guide

See: `/NOTIFICATION-SYSTEM-FINAL-REPORT.md`

Implementation: `/internal/cmd/notify.go`

---

## This Directory Will Be Removed

**Timeline**: This directory will be removed in ~1 month (September 2026)

Please migrate to the new system before then.
