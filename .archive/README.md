# Archive Directory

This directory contains archived temporary files and historical documents that are no longer actively used but may be useful for reference.

## Structure

### 2026-06-reports/
Temporary work reports and status documents from June 2026:
- Daily work summaries
- Implementation status checks
- Task completion reports
- Scheduler refactor series
- Final summaries and checklists

**Purpose**: These documents captured work-in-progress during active development. They're archived here for historical reference and audit trail purposes.

**Note**: Active project documentation should be maintained in the `/docs/` directory using the categorized structure.

### 2026-06-fixes/
Temporary fix reports and debugging documents from earlier in June 2026.

## Archive Policy

Documents are moved here when they:
1. **Are temporary** - Created during active development as scratch notes or progress tracking
2. **Are completed** - The work described is finished and integrated
3. **Have historical value** - May be useful for understanding past decisions or debugging similar issues
4. **Should not be deleted** - Contain information worth preserving for audit trail

## What NOT to Archive Here

- **Active documentation** → Keep in `/docs/` with proper categorization
- **Project core docs** → Keep in project root (CLAUDE.md, README.md, INDEX.md)
- **Subproject docs** → Keep in subproject directories (agent-ts/CLAUDE.md, etc.)
- **Truly temporary files** → Use .gitignore and delete after use

## Maintenance

- Archives are organized by date period (e.g., `2026-06-reports/`)
- Files should maintain their original names for traceability
- Consider consolidating very old archives periodically (e.g., yearly rollup)
- Git history provides additional context - use `git log --follow` to trace file movements

## Related

- `/docs/` - Active project documentation with categorized structure
- `/docs/archive/` - Legacy docs directory (to be consolidated)
- `.gitignore` - Patterns to prevent temporary files from being committed

---

**Last updated**: 2026-06-26
