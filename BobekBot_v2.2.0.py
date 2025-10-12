import discord
from discord import app_commands
import asyncio
import random
import os
import requests
from ai4free import PhindSearch
import time
import html
import sqlite3
import json
from datetime import datetime
import re

# ======================================================================================================================
# CONFIGURATION & CONSTANTS
# ======================================================================================================================

OWNER_IDS = []  # This will be populated in on_ready
DB_FILE = "BobekBot_sqlite3.db"

# ======================================================================================================================
# DATABASE & LOGGING SETUP
# ======================================================================================================================

def setup_database():
    """Creates the database and tables if they don't exist."""
    print("[DB] Initializing database...")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT sqlite_version();")
        print(f"[DB] SQLite Version: {cursor.fetchone()[0]}")

        # Create guilds table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            name TEXT,
            is_active INTEGER DEFAULT NULL, -- 1 for active, 0 for removed, NULL for external/unknown
            first_seen_timestamp INTEGER,
            removal_timestamp INTEGER
        );
        """)

        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            first_seen_timestamp INTEGER
        );
        """)

        # Create guild name history table
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

        # Create command_logs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            guild_id INTEGER,
            command_name TEXT NOT NULL,
            options TEXT,
            was_successful INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (guild_id) REFERENCES guilds (guild_id)
        );
        """)

        # Create economy table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS economy (
            user_id INTEGER PRIMARY KEY,
            wallet_balance INTEGER NOT NULL DEFAULT 0,
            bank_balance INTEGER NOT NULL DEFAULT 1000,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        """)
        conn.commit()
    print("[DB] Database setup complete.")

