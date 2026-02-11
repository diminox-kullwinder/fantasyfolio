# Known Issues - FantasyFolio

## v0.4.9 Issues (2026-02-11)

### change_journal Table Missing (Medium Priority)
**Discovered:** 2026-02-11 during Windows deployment testing  
**Reporter:** Matthew  
**Status:** Logged for v0.4.10  

**Problem:**
- Code in `fantasyfolio/services/change_journal.py` expects `change_journal` table
- Table is missing from `data/schema.sql`
- Results in error logs: `sqlite3.OperationalError: no such table: change_journal`

**Impact:**
- Cosmetic (doesn't break core functionality)
- Change journal feature doesn't work
- Error messages clutter application logs

**Root Cause:**
- Table schema never added to schema.sql
- Feature was implemented but never fully integrated

**Proposed Fix (Choose One):**
1. **Option A - Add table schema** (if audit trail is valuable):
   ```sql
   CREATE TABLE IF NOT EXISTS change_journal (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       entity_type TEXT NOT NULL,
       entity_id INTEGER NOT NULL,
       action TEXT NOT NULL,
       field_name TEXT,
       old_value TEXT,
       new_value TEXT,
       source TEXT DEFAULT 'api',
       user_info TEXT,
       timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   CREATE INDEX IF NOT EXISTS idx_change_journal_entity ON change_journal(entity_type, entity_id);
   CREATE INDEX IF NOT EXISTS idx_change_journal_timestamp ON change_journal(timestamp);
   ```

2. **Option B - Gracefully disable** (recommended for single-user):
   - Wrap journal calls in try/except
   - Add feature flag to disable
   - Keep code for future use

**Recommendation:** Option B - disable for single-user use case. No compliance requirements, backups handle recovery better than journal rollback.

**Kanban Task:** `task-20260211094446849965`  
**Assigned:** Hal  
**Priority:** Medium  
**Target:** v0.4.10

---

**Note:** This file tracks issues found during testing and deployment. It persists across model changes, reboots, and session restarts.
