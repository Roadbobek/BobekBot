import discord

# 1. SETUP: Define the bot and its intents
# Intents are permissions. The default intents are fine for slash commands.
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# An app_commands.CommandTree is the object that holds all your slash commands
tree = discord.app_commands.CommandTree(client)

# 2. THE COMMAND: Define a slash command
# The decorator registers the command with Discord.
# - name: The name of the command users will type (e.g., /hello)
# - description: The help text shown in the command list
@tree.command(name="hello", description="Says hello to you!")
async def hello_command(interaction: discord.Interaction):
    """
    This is the function that runs when the /hello command is used.
    """
    # '''interaction''' is a crucial object. It represents the slash command
    # invocation and contains all the information about it, like the user
    # who ran it, the channel it was run in, and any arguments.

    # We use interaction.response.send_message() to reply.
    # '''ephemeral=True''' makes the reply visible only to the person who used
    # the command, which is great for clean channels.
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!", ephemeral=True)


# 3. SYNCING: This event runs when the bot is logged in and ready.
@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("--------------------------------")

    # This is crucial. It syncs the commands you defined in your code
    # with Discord's servers. If you add a new command, you need this
    # to make it appear.
    await tree.sync()
    print("Commands synced.")


# 4. RUN THE BOT: Replace "YOUR_BOT_TOKEN" with your actual bot token
# You get this from the Discord Developer Portal.
try:
    client.run("YOUR_BOT_TOKEN")
except discord.errors.LoginFailure:
    print("LOGIN FAILED: Please replace 'YOUR_BOT_TOKEN' with your actual bot token.")
except Exception as e:
    print(f"An error occurred: {e}")