def log_command(interaction: discord.Interaction, options: dict, was_successful: bool):
    """Logs a command usage to the database and prints to console."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            current_timestamp = int(time.time())

            # Add user to DB if they don't exist, now with a timestamp
            cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_seen_timestamp) VALUES (?, ?, ?)",
                           (interaction.user.id, interaction.user.name, current_timestamp))

            guild_id = interaction.guild.id if interaction.guild else None
            db_guild_name = None
            log_guild_display = "DM"

            if guild_id:
                full_guild = client.get_guild(guild_id)
                if full_guild:
                    # Bot is a member, we know the name
                    db_guild_name = full_guild.name
                    log_guild_display = f"'{full_guild.name}' ({full_guild.id})"
                else:
                    # Bot is not a member, this is an external server
                    db_guild_name = f"[Name Unknown: {guild_id}]"
                    log_guild_display = f"[External Server: {guild_id}]"
                
                # Add guild to DB if it doesn't exist
                cursor.execute("INSERT OR IGNORE INTO guilds (guild_id, name, first_seen_timestamp) VALUES (?, ?, ?)",
                               (guild_id, db_guild_name, current_timestamp))

            # Insert the command log
            command_name = f"{interaction.command.parent.name} {interaction.command.name}" if interaction.command.parent else interaction.command.name
            log_data = (
                current_timestamp,
                interaction.user.id,
                guild_id,
                command_name,
                json.dumps(options),
                1 if was_successful else 0
            )
            cursor.execute(
                "INSERT INTO command_logs (timestamp, user_id, guild_id, command_name, options, was_successful) VALUES (?, ?, ?, ?, ?, ?)",
                log_data)
            conn.commit()

        status = "SUCCESS" if was_successful else "FAILED"
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [CMD] [{status}] User '{interaction.user.name}' ({interaction.user.id}) ran '/{command_name}' in {log_guild_display}. Options: {json.dumps(options)}")
    except Exception as e:
        print(f"[FATAL LOGGING ERROR] Failed to log command for user {interaction.user.id}: {e}")

# ======================================================================================================================
# BOT SETUP
# ======================================================================================================================

def load_dotenv(filepath=".env"):
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    except FileNotFoundError:
        print(f"Warning: .env file not found at {filepath}. Attempting to use system environment variables only.")
    except Exception as e:
        print(f"Error loading .env file: {e}")

load_dotenv()

intents = discord.Intents.default()
intents.presences = True
intents.members = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

ph = PhindSearch()
guerrilla_sessions = {}
API_URL = "http://api.guerrillamail.com/ajax.php"
USER_AGENT = "BobekBot/1.0 (DiscordBot)"

# ======================================================================================================================
# BOT EVENTS
# ======================================================================================================================

@client.event
async def on_ready():
    print("-" * 60)
    global OWNER_IDS
    setup_database()

    # --- Guild Synchronization --- 
    print("[SYSTEM] Syncing guilds with the database...")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        db_guild_ids = {row[0] for row in cursor.execute("SELECT guild_id FROM guilds").fetchall()}
        current_guild_ids = {guild.id for guild in client.guilds}

        # 1. Find guilds the bot was removed from while offline
        removed_guilds = db_guild_ids - current_guild_ids
        if removed_guilds:
            cursor.executemany("UPDATE guilds SET is_active = 0, removal_timestamp = ? WHERE guild_id = ?", [(int(time.time()), gid) for gid in removed_guilds])
            print(f"[SYSTEM] Marked {len(removed_guilds)} guild(s) as inactive (bot was removed while offline).")

        # 2. Find guilds the bot was added to while offline
        added_guilds = current_guild_ids - db_guild_ids
        if added_guilds:
            added_guild_data = [(guild.id, guild.name, 1, int(time.time())) for guild in client.guilds if guild.id in added_guilds]
            cursor.executemany("INSERT INTO guilds (guild_id, name, is_active, first_seen_timestamp) VALUES (?, ?, ?, ?)", added_guild_data)
            print(f"[SYSTEM] Detected {len(added_guilds)} new guild(s) joined while offline.")

        # 3. Update existing guilds (name might have changed, or bot was re-invited)
        existing_guilds = current_guild_ids.intersection(db_guild_ids)
        if existing_guilds:
            update_guild_data = [(guild.name, 1, None, guild.id) for guild in client.guilds if guild.id in existing_guilds] # Set removal_timestamp to NULL
            cursor.executemany("UPDATE guilds SET name = ?, is_active = ?, removal_timestamp = ? WHERE guild_id = ?", update_guild_data)
        
        conn.commit()
    print(f"[SYSTEM] Guild sync complete. Now in {len(client.guilds)} servers.")

    # --- Set Owner IDs ---
    app_info = await client.application_info()
    if app_info.team:
        OWNER_IDS = [member.id for member in app_info.team.members]
        print(f"[SYSTEM] Owner is a Team. Authorized IDs: {OWNER_IDS}")
    else:
        OWNER_IDS = [app_info.owner.id]
        print(f"[SYSTEM] Owner is a User. Authorized ID: {OWNER_IDS[0]}")

    await tree.sync()
    print("[SYSTEM] Commands synced.")

    activity = discord.Game(name="with myself")
    await client.change_presence(status=discord.Status.online, activity=activity)
    print("[SYSTEM] Bot presence set.")
    print(f" BobekBot initialised! <3 ".center(60, "."))

@client.event
async def on_guild_join(guild: discord.Guild):
    """Logs when the bot joins a new server."""
    with sqlite3.connect(DB_FILE) as conn:
        # On join, set as active, update name, and set first_seen if it's new, clear removal time
        conn.execute("INSERT INTO guilds (guild_id, name, is_active, first_seen_timestamp) VALUES (?, ?, 1, ?) ON CONFLICT(guild_id) DO UPDATE SET name=excluded.name, is_active=1, removal_timestamp=NULL", 
                     (guild.id, guild.name, int(time.time())))
        conn.commit()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [GUILD] Joined server: '{guild.name}' ({guild.id}). Now in {len(client.guilds)} servers.")

@client.event
async def on_guild_remove(guild: discord.Guild):
    """Logs when the bot is removed from a server."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE guilds SET is_active = 0, removal_timestamp = ? WHERE guild_id = ?", (int(time.time()), guild.id))
        conn.commit()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [GUILD] Removed from server: '{guild.name}' ({guild.id}). Now in {len(client.guilds)} servers.")

