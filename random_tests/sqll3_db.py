import sqlite3

# This is the recommended approach:
def initialize_db(db_path='BobekBot_sqlite3.db'):
    try:
        # 'with' statement for connection
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            print(f'Database connected to {db_path}.')

            # Example: Create a table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    points INTEGER NOT NULL DEFAULT 0
                )
            """)

            # 3. Connection is automatically committed and closed
            #    when exiting the 'with' block (unless an exception occurs)
            conn.commit()
            print("Database setup complete.")

    except sqlite3.Error as error:
        print(f'Error occurred during DB initialization: {error}')

# # Using try
# try:
#     # Connect to SQLite Database and create a cursor
#     sqliteConnection = sqlite3.connect('BobekBot_sqlite3.db')
#     cursor = sqliteConnection.cursor()
#     print('Database initialised.')
#
#     # Execute a query to get the SQLite version
#     query = 'SELECT sqlite_version();'
#     cursor.execute(query)
#
#     # Fetch and print the result
#     result = cursor.fetchall()
#     print('SQLite Version: {}'.format(result[0][0]))
#
#     # Close the cursor after use (TEMPORARY)
#     cursor.close()
#
# except sqlite3.Error as error:
#     print('Error occurred -', error)

# # handle Database with safe resource handleing using with
# with sqlite3.connect('BobekBot_sqlite3.db') as conn: # Creates a new database file if it doesn’t exist
#     cursor = conn.cursor() # Connect to the database, create and assign connection to the cursor variable

# Simple Database handleing
# conn = sqlite3.connect('BobekBot.db') # Creates a new database file if it doesn’t exist
# cursor = conn.cursor() # Connect to the database, create and assign connection to the cursor variable

# Cleanup
# finally:
#     # Ensure the database connection is closed
#     if cursor:
#         cursor.close()
#     if sqliteConnection:
#         sqliteConnection.close()
#     print('SQLite Connection closed')