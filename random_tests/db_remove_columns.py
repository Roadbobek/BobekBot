import sqlite3

# --- CONFIGURATION ---
# Make sure this matches the DB_FILE constant in your main bot script.
DB_FILE = "../BobekBot_sqlite3.db"

def remove_columns_from_economy():
    """Safely removes the wins, losses, and last_daily columns from the economy table."""
    print(f"[MIGRATE] Connecting to database '{DB_FILE}'...")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            print("[MIGRATE] Connection successful. Beginning column removal process...")

            # Step 1: Create a new table with the desired final schema (without the columns to be removed).
            print("[MIGRATE] Step 1: Creating new temporary table 'economy_new'...")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS economy_new (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 100,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            );
            """)

            # Step 2: Copy the data you want to keep from the old table to the new one.
            print("[MIGRATE] Step 2: Copying existing user_id and balance data...")
            cursor.execute("""
            INSERT INTO economy_new (user_id, balance)
            SELECT user_id, balance
            FROM economy;
            """)

            # Step 3: Drop the old, original table.
            print("[MIGRATE] Step 3: Deleting old 'economy' table...")
            cursor.execute("DROP TABLE economy;")

            # Step 4: Rename the new table to the original name.
            print("[MIGRATE] Step 4: Renaming 'economy_new' to 'economy'...")
            cursor.execute("ALTER TABLE economy_new RENAME TO economy;")

            conn.commit()
            print("\n[MIGRATE] Successfully removed columns and rebuilt the 'economy' table!")

    except sqlite3.Error as e:
        print(f"\n[MIGRATE] An error occurred during the database operation: {e}")
        print("[MIGRATE] The database might be in an inconsistent state. Please check it manually.")

if __name__ == "__main__":
    print("This script will permanently remove the 'wins', 'losses', and 'last_daily' columns from your economy table.")
    answer = input("Are you sure you want to continue? (y/n): ")
    if answer.lower() == 'y':
        remove_columns_from_economy()
    else:
        print("Operation cancelled.")