@client.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    """Logs when a guild's name is changed."""
    if before.name != after.name:
        with sqlite3.connect(DB_FILE) as conn:
            # Update the main guilds table with the new name
            conn.execute("UPDATE guilds SET name = ? WHERE guild_id = ?", (after.name, after.id))
            # Add a permanent record of the name change to the history table
            conn.execute("INSERT INTO guild_name_history (guild_id, old_name, new_name, change_timestamp) VALUES (?, ?, ?, ?)",
                         (after.id, before.name, after.name, int(time.time())))
            conn.commit()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [GUILD] Server '{before.name}' renamed to '{after.name}' ({after.id}).")

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Global error handler for all slash commands."""
    command_name = interaction.command.name if interaction.command else 'Unknown'
    options = {opt['name']: opt['value'] for opt in interaction.data.get('options', [])}
    log_command(interaction, options, was_successful=False)
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] Unhandled error in command '/{command_name}': {error}")
    
    error_message = "An unexpected error occurred. The developers have been notified."
    if isinstance(error, app_commands.CommandOnCooldown):
        error_message = f"This command is on cooldown. Please try again in {error.retry_after:.2f} seconds."
    elif isinstance(error, app_commands.MissingPermissions):
        error_message = "You don't have the required permissions to run this command."

    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(error_message, ephemeral=True)
        else:
            await interaction.followup.send(error_message, ephemeral=True)
    except discord.errors.InteractionResponded:
        pass # If we already responded in the command's own error handling, that's fine.
    except Exception as e:
        print(f"[ERROR] Failed to send error message to user: {e}")

# ======================================================================================================================
# EconomyManager Class
# ======================================================================================================================

class EconomyManager():
    """Class for global EconomyManager"""

    @staticmethod
    def get_balance(user_id: int):
        """Get and return wallet and bank balance for specified user, if not in DB we add."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                current_timestamp = int(time.time())

                # Add user to DB if they don't exist, with default DB values.
                cursor.execute("INSERT OR IGNORE INTO economy (user_id) VALUES (?)", (user_id,))

                # Check if a new row was actually inserted.
                # cursor.rowcount will be 1 if the user was new, and 0 if they already existed.
                if cursor.rowcount > 0:
                    print(f"[Economy] New user created: {user_id}. Giving default balance.")
                    # The database already set the default values, so we don't need to do anything else here.
                    # We can now commit this new user to the database.
                    conn.commit()

                # Now, select the balances. This is guaranteed to find a row.
                cursor.execute("SELECT wallet_balance, bank_balance FROM economy WHERE user_id = ?", (user_id,))
                balances = cursor.fetchone()

                # Return balances for user.
                if balances:
                    return balances # Returns (wallet_balance, bank_balance)
                else:
                    # This is a fallback case, it should ideally never be reached.
                    print(f"[FATAL EconomyManager.get_balance ERROR] Could not fetch balance for user {user_id} after get-or-create.")
                    return (0, 0) # Return a safe default on error

        except Exception as e:
            print(f"[FATAL EconomyManager.get_balance ERROR] Failed to connect to Database for {user_id}: {e}")
            return (0, 0) # Return a safe default on error

    @staticmethod
    def update_wallet_balance(user_id: int, amount: int):
        """
        Adds or subtracts a specified amount from a user's wallet balance.
        The amount can be positive (to add) or negative (to subtract).

        Args:
            user_id: The Discord ID of the user.
            amount: The amount of money to add or subtract.

        Returns:
            True if the update was successful, False otherwise.
        """
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()

                current_wallet, _ = EconomyManager.get_balance(user_id)
                if current_wallet is None: # This would mean a DB error happened in get_balance
                    return False

                new_wallet = current_wallet + amount

                cursor.execute("UPDATE economy SET wallet_balance = ? WHERE user_id = ?",
                               (new_wallet, user_id))
                conn.commit()

                print(f"[Economy] Updated user {user_id} wallet by {amount}. New balance: ...")
                return True

        except sqlite3.Error as e:
            print(f"[FATAL EconomyManager.update_wallet_balance ERROR] Database error for user {user_id}: {e}")
            return False

    @staticmethod
    def deposit(user_id: int, amount: int):
        """
        Deposits a specified amount from a user's wallet into their bank.

        Args:
            user_id: The Discord ID of the user.
            amount: The amount of money to deposit.

        Returns:
            A string indicating the status: "success", "insufficient_funds", "invalid_amount", or "db_error".
        """
        # 1. Input Validation: Ensure the amount is a positive number.
        if amount <= 0:
            return "invalid_amount"

        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()

                # 2. Get current balance and ensure the user exists.
                # We don't need a separate check; get_balance handles user creation.
                wallet_balance, bank_balance = EconomyManager.get_balance(user_id)

                # 3. Check for sufficient funds in the wallet.
                if amount > wallet_balance:
                    return "insufficient_funds"

                # 4. Perform the atomic transaction: subtract from wallet, add to bank.
                new_wallet = wallet_balance - amount
                new_bank = bank_balance + amount
                cursor.execute("UPDATE economy SET wallet_balance = ?, bank_balance = ? WHERE user_id = ?",
                               (new_wallet, new_bank, user_id))
                conn.commit()

                print(f"[Economy] User {user_id} deposited {amount}. New balance: Wallet={new_wallet}, Bank={new_bank}")
                return "success"

        except sqlite3.Error as e:
            print(f"[FATAL EconomyManager.deposit ERROR] Database error for user {user_id}: {e}")
            return "db_error"

    @staticmethod
    def withdraw(user_id: int, amount: int):
        """
        Withdraws a specified amount from a user's bank into their wallet.

        Args:
            user_id: The Discord ID of the user.
            amount: The amount of money to withdraw.

        Returns:
            A string indicating the status: "success", "insufficient_funds", "invalid_amount", or "db_error".
        """
        # 1. Input Validation: Ensure the amount is a positive number.
        if amount <= 0:
            return "invalid_amount"

        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()

                # 2. Get current balance and ensure the user exists.
                wallet_balance, bank_balance = EconomyManager.get_balance(user_id)

                # 3. Check for sufficient funds in the bank.
                if amount > bank_balance:
                    return "insufficient_funds"

                # 4. Perform the atomic transaction: add to wallet, subtract from bank.
                new_wallet = wallet_balance + amount
                new_bank = bank_balance - amount
                cursor.execute("UPDATE economy SET wallet_balance = ?, bank_balance = ? WHERE user_id = ?",
                               (new_wallet, new_bank, user_id))
                conn.commit()

                print(f"[Economy] User {user_id} withdrew {amount}. New balance: Wallet={new_wallet}, Bank={new_bank}")
                return "success"

        except sqlite3.Error as e:
            print(f"[FATAL EconomyManager.withdraw ERROR] Database error for user {user_id}: {e}")
            return "db_error"

    @staticmethod
    def send(sender_user_id: int, receiver_user_id: int, amount: int):
        """
        Transfers a specified amount from a user's wallet into another user's wallet.

        Args:
            sender_user_id: The Discord ID of the sending user.
            receiver_user_id: The Discord ID of the receiving user.
            amount: The amount of money to send.

        Returns:
            A string indicating the status: "success", "insufficient_funds", "invalid_amount", "self_transfer", or "db_error".
        """
        # 1. Input Validation
        if amount <= 0:
            return "invalid_amount"
        if sender_user_id == receiver_user_id:
            return "self_transfer"

        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()

                # 2. Get sender's balance and check for sufficient funds
                sender_wallet, _ = EconomyManager.get_balance(sender_user_id)
                if sender_wallet is None:
                    return "db_error"  # Sender couldn't be fetched/created
                if amount > sender_wallet:
                    return "insufficient_funds"

                # 3. Ensure receiver exists in the database (get_balance creates them if new)
                receiver_wallet, _ = EconomyManager.get_balance(receiver_user_id)
                if receiver_wallet is None:
                    return "db_error"  # Receiver couldn't be fetched/created

                # 4. Perform the atomic transaction
                # Subtract from sender
                new_sender_wallet = sender_wallet - amount
                cursor.execute("UPDATE economy SET wallet_balance = ? WHERE user_id = ?",
                               (new_sender_wallet, sender_user_id))

                # Add to receiver
                new_receiver_wallet = receiver_wallet + amount
                cursor.execute("UPDATE economy SET wallet_balance = ? WHERE user_id = ?",
                               (new_receiver_wallet, receiver_user_id))

                conn.commit()

                print(f"[Economy] User {sender_user_id} sent {amount} to {receiver_user_id}.")
                return "success"

        except sqlite3.Error as e:
            print(f"[FATAL EconomyManager.send ERROR] Database error between {sender_user_id} and {receiver_user_id}: {e}")
            return "db_error"

