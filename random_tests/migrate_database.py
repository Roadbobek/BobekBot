import sqlite3

# --- CONFIGURATION ---
# Make sure this matches the DB_FILE constant in your main bot script.
DB_FILE = "../BobekBot_sqlite3.db"

def migrate_database():
    """Applies necessary schema changes to an existing database without losing data."""
    print(f"[MIGRATE] Connecting to database '{DB_FILE}'...")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            print("[MIGRATE] Connection successful. Checking schema...")

            # --- Helper function to check if a column exists in a table ---
            def column_exists(table_name, column_name):
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [info[1] for info in cursor.fetchall()]
                return column_name in columns

            # --- MIGRATION 1: Add timestamp columns to 'guilds' table ---
            if not column_exists('guilds', 'first_seen_timestamp'):
                print("[MIGRATE] Adding 'first_seen_timestamp' to 'guilds' table...")
                cursor.execute("ALTER TABLE guilds ADD COLUMN first_seen_timestamp INTEGER")
            else:
                print("[MIGRATE] 'guilds.first_seen_timestamp' column already exists. Skipping.")

            if not column_exists('guilds', 'removal_timestamp'):
                print("[MIGRATE] Adding 'removal_timestamp' to 'guilds' table...")
                cursor.execute("ALTER TABLE guilds ADD COLUMN removal_timestamp INTEGER")
            else:
                print("[MIGRATE] 'guilds.removal_timestamp' column already exists. Skipping.")

            # --- MIGRATION 2: Add timestamp column to 'users' table ---
            if not column_exists('users', 'first_seen_timestamp'):
                print("[MIGRATE] Adding 'first_seen_timestamp' to 'users' table...")
                cursor.execute("ALTER TABLE users ADD COLUMN first_seen_timestamp INTEGER")
            else:
                print("[MIGRATE] 'users.first_seen_timestamp' column already exists. Skipping.")
            
            # --- MIGRATION 3: Create guild_name_history table ---
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_name_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                old_name TEXT NOT NULL,
                new_name TEXT NOT NULL,
                change_timestamp INTEGER NOT NULL,
                FOREIGN KEY (guild_id) REFERENCES guilds (guild_id)
            );
            """)
            print("[MIGRATE] Ensured 'guild_name_history' table exists.")

            conn.commit()
            print("[MIGRATE] All migrations applied successfully!")

    except sqlite3.Error as e:
        print(f"[MIGRATE] An error occurred during database migration: {e}")

if __name__ == "__main__":
    migrate_database()
