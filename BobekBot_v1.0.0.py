import discord
from discord import app_commands
# from discord.ext import commands
import asyncio
import random
import os # for env vars
import requests # for /ip-info
from ai4free import PhindSearch # for /ask-ai
import time
import html
import sqlite3

# ======================================================================================================================

OWNER_IDS = [] # Defined in code

# ======================================================================================================================

# Load secrets from environmental variables (.env file)

# Function to load environment variables from a .env file
def load_dotenv(filepath=".env"):
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'): # Ignore empty lines and comments
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    except FileNotFoundError:
        print(f"Warning: .env file not found at {filepath}. Attempting to use system environment variables only.")
    except Exception as e:
        print(f"Error loading .env file: {e}")

# Load environment variables from .env file first
load_dotenv()

# ======================================================================================================================

# This is the recommended approach for handling an sqlite3 database
# Function to initialise our database.
def initialise_db(db_path='BobekBot_sqlite3.db'):
    try:
        # 'with' statement for connection
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            print(f'Database connected to {db_path}')

            # Execute a query to get the SQLite version
            query = 'SELECT sqlite_version();'
            cursor.execute(query)
            # Fetch and print the result
            result = cursor.fetchall()
            print('SQLite Version: {}'.format(result[0][0]))

            # Example: Create a table if it doesn't exist
            # cursor.execute("""
            #     CREATE TABLE IF NOT EXISTS users (
            #         user_id INTEGER PRIMARY KEY,
            #         points INTEGER NOT NULL DEFAULT 0
            #     )
            # """)

            # Connection is automatically committed and closed
            # when exiting the 'with' block (unless an exception occurs)
            conn.commit()
            print("Database setup complete.")

    except sqlite3.Error as error:
        print(f'Error occurred during Database initialization: {error}')


# Cleanup
# finally:
#     # Ensure the database connection is closed
#     if cursor:
#         cursor.close()
#     if sqliteConnection:
#         sqliteConnection.close()
#     print('SQLite Connection closed')

# ======================================================================================================================

# 1. SETUP: Define the bot and its intents

# Intents are permissions.
intents = discord.Intents.default()
intents.presences = True # This gets the "Online" status
intents.members = True # This gets the bot onto the member list
client = discord.Client(intents=intents)

# An app_commands.CommandTree is the object that holds all your slash commands
tree = discord.app_commands.CommandTree(client)

# ======================================================================================================================

# 2. THE COMMAND: Define a slash command
# The decorator registers the command with Discord.
# - name: The name of the command users will type (e.g., /hello)
# - description: The help text shown in the command list
@tree.command(name="hello", description="Says hello to you!")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def hello_command(interaction: discord.Interaction, ephemeral: bool = False):
    """
    This is the function that runs when the /hello command is used.
    """
    # '''interaction''' is a crucial object. It represents the slash command
    # invocation and contains all the information about it, like the user
    # who ran it, the channel it was run in, and any arguments.

    # We use interaction.response.send_message() to reply.
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!", ephemeral=ephemeral) # We can use ephemeral=True to make it only visible to user

# ----------------------------------------------------------------------------------------------------------------------

@tree.command(name="greet", description="Greets you back!")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def greet_command(interaction: discord.Interaction, ephemeral: bool = False):
    """
    This is the function that runs when the /greet command is used.
    """

    greet_command_greetings = (" nigger", " faggot", " retard", "")

    if interaction.user.id in OWNER_IDS: # For bot owner and team members
        await interaction.response.send_message(f"Hey Bobek <3 {interaction.user.mention}!", ephemeral=ephemeral)
    elif interaction.user.id == 1350499151418359901: # For user (1350499151418359901), (The Fentanyl Consumer)
        await interaction.response.send_message(f"Hey baby :kissing_heart: {interaction.user.mention}", ephemeral=ephemeral)
    elif interaction.user.id == 1371270077957144707 or interaction.user.id == 1406691426036617297: # For user (1371270077957144707) and 1406691426036617297, (Chrome) and (extinct (Chrome))
        await interaction.response.send_message(f"Hey cutie :stuck_out_tongue_winking_eye: {interaction.user.mention}", ephemeral=ephemeral)
    else: # Regular users
        await interaction.response.send_message(f"Fuck you{random.choice(greet_command_greetings)}! {interaction.user.mention}", ephemeral=ephemeral)