# ======================================================================================================================
# COMMANDS
# ======================================================================================================================

@tree.command(name="hello", description="Says hello to you!")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def hello_command(interaction: discord.Interaction, ephemeral: bool = False):
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!", ephemeral=ephemeral)
    log_command(interaction, {'ephemeral': ephemeral}, was_successful=True)

@tree.command(name="greet", description="Greets you back!")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def greet_command(interaction: discord.Interaction, ephemeral: bool = False):
    greet_command_greetings = (" nigger", " faggot", " retard", "")
    if interaction.user.id in OWNER_IDS:
        await interaction.response.send_message(f"Hey Bobek <3 {interaction.user.mention}!", ephemeral=ephemeral)
    elif interaction.user.id == 1350499151418359901: # For Roadbobek
        await interaction.response.send_message(f"Hey baby :kissing_heart: {interaction.user.mention}", ephemeral=ephemeral)
    elif interaction.user.id in [1371270077957144707, 1406691426036617297]: # For Chrome / extinc
        await interaction.response.send_message(f"Hey cutie :stuck_out_tongue_winking_eye: {interaction.user.mention}", ephemeral=ephemeral)
    elif interaction.user.id == 1261168774967726158: # For player
        await interaction.response.send_message(f"Hey buddy <: {interaction.user.mention}!", ephemeral=ephemeral)
    else:
        await interaction.response.send_message(f"Fuck you{random.choice(greet_command_greetings)}! {interaction.user.mention}", ephemeral=ephemeral)
    log_command(interaction, {'ephemeral': ephemeral}, was_successful=True)

