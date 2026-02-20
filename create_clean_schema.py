import sqlite3

conn = sqlite3.connect('data/fantasyfolio.db')
cursor = conn.cursor()

# Get all schema objects except FTS internal tables
cursor.execute("""
    SELECT sql FROM sqlite_master 
    WHERE sql IS NOT NULL 
    AND name NOT LIKE '%_fts_%'
    AND name NOT LIKE 'sqlite_%'
    ORDER BY 
        CASE type
            WHEN 'table' THEN 1
            WHEN 'index' THEN 2
            WHEN 'view' THEN 3
            WHEN 'trigger' THEN 4
        END,
        name
""")

with open('data/schema_clean.sql', 'w') as f:
    for row in cursor.fetchall():
        if row[0]:
            f.write(row[0] + ';\n\n')

conn.close()
print("Clean schema exported to data/schema_clean.sql")
