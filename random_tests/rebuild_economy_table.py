import sqlite3

# --- CONFIGURATION ---
# Make sure this matches the DB_FILE constant in your main bot script.
DB_FILE = "../BobekBot_sqlite3.db"

def rebuild_economy_table():
    """Drops the existing economy table and creates a new one with the updated schema."""
    print(f"[REBUILD] Connecting to database '{DB_FILE}'...")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            print("[REBUILD] Connection successful. Rebuilding 'economy' table...")

            # Step 1: Drop the old table if it exists.
            print("[REBUILD] Step 1: Dropping old 'economy' table...")
            cursor.execute("DROP TABLE IF EXISTS economy;")

            # Step 2: Create the new table with the desired final schema.
            print("[REBUILD] Step 2: Creating new 'economy' table with wallet and bank balances...")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                wallet_balance INTEGER NOT NULL DEFAULT 0,
                bank_balance INTEGER NOT NULL DEFAULT 1000,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            );
            """)

            conn.commit()
            print("\n[REBUILD] Successfully rebuilt the 'economy' table!")

    except sqlite3.Error as e:
        print(f"\n[REBUILD] An error occurred during the database operation: {e}")

if __name__ == "__main__":
    print("This script will PERMANENTLY DELETE all data in your current 'economy' table and create a new one.")
    answer = input("Are you sure you want to continue? (y/n): ")
    if answer.lower() == 'y':
        rebuild_economy_table()
    else:
        print("Operation cancelled.")