@tree.command(name="ip-info", description="Get information about an IP address.")
@discord.app_commands.describe(ip_address="The IP address to look up (e.g., 8.8.8.8)")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def ip_info_command(interaction: discord.Interaction, ip_address: str, ephemeral: bool = False):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        response = requests.get(f"http://ip-api.com/json/{ip_address}")
        response.raise_for_status()
        ip_api = response.json()
        if ip_api.get('status') == "success":
            embed = discord.Embed(title=f"IP Lookup Results for {ip_api.get('query', 'N/A')}", color=discord.Color.blue())
            embed.add_field(name="Status", value=f":white_check_mark: {ip_api.get('status', 'N/A').capitalize()}", inline=False)
            embed.add_field(name="Country", value=f"{ip_api.get('country', 'N/A')} ({ip_api.get('countryCode', 'N/A')})", inline=True)
            embed.add_field(name="Region", value=f"{ip_api.get('regionName', 'N/A')} ({ip_api.get('region', 'N/A')})", inline=True)
            embed.add_field(name="City", value=f"{ip_api.get('city', 'N/A')}", inline=True)
            embed.add_field(name="ZIP Code", value=f"{ip_api.get('zip', 'N/A')}", inline=True)
            embed.add_field(name="Coordinates", value=f"Lat: {ip_api.get('lat', 'N/A')}, Lon: {ip_api.get('lon', 'N/A')}", inline=True)
            embed.add_field(name="Timezone", value=f"{ip_api.get('timezone', 'N/A')}", inline=True)
            embed.add_field(name="ISP", value=f"{ip_api.get('isp', 'N/A')}", inline=False)
            embed.add_field(name="Organization", value=f"{ip_api.get('org', 'N/A')}", inline=False)
            embed.add_field(name="AS", value=f"{ip_api.get('as', 'N/A')}", inline=False)
            embed.set_footer(text="Powered by BobekBot <3")
            await interaction.followup.send(embed=embed)
            log_command(interaction, {'ip_address': ip_address, 'ephemeral': ephemeral}, was_successful=True)
        else:
            await interaction.followup.send(f"API Error: Could not find information for the IP address `{ip_address}`. Reason: {ip_api.get('message')}")
    except requests.exceptions.RequestException:
        await interaction.followup.send(f"Error: An error occurred while trying to contact the IP lookup service.")

@tree.command(name="ask-ai", description="Ask a question to the AI.")
@discord.app_commands.describe(prompt="The question you want to ask the AI.")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def ask_ai_command(interaction: discord.Interaction, prompt: str, ephemeral: bool = False):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        full_prompt = f"You are acting as a Chat Bot for the Discord bot BobekBot you are made by Roadbobek, here is the users prompt: {prompt}"
        response = await asyncio.to_thread(ph.chat, full_prompt)
        await interaction.followup.send(f"**Your Question:**\n> {prompt}\n\n**AI's Answer:**\n{response}")
        log_command(interaction, {'prompt': prompt, 'ephemeral': ephemeral}, was_successful=True)
    except Exception as e:
        await interaction.followup.send("Sorry, I encountered an error while trying to answer your question.")

