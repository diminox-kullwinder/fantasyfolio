# FantasyFolio Feature Backlog

## v0.4.11+ Features

### Advanced Search Query Builder Enhancement
**Priority:** Medium  
**Effort:** 4-6 hours  
**Requested:** 2026-02-12 by Matthew

**Current State:**
Simple advanced search with top-level scope/format filters and basic text search:
- Scope: All folders / Current folder
- Format: STL, OBJ, 3MF (separate dropdown)
- Search terms: Title & Content / Title only / Content only

**Requested Enhancement:**
Full query builder with per-line field selection and flexible criteria:

**Example Query:**
```
Line 1: [Field: Name] [is] "XYZ"
  AND
Line 2: [Field: File Type] [is] "STL"
  OR  
Line 3: [Field: File Type] [is] "OBJ"
  AND
Line 4: [Field: Modified Date] [after] "2024-01-01"
```

**Requirements:**
1. **Field dropdown per line:**
   - Name / Filename
   - Title
   - File Type / Format
   - Modified Date
   - Created Date
   - File Size
   - Collection (3D)
   - Publisher (PDF)
   - Game System (PDF)

2. **Operator dropdown (context-aware):**
   - Text fields: is, contains, starts with, ends with
   - Date fields: before, after, between
   - Number fields: equals, greater than, less than, between
   - Enum fields: is, is not

3. **Input type changes based on field:**
   - Text: input box
   - Date: date picker
   - Format: dropdown (STL/OBJ/3MF/PDF/etc)
   - Size: number input with unit selector

4. **Boolean logic between lines:**
   - AND / OR dropdown between each line
   - Proper SQL generation with parentheses

5. **UI/UX:**
   - Add/remove lines dynamically
   - Visual grouping for AND/OR logic
   - Query preview/summary
   - Save/load common queries

**Technical Implementation:**
- Frontend: Dynamic form builder with field-aware validation
- Backend: SQL query builder with safe parameter binding
- Consider using a query builder library (e.g., SQLAlchemy filter syntax)

**Related Issues:**
- Current advanced search works but is limited
- Users need more granular filtering for large collections

---

## Other Backlog Items

*(Add future feature requests here)*
