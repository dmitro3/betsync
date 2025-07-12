import discord
import json
import asyncio
from discord.ext import commands
from Cogs.utils.emojis import emoji
from Cogs.start import GamePaginator

class Guide(commands.Cog):
    def __init__(self, bot):

        self.emojis = emoji()
        self.required = [self.emojis["money"]]
        self.bot = bot

    @commands.command(aliases=['cmds'])
    async def help(self, ctx):
        """Main help command with categorized commands and pagination"""
        # Create category dropdown
        class CategorySelect(discord.ui.Select):
            def __init__(self, embeds):
                super().__init__(
                    placeholder="🎲 Select a command category...",
                    options=[
                        discord.SelectOption(label="🎮 All Commands", value="all", description="View all available commands"),
                        discord.SelectOption(label="🃏 Games", value="games", description="View all casino games"),
                        discord.SelectOption(label="💰 Banking", value="banking", description="Deposit/withdraw commands"),
                        discord.SelectOption(label="👤 Profile", value="profile", description="Profile & stats commands"),
                        discord.SelectOption(label="ℹ️ Information", value="info", description="Help & info commands")
                    ]
                )
                self.embeds = embeds

            async def callback(self, interaction: discord.Interaction):
                if self.values[0] == "all":
                    await interaction.response.edit_message(
                        embed=self.embeds["all"][0],
                        view=HelpView(self.embeds, "all")
                    )
                else:
                    await interaction.response.edit_message(
                        embed=self.embeds[self.values[0]][0],
                        view=HelpView(self.embeds, self.values[0])
                    )

        # Get command descriptions from Start cog
        start_cog = self.bot.get_cog("Start")
        command_descriptions = start_cog.command_descriptions if start_cog else {}
        game_descriptions = start_cog.game_descriptions if start_cog else {}

        # Get all game commands from Cogs/games
        game_commands = {}
        for cog in self.bot.cogs.values():
            if cog.__module__.startswith("Cogs.games."):
                for cmd in cog.get_commands():
                    game_commands[cmd.name] = game_descriptions.get(cmd.name, cmd.description or "No description available")

        # Combine with other commands
        all_commands = {**command_descriptions, **game_commands}

        # Build all command pages
        embeds = {
            "all": [],
            "games": [],
            "banking": [],
            "profile": [],
            "info": []
        }

        # Categorize commands
        categorized = {
            "games": {k:v for k,v in all_commands.items() if k in game_commands},
            "banking": {k:v for k,v in all_commands.items() if k in ["deposit", "withdraw", "tip"]},
            "profile": {k:v for k,v in all_commands.items() if k in ["profile", "leaderboard", "rakeback"]},
            "info": {k:v for k,v in all_commands.items() if k in ["help", "commands", "tnc"]},
            "all": all_commands
        }
        categorized["all"] = command_descriptions

        # Build embeds for each category
        items_per_page = 8
        for category, commands in categorized.items():
            command_list = list(commands.items())
            
            # Ensure every category has at least one page
            if not command_list:
                embed = discord.Embed(
                    title=f":information_source: | {category.capitalize()} Commands",
                    description="No commands available in this category",
                    color=0x00FFAE
                )
                embeds[category].append(embed)
                continue
                
            for i in range(0, len(command_list), items_per_page):
                page_commands = command_list[i:i+items_per_page]
                
                embed = discord.Embed(
                    title=f":information_source: | {category.capitalize()} Commands",
                    description=f"Use the dropdown to switch categories\nTotal: {len(command_list)} commands",
                    color=0x00FFAE
                )
                
                for cmd, desc in page_commands:
                    embed.add_field(
                        name=f"`.{cmd}`",
                        value=desc,
                        inline=False
                    )
                
                embed.set_footer(text=f"Page {i//items_per_page + 1}/{(len(command_list)+items_per_page-1)//items_per_page}")
                embeds[category].append(embed)

        # Create combined view with dropdown and pagination
        class HelpView(discord.ui.View):
            def __init__(self, embeds, initial_category="all"):
                super().__init__()
                self.embeds = embeds
                self.current_category = initial_category
                self.current_page = 0
                
                # Add category dropdown
                self.add_item(CategorySelect(embeds))
                
                # Add pagination buttons if needed
                if len(embeds[initial_category]) > 1:
                    self.add_pagination_buttons()
            
            def add_pagination_buttons(self):
                # Previous button
                prev_button = discord.ui.Button(
                    label="◀",
                    style=discord.ButtonStyle.gray,
                    disabled=self.current_page == 0
                )
                prev_button.callback = self.prev_page
                self.add_item(prev_button)
                
                # Next button
                next_button = discord.ui.Button(
                    label="▶",
                    style=discord.ButtonStyle.gray,
                    disabled=self.current_page == len(self.embeds[self.current_category]) - 1
                )
                next_button.callback = self.next_page
                self.add_item(next_button)
            
            async def prev_page(self, interaction: discord.Interaction):
                self.current_page = max(0, self.current_page - 1)
                await self.update_view(interaction)
            
            async def next_page(self, interaction: discord.Interaction):
                self.current_page = min(len(self.embeds[self.current_category]) - 1, self.current_page + 1)
                await self.update_view(interaction)
            
            async def update_view(self, interaction):
                # Update buttons state
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        if item.label == "◀":
                            item.disabled = self.current_page == 0
                        elif item.label == "▶":
                            item.disabled = self.current_page == len(self.embeds[self.current_category]) - 1
                
                await interaction.response.edit_message(
                    embed=self.embeds[self.current_category][self.current_page],
                    view=self
                )
        
        # Send initial embed with combined view
        view = HelpView(embeds)
        await ctx.reply(embed=embeds["all"][0], view=view)

    @commands.command()
    @commands.cooldown(1, 86400, commands.BucketType.user)  # 24-hour cooldown
    async def modmail(self, ctx):
        """Send a message to the bot administrators"""
        # First, send instructions to the user
        embed = discord.Embed(
            title="📧 ModMail System",
            description="Please check your DMs to continue with the ModMail process.",
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)

        try:
            # Send DM to user asking for their message
            dm_embed = discord.Embed(
                title="📧 ModMail System",
                description="Please type your message below. This will be sent to the bot administrators.\n\nYou have 200 seconds to reply.",
                color=0x00FFAE
            )
            dm_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            dm = await ctx.author.send(embed=dm_embed)

            # Wait for user's response
            def check(m):
                return m.author == ctx.author and m.channel == dm.channel and not m.content.startswith('.') # Changed prefix check

            try:
                # Wait for response with timeout
                response = await self.bot.wait_for('message', check=check, timeout=200)
                message_content = response.content

                # Load admin IDs from file
                admin_ids = []
                try:
                    with open("admins.txt", "r") as f:
                        for line in f:
                            line = line.strip()
                            if line and line.isdigit():
                                admin_ids.append(int(line))
                except Exception as e:
                    await ctx.author.send(f"Error processing ModMail: {e}")
                    return

                # Create embed for admins
                admin_embed = discord.Embed(
                    title="📨 New ModMail",
                    description=f"**From:** {ctx.author.mention} (`{ctx.author.id}`)\n**Server:** {ctx.guild.name} (`{ctx.guild.id}`)\n\n**Message:**\n{message_content}",
                    color=0xFF9900,
                    timestamp=ctx.message.created_at
                )
                admin_embed.set_footer(text=f"User ID: {ctx.author.id}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

                # Send message to all admins
                sent_count = 0
                for admin_id in admin_ids:
                    try:
                        admin = await self.bot.fetch_user(admin_id)
                        if admin:
                            await admin.send(embed=admin_embed)
                            sent_count += 1
                    except Exception as e:
                        print(f"Failed to send ModMail to admin {admin_id}: {e}")

                # Confirm to user
                if sent_count > 0:
                    confirm_embed = discord.Embed(
                        title="✅ ModMail Sent",
                        description="Your message has been sent to the administrators. Please wait patiently for a response.",
                        color=0x00FF00
                    )
                    confirm_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
                    await ctx.author.send(embed=confirm_embed)
                else:
                    error_embed = discord.Embed(
                        title="❌ ModMail Failed",
                        description="Failed to send your message to any administrators. Please try again later or contact support.",
                        color=0xFF0000
                    )
                    error_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
                    await ctx.author.send(embed=error_embed)

            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ ModMail Timed Out",
                    description="You did not provide a message within the time limit. Please use `.modmail` again if you still need to contact administrators.", # Changed prefix
                    color=0xFF0000
                )
                timeout_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
                await ctx.author.send(embed=timeout_embed)

        except discord.Forbidden:
            # User has DMs closed
            error_embed = discord.Embed(
                title="❌ ModMail Failed",
                description="I couldn't send you a DM. Please enable DMs from server members and try again.",
                color=0xFF0000
            )
            error_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            await ctx.reply(embed=error_embed)
            self.modmail.reset_cooldown(ctx)

        # Removed redundant await ctx.reply(embed=embed) from original modmail

    @commands.command()
    async def guide(self, ctx):
        # Note: The original guide command still uses '!' prefix and mentions conversions.
        # This might need updating separately if the bot's prefix is globally changed to '.'
        # and if conversion info should be removed entirely.
        embed = discord.Embed(title=":slot_machine: **Welcome to BetSync Casino!**", color=0x00FFAE, description="**BetSync** is a **Crypto Powered Casino** where you can bet, win, and enjoy a variety of games. We offer **fast deposits**, **fair games**, and **multiple earning methods**! Here\'s everything you need to know to get started:\n")
        embed.add_field(name=f"{self.required[0]} **Tokens & Credits**", value="- **Tokens**: Used for **betting and playing games**.Use `.deposit` to get tokens\n- **Credits**: Rewarded after **winning a bet**, Used for **withdrawals**`.withdraw <credits` and **Betting**.\n- **Conversion Rates**:\n```\n1 Token/Credit = $0.0212\n```\nUse `.rate <amount> <currency>` to convert between **Tokens**, **Credits**, and **crypto**.\n", inline=False) # Changed prefix
        embed.add_field(name=":inbox_tray: **Deposits & Withdrawals**", value="- **Deposit**: Use `.deposit` to select a currency and get a address\n- **Minimum Deposit**: Check in `.help`\n- **Withdraw**: Use `.withdraw`.\n- **Minimum Withdrawal**: 20 Credits.\n- **Processing**: Deposits are instant after 1 confirmation. Withdrawals take a few minutes.\n", inline=False) # Changed prefix
        embed.add_field(name=":gift: **Earn Free Tokens**", value="- **Daily Reward**: Use `.daily` to claim **free tokens**.\n- **Giveaways**: Look out for **airdrops** hosted \n- **Tips**: Other players can **tip you tokens**.\n- **Rakeback:** Get **cashback** on bets via `.rakeback` **(based on deposits).**\n", inline=False) # Changed prefix
        embed.add_field(name=":video_game: **Playing Games**", value="- **See All Games:** Use `.games` to view available games.\n- **Multiplayer Games:** Use `.multiplayer` to see PvP games.\n - **Popular Games:** Play **Blackjack**,** Keno:**, **Towers:**, **Mines:**, **Coinflip**, and more!\n Each game has a **detailed command:**, e.g., `.blackjack` for rules, bets, and payouts.\n", inline=False) # Changed prefix
        embed.add_field(name=":shield: **Fairness & Security**", value="- All games use **cryptographically secure random number generation**\n- **Provably Fair**: Every bet is `verifiable and unbiased`.\n- **98.5% RTP**: Fair odds compared to other casinos\n", inline=False)
        embed.add_field(name=":scroll: **Example Commands**", value="- `.deposit:` **Deposit** \n - `.withdraw:` **Withdraw** \n - `.rate 100 BTC:` **Convert** \n - `.blackjack 10:` **Bet** \n - `.mines 5 3:` **Play Mines** \n - `.commands:` **All Commands** \n - `.games:` **All Games**", inline=False) # Changed prefix, updated help command
        embed.add_field(name=":question_mark: **Need Help?**", value="- For support, type `.support` and **submit a request.**\n- Got **feedback?** Let us know!", inline=False) # Changed prefix
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.set_author(name="BetSync Official Guide", icon_url=self.bot.user.avatar.url)

        await ctx.message.reply(embed=embed)

    @commands.command(aliases=['game'])
    async def games(self, ctx):
        """Display all available casino games with descriptions"""
        # Get game descriptions from Start cog
        start_cog = self.bot.get_cog("Start")
        game_descriptions = start_cog.game_descriptions if start_cog else {}
        
        # Build games embed with pagination
        embeds = []
        games_per_page = 8
        game_list = list(game_descriptions.items())
        
        for i in range(0, len(game_list), games_per_page):
            page_games = game_list[i:i+games_per_page]
            
            embed = discord.Embed(
                title="🎮 BetSync Casino Games",
                description=f"Here are all {len(game_list)} available games! Use `.game_name` to play any game.",
                color=0x00FFAE
            )
            
            for game_name, description in page_games:
                embed.add_field(
                    name=f"🎲 `.{game_name}`",
                    value=description,
                    inline=False
                )
            
            embed.set_footer(text=f"Page {i//games_per_page + 1}/{(len(game_list)+games_per_page-1)//games_per_page} • BetSync Casino")
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embeds.append(embed)
        
        # Use pagination if more than one page
        if len(embeds) > 1:
            view = GamePaginator(embeds)
            await ctx.reply(embed=embeds[0], view=view)
        else:
            await ctx.reply(embed=embeds[0] if embeds else discord.Embed(
                title="🎮 BetSync Casino Games", 
                description="No games available at the moment.", 
                color=0x00FFAE
            ))

def setup(bot):
    bot.add_cog(Guide(bot))