@tree.command(name="balance", description="Check a persons balance.")
@app_commands.describe(user="Person to check balance for.")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def balance_command(interaction: discord.Interaction, user: discord.Member = None, ephemeral: bool = False):
    await interaction.response.defer(ephemeral=ephemeral)
    if user:
        target_user = user
    else:
        target_user = interaction.user
    user_display_name = target_user.display_name
    user_avatar = target_user.display_avatar
    try:
        balances = EconomyManager.get_balance(target_user.id)
        embed = discord.Embed(title=f"Balances for {user_display_name}", color=discord.Color.green())
        embed.set_author(name=user_display_name, icon_url=user_avatar)
        embed.add_field(name=":dollar: Wallet", value=f"**${balances[0]:,}**", inline=True)
        embed.add_field(name=":bank: Bank", value=f"**${balances[1]:,}**", inline=True)
        embed.set_footer(text=f"Total: ${balances[0] + balances[1]:,}")
        await interaction.followup.send(embed=embed)
        log_command(interaction, {'user': user, 'ephemeral': ephemeral}, was_successful=True)
    except Exception as e:
        await interaction.followup.send(f"An unknown error occurred, {e}.", ephemeral=True)
        print(f"[ERROR] Unknown error in /balance: ({e}).")

@tree.command(name="deposit", description="Deposit money from your wallet into your bank.")
@app_commands.describe(amount="The amount to deposit. Use 'all' to deposit everything.")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def deposit_command(interaction: discord.Interaction, amount: str, ephemeral: bool = False):
    user_id = interaction.user.id
    wallet_balance, _ = EconomyManager.get_balance(user_id)

    if wallet_balance is None:
        await interaction.response.send_message(":cross_mark: Could not fetch your balance due to a database error.", ephemeral=True)
        log_command(interaction, {'amount': amount}, was_successful=False)
        return

    try:
        if amount.lower() == 'all':
            deposit_amount = wallet_balance
        else:
            deposit_amount = int(amount)
    except ValueError:
        await interaction.response.send_message("Please enter a valid number or 'all'.", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=False)
        return

    if deposit_amount <= 0:
        await interaction.response.send_message("You have nothing to deposit.", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=False)
        return

    status = EconomyManager.deposit(user_id, deposit_amount)

    if status == "success":
        await interaction.response.send_message(f":white_check_mark: Successfully deposited **${deposit_amount:,}** into your bank!", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=True)
    elif status == "insufficient_funds":
        await interaction.response.send_message(":cross_mark: You don't have that much money in your wallet to deposit.", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=False)
    else: # db_error or invalid_amount
        await interaction.response.send_message("An error occurred. Please enter a valid positive amount.", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=False)

@tree.command(name="withdraw", description="Withdraw money from your bank into your wallet.")
@app_commands.describe(amount="The amount to withdraw. Use 'all' to withdraw everything.")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def withdraw_command(interaction: discord.Interaction, amount: str, ephemeral: bool = False):
    user_id = interaction.user.id
    _, bank_balance = EconomyManager.get_balance(user_id)

    if bank_balance is None:
        await interaction.response.send_message(":cross_mark: Could not fetch your balance due to a database error.", ephemeral=True)
        log_command(interaction, {'amount': amount}, was_successful=False)
        return

    try:
        if amount.lower() == 'all':
            withdraw_amount = bank_balance
        else:
            withdraw_amount = int(amount)
    except ValueError:
        await interaction.response.send_message("Please enter a valid number or 'all'.", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=False)
        return

    if withdraw_amount <= 0:
        await interaction.response.send_message("You have nothing to withdraw.", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=False)
        return

    status = EconomyManager.withdraw(user_id, withdraw_amount)

    if status == "success":
        await interaction.response.send_message(f":white_check_mark: Successfully withdrew **${withdraw_amount:,}** from your bank!", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=True)
    elif status == "insufficient_funds":
        await interaction.response.send_message(":cross_mark: You don't have that much money in your bank to withdraw.", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=False)
    else: # db_error or invalid_amount
        await interaction.response.send_message("An error occurred. Please enter a valid positive amount.", ephemeral=ephemeral)
        log_command(interaction, {'amount': amount}, was_successful=False)

