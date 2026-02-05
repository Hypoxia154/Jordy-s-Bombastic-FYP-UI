import sqlite3

conn = sqlite3.connect("app.db")
conn.row_factory = sqlite3.Row

# Check users
print("--- USERS ---")
users = conn.execute("SELECT username, role FROM users").fetchall()
for u in users:
    print(dict(u))

# Check sessions
print("\n--- CHAT SESSIONS ---")
sessions = conn.execute("SELECT * FROM chat_sessions").fetchall()
if not sessions:
    print("No chat sessions found.")
else:
    for s in sessions:
        print(dict(s))

conn.close()