# ----------------------------------------------------------------------------------------------------------------------

@tree.command(name="ip-info", description="Get information about an IP address.")
@discord.app_commands.describe(ip_address="The IP address to look up (e.g., 8.8.8.8)")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def ip_info_command(interaction: discord.Interaction, ip_address: str, ephemeral: bool = False):
    """
    This is the function that runs when the /ip-info command is used.
    """
    # Defer the response first, as the API call might take a moment.
    # This tells Discord "I'm working on it!" and prevents a timeout.
    await interaction.response.defer(ephemeral=ephemeral)

    try:
        # Make the request to the IP API
        response = requests.get(f"http://ip-api.com/json/{ip_address}")
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        ip_api = response.json()

        # Check if the API call was successful
        if ip_api.get('status') == "success":
            # Create a nice embed to display the information
            embed = discord.Embed(
                title=f"IP Lookup Results for {ip_api.get('query', 'N/A')}",
                color=discord.Color.blue()
            )
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

            # Send the embed as a follow-up to the deferred response
            await interaction.followup.send(embed=embed)
        else:
            # If the API reports a failure (e.g., invalid IP)
            await interaction.followup.send(f"API Error: Could not find information for the IP address `{ip_address}`. Reason: {ip_api.get('message')}")

    except requests.exceptions.RequestException as e:
        # Handle network-related errors
        await interaction.followup.send(f"Error: An error occurred while trying to contact the IP lookup service. Please try again later.")
    except Exception as e:
        # Handle any other unexpected errors
        await interaction.followup.send(f"An unexpected error occurred: {e}")

# ----------------------------------------------------------------------------------------------------------------------

# Create a single, reusable instance of the AI client.
# This is more efficient than creating a new one for every command.
ph = PhindSearch()

@tree.command(name="ask-ai", description="Ask a question to the AI.")
@discord.app_commands.describe(prompt="The question you want to ask the AI.")
@app_commands.describe(ephemeral="Hide message and response from others.")
async def ask_ai_command(interaction: discord.Interaction, prompt: str, ephemeral: bool = False):
    """
    This function runs when the /ask-ai command is used.
    """
    # 1. Defer the response.
    # This is crucial. It tells Discord "I'm working on it!" and gives you
    # a 15-minute window to respond, preventing a timeout error.
    await interaction.response.defer(ephemeral = ephemeral)

    try:
        # 2. Run the blocking AI function in a separate thread.
        # The ph.chat() function is likely "blocking" (synchronous). If you
        # just `await` it directly, it will freeze your entire bot.
        # `asyncio.to_thread` runs it in the background so the bot stays responsive.
        full_prompt = f"You are acting as a Chat Bot for the Discord bot BobekBot you are made by Roadbobek, here is the users prompt: {prompt}"

        response = await asyncio.to_thread(ph.chat, full_prompt)

        # 3. Send the AI's response as a follow-up message.
        # Since we deferred, we must use `followup.send`.
        await interaction.followup.send(f"**Your Question:**\n> {prompt}\n\n**AI's Answer:**\n{response}")

    except Exception as e:
        # 4. Handle any errors that might occur during the AI call.
        print(f"An error occurred in the AI command: {e}")
        await interaction.followup.send(
            "Sorry, I encountered an error while trying to answer your question. Please try again later.")

# ----------------------------------------------------------------------------------------------------------------------

# This dictionary will store session objects for each user.
# Key: discord.user.id, Value: requests.Session()
guerrilla_sessions = {}
API_URL = "http://api.guerrillamail.com/ajax.php"
USER_AGENT = "BobekBot/1.0 (DiscordBot)"

