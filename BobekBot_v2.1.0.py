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
            balance INTEGER NOT NULL DEFAULT 100,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            last_daily INTEGER DEFAULT 0,
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
    elif interaction.user.id == 1350499151418359901:
        await interaction.response.send_message(f"Hey baby :kissing_heart: {interaction.user.mention}", ephemeral=ephemeral)
    elif interaction.user.id in [1371270077957144707, 1406691426036617297]:
        await interaction.response.send_message(f"Hey cutie :stuck_out_tongue_winking_eye: {interaction.user.mention}", ephemeral=ephemeral)
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

@tree.command(name="owner", description="Execute a private, owner-only command.")
@app_commands.describe(
    command="The command to execute. Type 'help' for a list of commands.",
    public="Make the output visible to everyone. Default: False"
)
async def owner_command(interaction: discord.Interaction, command: str, public: bool = False):
    if interaction.user.id not in OWNER_IDS:
        log_command(interaction, {'command': command, 'public': public}, was_successful=False)
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # The visibility of the entire interaction is determined by this first response.
    await interaction.response.defer(ephemeral=not public)

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

    log_command(interaction, {'command': command, 'public': public}, was_successful=True)

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
        embed = discord.Embed(title="Your Temporary Email Address", description=f"Your new temporary email is **`{api_response.get('email_addr')}`**.", color=discord.Color.green())
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