@tree.command(name="send", description="Send money from your wallet to another user.")
@app_commands.describe(
    receiver="The user you want to send money to.",
    amount="The amount of money to send.",
    ephemeral="Hide message and response from others."
)
async def send_command(interaction: discord.Interaction, receiver: discord.User, amount: int, ephemeral: bool = False):
    sender = interaction.user
    log_options = {'receiver': str(receiver), 'amount': amount}

    # Prevent sending money to bots
    if receiver.bot:
        await interaction.response.send_message("You cannot send money to a bot.", ephemeral=False)
        log_command(interaction, log_options, was_successful=False)
        return

    status = EconomyManager.send(sender.id, receiver.id, amount)

    if status == "success":
        await interaction.response.send_message(f":white_check_mark: You successfully sent **${amount:,}** to {receiver.mention}!")
        log_command(interaction, log_options, was_successful=True)
    elif status == "insufficient_funds":
        await interaction.response.send_message(":cross_mark: You don't have enough money in your wallet to send that amount.", ephemeral=ephemeral)
        log_command(interaction, log_options, was_successful=False)
    elif status == "invalid_amount":
        await interaction.response.send_message(":cross_mark: Please enter a positive amount to send.", ephemeral=ephemeral)
        log_command(interaction, log_options, was_successful=False)
    elif status == "self_transfer":
        await interaction.response.send_message(":cross_mark: You cannot send money to yourself.", ephemeral=ephemeral)
        log_command(interaction, log_options, was_successful=False)
    else:  # db_error
        await interaction.response.send_message("A database error occurred. Please try again later.", ephemeral=ephemeral)
        log_command(interaction, log_options, was_successful=False)

# @tree.command(name="singleplayer-coinflip", description="Singleplayer coinflip gambling.")
# @app_commands.describe(amount="Amount to gamble.")
# @app_commands.describe(ephemeral="Hide message and response from others.")
# async def sp_coinflip_command(interaction: discord.Interaction, amount: int, ephemeral: bool = False):
#     await interaction.response.defer(ephemeral=ephemeral)
#     try:
#         balances = EconomyManager.get_balance(interaction.user.id)
#         embed = discord.Embed(title=f"Gambling {} {user_display_name}", color=discord.Color.green())
#         embed.add_field(name=":dollar: Wallet", value=f"${balances[0]}", inline=True)
#         embed.add_field(name=":bank: Bank", value=f"${balances[1]}", inline=True)
#         await interaction.followup.send(embed=embed)
#         log_command(interaction, {'amount': amount, 'ephemeral': ephemeral}, was_successful=True)
#     except Exception as e:
#         await interaction.response.send_message(f"An unknown error occurred, {e}.", ephemeral=True)

@tree.command(name="owner", description="Execute a private, owner-only command.")
@app_commands.describe(
    command="The command to execute. Type 'help' for a list of commands.",
    ephemeral="Hide message and response from others."
)
async def owner_command(interaction: discord.Interaction, command: str, ephemeral: bool = False):
    if interaction.user.id not in OWNER_IDS:
        log_command(interaction, {'command': command, 'ephemeral': ephemeral}, was_successful=False)
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # The visibility of the entire interaction is determined by this first response.
    await interaction.response.defer(ephemeral=ephemeral)

    # --- Argument Parser ---
    parts = command.strip().split()
    subcommand = parts[0].lower() if parts else ''
    positional_args = []
    keyword_args = {}
    for part in parts[1:]:
        if '=' in part:
            try:
                key, value = part.split('=', 1)
                keyword_args[key.lower()] = value
            except ValueError:
                positional_args.append(part)
        else:
            positional_args.append(part)

    log_command(interaction, {'command': command, 'ephemeral': ephemeral}, was_successful=True)

    # --- Subcommand Router ---
    if subcommand == 'help':
        embed = discord.Embed(title="Owner Command Help", description="Here are the available private commands:", color=discord.Color.gold())
        embed.add_field(name="`help`", value="Shows this help message.", inline=False)
        embed.add_field(name="`shutdown`", value="Shuts down the bot safely.", inline=False)
        embed.add_field(name="`repeat <text> [times=1]`", value="Repeats the text you provide. `times` is an optional integer.", inline=False)
        embed.set_footer(text="Syntax: <command> [positional_args] [keyword=value]")
        await interaction.followup.send(embed=embed)

    elif subcommand == 'shutdown':
        await interaction.followup.send("Bot is shutting down.")
        await client.close()

    elif subcommand == 'repeat':
        if not positional_args:
            await interaction.followup.send("Error: You must provide text to repeat.", ephemeral=True)
            return

        text_to_repeat = ' '.join(positional_args)
        try:
            repeat_count = int(keyword_args.get('times', 1))
        except (ValueError, TypeError):
            repeat_count = 1
        
        repeat_count = min(repeat_count, 10) # Prevent abuse

        final_message = '\n'.join([text_to_repeat] * repeat_count)
        await interaction.followup.send(final_message)

    else:
        await interaction.followup.send(f"Error: Unknown owner command '{subcommand}'. Type 'help' for a list.", ephemeral=True)

