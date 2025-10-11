import discord
import asyncio
import os
import sys

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Function to load environment variables from a .env file
def load_dotenv(filepath=".env"):
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    except FileNotFoundError:
        print(f"Warning: .env file not found at {filepath}. This script requires it to run.")

async def main():
    """Main function to fetch and print user details."""
    # --- 1. Load Token and User ID ---
    load_dotenv()
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

    if not DISCORD_BOT_TOKEN:
        print("[ERROR] DISCORD_BOT_TOKEN not found in .env file or environment variables.")
        return

    if len(sys.argv) < 2:
        print("[ERROR] No User ID provided.")
        print("Usage: python get_user_from_id.py <USER_ID>")
        return

    try:
        user_id_to_fetch = int(sys.argv[1])
    except ValueError:
        print(f"[ERROR] Invalid User ID: '{sys.argv[1]}'. Must be a number.")
        return

    # --- 2. Connect to Discord ---
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    try:
        print("Connecting to Discord...")
        # We use login() and close() for a quick, one-off script.
        await client.login(DISCORD_BOT_TOKEN)
        
        # --- 3. Fetch the User ---
        print(f"Fetching user with ID: {user_id_to_fetch}...")
        try:
            user = await client.fetch_user(user_id_to_fetch)
            print("\n--- User Found ---")
            print(f"ID:       {user.id}")
            print(f"Username: {user.name}")
            if user.global_name:
                print(f"Display Name: {user.global_name}")
            print(f"Bot:      {user.bot}")
            print("------------------\n")

        except discord.NotFound:
            print(f"\n[ERROR] User with ID '{user_id_to_fetch}' was not found.\n")
        except discord.HTTPException as e:
            print(f"\n[ERROR] An HTTP error occurred: {e}\n")

    except discord.errors.LoginFailure:
        print("[ERROR] Login failed. Please check your DISCORD_BOT_TOKEN.")
    finally:
        if not client.is_closed():
            await client.close()
            print("Connection closed.")

if __name__ == "__main__":
    asyncio.run(main())
