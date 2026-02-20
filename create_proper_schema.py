import sqlite3

conn = sqlite3.connect('data/fantasyfolio.db')
cursor = conn.cursor()

output = []

# Header
output.append("-- FantasyFolio Database Schema")
output.append("-- v0.4.15 - Clean schema without FTS internal tables")
output.append("")

# Get all regular tables (NOT FTS tables, not FTS internal tables)
cursor.execute("""
    SELECT sql FROM sqlite_master 
    WHERE type='table'
    AND sql IS NOT NULL 
    AND name NOT LIKE '%_fts%'
    AND name NOT LIKE 'sqlite_%'
    ORDER BY name
""")
for row in cursor.fetchall():
    if row[0]:
        output.append(row[0] + ';')
        output.append('')

# Get FTS virtual tables
cursor.execute("""
    SELECT sql FROM sqlite_master 
    WHERE type='table'
    AND name LIKE '%_fts'
    AND name NOT LIKE '%_fts_%'
    ORDER BY name
""")
fts_tables = cursor.fetchall()
if fts_tables:
    output.append("-- FTS5 Virtual Tables (SQLite creates internal tables automatically)")
    output.append('')
    for row in fts_tables:
        if row[0]:
            output.append(row[0] + ';')
            output.append('')

# Get indexes (excluding FTS internal indexes)
cursor.execute("""
    SELECT sql FROM sqlite_master 
    WHERE type='index'
    AND sql IS NOT NULL
    AND name NOT LIKE '%_fts%'
    ORDER BY name
""")
indexes = cursor.fetchall()
if indexes:
    output.append("-- Indexes")
    output.append('')
    for row in indexes:
        if row[0]:
            output.append(row[0] + ';')
            output.append('')

conn.close()

with open('data/schema.sql', 'w') as f:
    f.write('\n'.join(output))

print(f"Clean schema exported: {len(output)} lines")