# --- TempMail Command Group ---
class TempMailGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="tempmail", description="Manage a temporary email address.")

    def make_api_call(self, session, function_name, params=None):
        if params is None: params = {}
        params.update({'f': function_name, 'ip': '127.0.0.1', 'agent': USER_AGENT})
        response = session.get(API_URL, params=params)
        response.raise_for_status()
        return response.json()

    @app_commands.command(name="get", description="Get a new temporary email address.")
    @app_commands.describe(ephemeral="Hide message and response from others.")
    async def get(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        session = requests.Session()
        loop = asyncio.get_running_loop()
        api_response = await loop.run_in_executor(None, self.make_api_call, session, "get_email_address")
        guerrilla_sessions[interaction.user.id] = session
        embed = discord.Embed(title="Your Temporary Email Address", description=f"Your new temporary email is **`{api_response.get('email_addr')}`**.", color=discord.Color.blue())
        embed.add_field(name="Expires", value=f"<t:{int(api_response.get('email_timestamp')) + 3600}:R>", inline=False)
        embed.set_footer(text="Use /tempmail check to see your inbox.")
        await interaction.followup.send(embed=embed)
        log_command(interaction, {'ephemeral': ephemeral}, was_successful=True)

    @app_commands.command(name="check", description="Shows all emails in your temporary inbox.")
    @app_commands.describe(ephemeral="Hide message and response from others.")
    async def check(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        session = guerrilla_sessions.get(interaction.user.id)
        if not session:
            await interaction.followup.send("You don't have an active temporary email. Use `/tempmail get` to create one first.")
            return
        loop = asyncio.get_running_loop()
        api_response = await loop.run_in_executor(None, self.make_api_call, session, "get_email_list", {'offset': 0})
        email_list = api_response.get('list', [])
        if not email_list:
            embed = discord.Embed(title="Your Inbox is Empty", description="There are no emails in your inbox.", color=discord.Color.blue())
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title="Your Inbox", description=f"Showing the first {len(email_list)} emails in your inbox.", color=discord.Color.blue())
            for email in email_list:
                subject = html.unescape(email.get('mail_subject', 'No Subject'))
                excerpt = html.unescape(email.get('mail_excerpt', '...'))
                embed.add_field(name=f"ID: {email['mail_id']} | From: {email['mail_from']}", value=f"**{subject}**\n> {excerpt}", inline=False)
            embed.set_footer(text="Use /tempmail read <email_id> to read a full email.")
            await interaction.followup.send(embed=embed)
        log_command(interaction, {'ephemeral': ephemeral}, was_successful=True)

    @app_commands.command(name="read", description="Read a specific email from your inbox.")
    @app_commands.describe(email_id="The ID of the email you want to read.")
    @app_commands.describe(ephemeral="Hide message and response from others.")
    async def read(self, interaction: discord.Interaction, email_id: str, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        session = guerrilla_sessions.get(interaction.user.id)
        if not session:
            await interaction.followup.send("You don't have an active temporary email. Use `/tempmail get` to create one first.")
            return
        loop = asyncio.get_running_loop()
        api_response = await loop.run_in_executor(None, self.make_api_call, session, "fetch_email", {'email_id': email_id})
        from_addr = html.unescape(api_response.get('mail_from', 'N/A'))
        subject = html.unescape(api_response.get('mail_subject', 'No Subject'))
        body = api_response.get('mail_body', 'No Content')
        clean_body = re.sub('<[^<]+?>', '', body)
        embed = discord.Embed(title=f"Subject: {subject}", description=f"**From:** {from_addr}", color=discord.Color.orange())
        embed.add_field(name="Body", value=clean_body[:1024], inline=False)
        await interaction.followup.send(embed=embed)
        log_command(interaction, {'email_id': email_id, 'ephemeral': ephemeral}, was_successful=True)

tree.add_command(TempMailGroup())

# ======================================================================================================================
# MAIN RUN
# ======================================================================================================================

async def main():
    """The main entry point for the bot, with graceful shutdown handling."""
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if DISCORD_BOT_TOKEN is None:
        print("[FATAL] Error: DISCORD_BOT_TOKEN environment variable not set.")
        return

    async with client:
        try:
            await client.start(DISCORD_BOT_TOKEN)
        except discord.errors.LoginFailure:
            print("[FATAL] LOGIN FAILED: The provided token is invalid.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[SYSTEM] Shutdown forced by KeyboardInterrupt. Exiting cleanly.")

# ======================================================================================================================