# Helper function to make API calls, managing sessions and required parameters
def make_api_call(session, function_name, params=None):
    if params is None:
        params = {}

    # Add required parameters for every request
    params['f'] = function_name
    params['ip'] = '127.0.0.1'  # The API requires an IP, we use a placeholder
    params['agent'] = USER_AGENT

    # The requests.Session object automatically handles the PHPSESSID cookie
    response = session.get(API_URL, params=params)
    response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)
    return response.json()


# --- Command Group Definition ---
# This creates the main `/tempmail` command group
class TempMailGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="tempmail", description="Manage a temporary email address.")


    # --- /tempmail get ---
    @app_commands.command(name="get", description="Get a new temporary email address.")
    @app_commands.describe(ephemeral="Hide message and response from others.")
    async def get(self, interaction: discord.Interaction, ephemeral: bool = False):
        """Initializes a session and gets a new temp email address."""
        await interaction.response.defer(ephemeral=ephemeral)

        try:
            # Create a new session for the user
            session = requests.Session()

            # Run the blocking API call in a background thread
            loop = asyncio.get_running_loop()
            api_response = await loop.run_in_executor(
                None, make_api_call, session, "get_email_address"
            )

            # Store the session for future commands
            guerrilla_sessions[interaction.user.id] = session

            email_addr = api_response.get('email_addr')
            timestamp = api_response.get('email_timestamp')

            embed = discord.Embed(
                title="Your Temporary Email Address",
                description=f"Your new temporary email is **`{email_addr}`**.",
                color=discord.Color.green()
            )
            embed.add_field(name="Expires", value=f"<t:{int(timestamp) + 3600}:R>", inline=False)
            embed.set_footer(text="Use /tempmail check to see your inbox.")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Error in /tempmail get: {e}")
            await interaction.followup.send(
                "Could not fetch a temporary email. The API might be down. Please try again later.")

    # --- /tempmail check ---
    @app_commands.command(name="check", description="Shows all emails in your temporary inbox.")
    @app_commands.describe(ephemeral="Hide message and response from others.")
    async def check(self, interaction: discord.Interaction, ephemeral: bool = False):
        """Shows all emails in the inbox for the user's current temp email."""
        await interaction.response.defer(ephemeral=ephemeral)

        session = guerrilla_sessions.get(interaction.user.id)
        if not session:
            await interaction.followup.send(
                "You don't have an active temporary email. Use `/tempmail get` to create one first.")
            return

        try:
            loop = asyncio.get_running_loop()
            # Use get_email_list with an offset of 0 to get all emails from the beginning
            api_response = await loop.run_in_executor(
                None, make_api_call, session, "get_email_list", {'offset': 0}
            )

            email_list = api_response.get('list', [])

            if not email_list:
                embed = discord.Embed(
                    title="Your Inbox is Empty",
                    description="There are no emails in your inbox.",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed)
                return

            embed = discord.Embed(
                title="Your Inbox",
                description=f"Showing the first {len(email_list)} emails in your inbox.",
                color=discord.Color.blue()
            )

            for email in email_list:
                # The API HTML-escapes content, so we unescape it
                subject = html.unescape(email.get('mail_subject', 'No Subject'))
                excerpt = html.unescape(email.get('mail_excerpt', '...'))
                embed.add_field(
                    name=f"ID: {email['mail_id']} | From: {email['mail_from']}",
                    value=f"**{subject}**\n> {excerpt}",
                    inline=False
                )
            embed.set_footer(text="Use /tempmail read <email_id> to read a full email.")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Error in /tempmail check: {e}")
            await interaction.followup.send("Could not check your inbox. Please try again.")

    # --- /tempmail read ---
    @app_commands.command(name="read", description="Read a specific email from your inbox.")
    @app_commands.describe(email_id="The ID of the email you want to read.")
    @app_commands.describe(ephemeral="Hide message and response from others.")
    async def read(self, interaction: discord.Interaction, email_id: str, ephemeral: bool = False):
        """Fetches and displays a full email by its ID."""
        await interaction.response.defer(ephemeral=ephemeral)

        session = guerrilla_sessions.get(interaction.user.id)
        if not session:
            await interaction.followup.send(
                "You don't have an active temporary email. Use `/tempmail get` to create one first.")
            return

        try:
            loop = asyncio.get_running_loop()
            api_response = await loop.run_in_executor(
                None, make_api_call, session, "fetch_email", {'email_id': email_id}
            )

            # The API returns HTML, we need to show it cleanly
            from_addr = html.unescape(api_response.get('mail_from', 'N/A'))
            subject = html.unescape(api_response.get('mail_subject', 'No Subject'))
            body = api_response.get('mail_body', 'No Content')

            # For Discord, we can't display HTML, so we'll just show the text.
            # A more advanced version could try to convert HTML to Markdown.
            import re
            clean_body = re.sub('<[^<]+?>', '', body)  # Basic HTML tag stripping

            embed = discord.Embed(
                title=f"Subject: {subject}",
                description=f"**From:** {from_addr}",
                color=discord.Color.orange()
            )
            # Discord embed descriptions have a 4096 character limit
            embed.add_field(name="Body", value=clean_body[:1024], inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Error in /tempmail read: {e}")
            await interaction.followup.send(f"Could not read email with ID `{email_id}`. Make sure the ID is correct.")


# ======================================================================================================================

# Register the custom command groups
tree.add_command(TempMailGroup())

# ======================================================================================================================


# 3. SYNCING: This event runs when the bot is logged in and ready.
@client.event
async def on_ready():
    global OWNER_IDS # Make accessible outside this function

    # Initialise database
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, initialise_db)


    # Fetch the application info
    app_info = await client.application_info()

    print(f"Logged in as {client.user} (ID: {client.user.id})!")
    # print(f"Application info: {app_info}")
    # print(f"Client info (Attributes & Methods): {dir(client)}")
    # print(f"Client info (Attributes & Values): {vars(client)}")

    # # Populate OWNER_IDS list with either app owner ID, or all app team member IDs
    # Using App info (app_info).
    if app_info.team:
        # If the bot is owned by a team, app_info.team will be a Team object
        # The team.members attribute is a list of TeamMember objects
        OWNER_IDS = [member.id for member in app_info.team.members]
        print(f"Owner is a Team. Authorized IDs: {OWNER_IDS}")
    elif app_info.owner.id:
        # If it's single-owner, you'll get the owner's ID instead
        OWNER_IDS = [app_info.owner.id] # Return a list containing only the single owner's ID
        print(f"Owner is a User. Authorized ID: {OWNER_IDS[0]}")
    else:
        # Fallback, will probably never happen. But we do NOT want this to fail.
        print("Could not determine bot owner.")
        OWNER_IDS = []

    # This is crucial. It syncs the commands you defined in your code
    # with Discord's servers. If you add a new command, you need this
    # to make it appear.
    await tree.sync()
    print("Commands synced.")

    # Set bots rich presence, pick one type.
    activity = discord.Game(name="with myself")
    # activity = discord.Streaming(name="My Stream!", url="https://www.twitch.tv/your_twitch_channel")
    # activity = discord.Activity(type=discord.ActivityType.listening, name="your commands")
    # activity = discord.Activity(type=discord.ActivityType.watching, name="over the server")

    await client.change_presence(status=discord.Status.online, activity=activity)
    print("Bot presence set.")

    print(" BobekBot initialised! <3 ".center(60, "."))

# ======================================================================================================================

# 4. RUN THE BOT: Get the token from an environment variable
# It will first check system environment variables, then the .env file.
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Check if the token was found
if DISCORD_BOT_TOKEN is None:
    print("Error: DISCORD_BOT_TOKEN environment variable not set.")
    print("Please ensure it's set in your system environment or in a .env file.")
else:
    try:
        client.run(DISCORD_BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("LOGIN FAILED: The provided token is invalid.")
    except Exception as e:
        print(f"An error occurred: {e}")

# ======================================================================================================================
