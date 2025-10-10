import discord

# 1. SETUP: Define the bot and its intents
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# 2. THE COMMAND: Define a slash command
@tree.command(name="hello", description="Says hello and shows your avatar!")
async def hello_command(interaction: discord.Interaction):
    """
    This is the function that runs when the /hello command is used.
    """
    # To display images, we use a discord.Embed.
    # This is a special object for creating rich content boxes.
    embed = discord.Embed(
        title=f"Hello, {interaction.user.display_name}!",
        description=f"It's nice to meet you, {interaction.user.mention}.",
        color=discord.Color.from_rgb(118, 200, 229)  # You can set a custom color
    )

    # The display_avatar object has a .url property containing the image link.
    # We set this URL as the embed's thumbnail.
    embed.set_thumbnail(url=interaction.user.display_avatar.url)

    # You can also add a footer or other fields
    embed.set_footer(text="Embeds are cool!")

    # When sending, you pass the embed object to the `embed` parameter.
    await interaction.response.send_message(embed=embed)


# 3. SYNCING: This event runs when the bot is logged in and ready.
@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("------")

    # Using a global sync. For faster testing, you can sync to a specific guild:
    # MY_GUILD = discord.Object(id=123456789012345678) # Replace with your guild ID
    # await tree.sync(guild=MY_GUILD)
    await tree.sync()
    print("Commands synced.")


# 4. RUN THE BOT: Replace "YOUR_BOT_TOKEN" with your actual bot token
try:
    client.run("YOUR_BOT_TOKEN")
except discord.errors.LoginFailure:
    print("LOGIN FAILED: Please replace 'YOUR_BOT_TOKEN' with your actual bot token.")
