import os
import requests
import discord
import json
import datetime
from discord.ext import commands
from Cogs.utils.emojis import emoji
from Cogs.utils.mongo import Users, Servers
from colorama import Fore, Back, Style

class Fetches(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_crypto_prices(self):
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,litecoin,solana",
            "vs_currencies": "usd"
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"{Fore.RED}[-] {Fore.WHITE}Failed to fetch crypto prices. Status Code: {Fore.RED}{response.status_code}{Fore.WHITE}")
            return None

    @commands.command(name="rate")
    async def rate(self, ctx, amount: float = None, currency: str = None):
        bot_icon = self.bot.user.avatar.url

        if amount is None or currency is None:
            embed = discord.Embed(
                title=":bulb: How to Use `!rate`",
                description="Convert tokens/credits to cryptocurrency at real-time rates.\n\n"
                          "**Usage:** `!rate <amount> <currency>`\n"
                          "**Example:** `!rate 100 BTC`\n\n"
                          ":pushpin: **Supported Currencies:**\n"
                          "`BTC, ETH, LTC, SOL, DOGE, USDT`",
                color=0xFFD700
            )
            embed.set_thumbnail(url=bot_icon)
            embed.set_footer(text="BetSync Casino • Live Exchange Rates", icon_url=bot_icon)
            return await ctx.message.reply(embed=embed)

        currency = currency.upper()
        prices = self.get_crypto_prices()

        if not prices:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | API Error",
                description="Could not retrieve live crypto prices. Please try again later.",
                color=0xFF0000
            )
            embed.set_footer(text="BetSync Casino", icon_url=bot_icon)
            return await ctx.message.reply(embed=embed)

        conversion_rates = {
            "BTC": prices.get("bitcoin", {}).get("usd"),
            "ETH": prices.get("ethereum", {}).get("usd"),
            "LTC": prices.get("litecoin", {}).get("usd"),
            "SOL": prices.get("solana", {}).get("usd"),
            "DOGE": prices.get("dogecoin", {}).get("usd"),
            "USDT": prices.get("tether", {}).get("usd")
        }

        if currency not in conversion_rates:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Currency",
                description=f"`{currency}` is not supported.\n\n"
                          ":pushpin: **Supported Currencies:**\n"
                          "`BTC, ETH, LTC, SOL, DOGE, USDT`",
                color=0xFF0000
            )
            embed.set_thumbnail(url=bot_icon)
            embed.set_footer(text="BetSync Casino", icon_url=bot_icon)
            return await ctx.message.reply(embed=embed)

        usd_value = amount * 0.013
        converted_amount = usd_value / conversion_rates[currency]

        embed = discord.Embed(
            title=":currency_exchange: Live Currency Conversion",
            color=0x00FFAE,
            description="ㅤㅤㅤ"
        )

        embed.add_field(
            name=":moneybag: Equivalent USD Value",
            value=f"**${usd_value:,.2f}**",
            inline=False
        )

        embed.add_field(
            name=f":arrows_counterclockwise: {amount:,.2f} Tokens/Credits in {currency}",
            value=f"```ini\n[{converted_amount:.8f} {currency}]\n```",
            inline=False
        )

        embed.set_thumbnail(url=bot_icon)
        embed.set_footer(text="BetSync Casino • Live Exchange Rates", icon_url=bot_icon)

        await ctx.message.reply(embed=embed)

    @commands.command()
    async def stats(self, ctx, user: discord.Member = None):
        user = ctx.author
        user_id = user.id
        db = Users()
        info = db.fetch_user(user_id)
        if info == False:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Registered", description="wait for autoregister to take place then use this command again", color=0xFF0000)
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar)
            return await ctx.message.reply(embed=embed)
        else:
            deposits = info["total_deposit_amount"]
            withdrawals = info["total_withdraw_amount"]
            games_played = info["total_played"]
            profit = info["total_earned"]
            games_won = info["total_won"]
            games_lost = info["total_lost"]
            spent = info["total_spent"]




        moneybag = emoji()["money"]
        statsemoji = emoji()["stats"]
        # Create embed
        embed = discord.Embed(title=f":star: | Stats for {user.name}", color=discord.Color.blue())
        embed.add_field(name=f"{moneybag} **Deposits:**", value=f"```{deposits} Tokens```", inline=False)
        embed.add_field(name=":outbox_tray: **Withdrawals:**", value=f"```{withdrawals} Credits```", inline=False)
        #embed.add_field(
            #name=":gift: Tips:",
            #value=f"Sent: **{tokens_tipped}** tokens, **{credits_tipped}** credits\n Received: **{tokens_received}** tokens, **{credits_received}** credits",
        #inline=False
    #)
        embed.add_field(name=":money_bag: Wagered", value=f"```{spent} Tokens```")
        embed.add_field(name=":money_with_wings: Won", value=f"```{profit} Credits```")
        #embed.add_field(
            #name=f"{statsemoji} Games:",
            #value=f":video_game: **Played: {games_played} games**\n:trophy: **Games Won: {games_won} games**\n",
            #inline=False
        #)
        #embed.add_field(name=":medal: Badges:", value=badge_text, inline=False)
        embed.set_footer(text="BetSync User Stats", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)


        await ctx.reply(embed=embed)

    @commands.command(aliases=["bal"])
    async def balance(self, ctx, param: str = None):
        """
        Show user balance with cryptocurrency conversions
        Usage: !bal [currency/user] - Sets currency or shows balance of mentioned user
        """
        user = ctx.author
        db = Users()
        
        # Check if a user was mentioned or ID provided
        mentioned_user = None
        if param:
            # Try to convert mention to a user
            try:
                # Extract user ID from mention format or use parameter directly
                user_id = int(''.join(filter(str.isdigit, param)))
                try:
                    mentioned_user = await self.bot.fetch_user(user_id)
                    user = mentioned_user  # Set user to mentioned user
                except:
                    # If not a valid user, assume it's a currency
                    pass
            except ValueError:
                # Not a user ID or mention, treat as currency
                pass
        
        # Fetch user info
        info = db.fetch_user(user.id)
        if not info:
            await ctx.reply(f"**{user.name} Does Not Have An Account.**")
            return
            
        # Currency chart from main.py
        crypto_values = {
            "BTC": 0.00000024,  # 1 point = 0.00000024 btc
            "LTC": 0.00023,     # 1 point = 0.00023 ltc
            "ETH": 0.000010,    # 1 point = 0.000010 eth
            "USDT": 0.0212,     # 1 point = 0.0212 usdt
            "SOL": 0.0001442    # 1 point = 0.0001442 sol
        }
        
        # Get current primary coin and points
        current_primary_coin = info.get("primary_coin", "BTC")
        points = info.get("points", 0)
        wallet = info.get("wallet", {
            "BTC": 0,
            "SOL": 0,
            "ETH": 0,
            "LTC": 0,
            "USDT": 0
        })
        
        # If it's not a user mention and param is specified, treat as currency
        currency = None
        if param and not mentioned_user:
            currency = param.upper()
            if currency not in crypto_values:
                await ctx.reply(f"**Invalid currency. Supported currencies: {', '.join(crypto_values.keys())}**")
                return
                
            # Calculate how much of the current primary coin the user has based on points
            current_coin_amount = points * crypto_values[current_primary_coin]
            
            # Update wallet with current coin value
            wallet[current_primary_coin] = current_coin_amount
            
            # Set points based on new currency from wallet
            new_coin_amount = wallet.get(currency, 0)
            new_points = new_coin_amount / crypto_values[currency] if crypto_values[currency] > 0 else 0
            
            # Update database with new primary coin and points
            db.collection.update_one(
                {"discord_id": user.id},
                {
                    "$set": {
                        "primary_coin": currency,
                        "points": new_points,
                        f"wallet.{current_primary_coin}": current_coin_amount
                    }
                }
            )
            
            # Update local variables for display
            current_primary_coin = currency
            points = new_points
            
        # Get live prices using crypto utility
        try:
            from Cogs.utils.crypto_utils import get_crypto_prices
            live_prices = get_crypto_prices()
        except ImportError:
            # Fallback if crypto_utils doesn't exist
            live_prices = {}
            
        # Calculate USD value of points based on primary coin
        coin_value = crypto_values.get(current_primary_coin, 0)
        primary_coin_amount = points * coin_value
        
        # Get USD value of primary coin amount
        coin_usd_price = 0
        # Special case for USDT as it's a stablecoin pegged to $1
        if current_primary_coin == "USDT":
            coin_usd_price = 1.0  # 1 USDT = $1 USD
        elif live_prices and current_primary_coin.lower() in live_prices:
            coin_usd_price = live_prices[current_primary_coin.lower()].get("usd", 0)
        
        usd_value = primary_coin_amount * coin_usd_price if coin_usd_price else 0
        
        # Create embed
        money = emoji()["money"]
        embed = discord.Embed(title=f"{money} | {user.name}'s Balance", color=discord.Color.blue())
        
        # Prepare currency emojis
        btc_emoji = "<:btc:1339343483089063976>"
        ltc_emoji = "<:ltc:1339343445675868191>"
        eth_emoji = "<:eth:1340981832799485985>"
        usdt_emoji = "<:usdt:1340981835563401217>"
        sol_emoji = "<:sol:1340981839497793556>"
        
        # Conversion rates
        crypto_values = {
            "BTC": 0.00000024,
            "LTC": 0.00023,
            "ETH": 0.000010,
            "USDT": 0.0212,
            "SOL": 0.0001442
        }
        
        # Calculate token values in each crypto
        user_data = db.fetch_user(ctx.author.id)
        tokens = user_data.get("points", 0)
        
        # Current primary coin balance 
        if current_primary_coin in user_data.get("wallet", {}):
            primary_balance = user_data["wallet"][current_primary_coin]
        else:
            primary_balance = 0
            
        # Main tokens/credits balance field
        embed.add_field(
            name="Balance",
            value=f"**Points:** `{tokens:.2f}`",
            inline=False
        )
        
        # Add conversion field showing token value in each currency
        conversions = []
        for crypto, rate in crypto_values.items():
            emoji_map = {
                "BTC": btc_emoji,
                "LTC": ltc_emoji, 
                "ETH": eth_emoji,
                "USDT": usdt_emoji,
                "SOL": sol_emoji
            }
            emoji_icon = emoji_map.get(crypto, "")
            value = tokens * rate
            conversions.append(f"{emoji_icon} `{value:.8f}` {crypto}")
        
        embed.add_field(
            name="Token Conversion Rates",
            value="\n".join(conversions),
            inline=False
        )
        
        # Add USD value
        if usd_value > 0:
            embed.add_field(
                name="Estimated Value",
                value=f"**USD:** `${usd_value:.2f}`",
                inline=False
            )
        
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        
        # Currency info field
        embed.add_field(
            name="Currency Info", 
            value=f"**Your primary currency is {current_primary_coin}. Use `!bal <currency>` to change it.**",
            inline=False
        )
        
        # Separator
        embed.add_field(
            name="",
            value="\u200b",  # Zero-width space
            inline=False
        )
        
        # Combined points and USD value field
        if coin_usd_price:
            embed.add_field(
                name=":moneybag: Points", 
                value=f"```{round(points, 2)} Points (${usd_value:.2f} USD)```",
                inline=False
            )
        else:
            embed.add_field(
                name=":moneybag: Points", 
                value=f"```{round(points, 2)} Points```",
                inline=False
            )
        
        # Conversion rate field
        embed.add_field(
            name=":arrows_counterclockwise: Conversion Rate", 
            value=f"```1 Point = {coin_value:.8f} {current_primary_coin}```",
            inline=False
        )
        
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        db.save(ctx.author.id)
        await ctx.reply(embed=embed)

    # Leaderboard Pagination View
    class LeaderboardView(discord.ui.View):
        def __init__(self, author_id, all_data, page_size=10, timeout=60):
            super().__init__(timeout=timeout)
            self.author_id = author_id
            self.all_data = all_data
            self.page_size = page_size
            self.current_page = 0
            self.total_pages = max(1, (len(all_data["users"]) + page_size - 1) // page_size)
            self.message = None
            self.scope = all_data.get("scope", "global")
            self.leaderboard_type = all_data.get("type", "stats")
            self.stat_type = all_data.get("stat_type", "wins")

            # Disable buttons if not needed
            self.update_buttons()

        def update_buttons(self):
            # Disable/enable prev/next buttons based on current page
            self.first_page_button.disabled = self.current_page == 0
            self.prev_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page >= self.total_pages - 1
            self.last_page_button.disabled = self.current_page >= self.total_pages - 1

        @discord.ui.button(label="<<", style=discord.ButtonStyle.gray, custom_id="first_page")
        async def first_page_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = 0
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        @discord.ui.button(label="<", style=discord.ButtonStyle.gray, custom_id="prev_page")
        async def prev_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = max(0, self.current_page - 1)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        @discord.ui.button(label=">", style=discord.ButtonStyle.gray, custom_id="next_page")
        async def next_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = min(self.total_pages - 1, self.current_page + 1)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        @discord.ui.button(label=">>", style=discord.ButtonStyle.gray, custom_id="last_page")
        async def last_page_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = self.total_pages - 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        def get_current_page_embed(self):
            # Get data for current page
            start_idx = self.current_page * self.page_size
            end_idx = min(start_idx + self.page_size, len(self.all_data["users"]))
            current_page_data = self.all_data["users"][start_idx:end_idx]

            # Create embed based on leaderboard type
            if self.leaderboard_type == "stats":
                return self.create_stats_embed(current_page_data, start_idx)
            elif self.leaderboard_type == "wagered":
                return self.create_wagered_embed(current_page_data, start_idx)

            # Default to stats embed
            return self.create_stats_embed(current_page_data, start_idx)

        def create_stats_embed(self, users_data, start_idx):
            stat_type = self.stat_type
            scope_text = self.scope.capitalize()
            stat_icon = "🏆" if stat_type == "wins" else "❌"

            title_text = "Wins" if stat_type == "wins" else "Losses"
            
            # Find user's position in the full leaderboard
            user_id = self.all_data.get("author_id")
            user_position = None
            for i, user in enumerate(self.all_data["users"]):
                if user["id"] == user_id:
                    user_position = i + 1
                    break
            
            description = f"Top users ranked by total {stat_type}"
            if user_position:
                user_amount = next((user["amount"] for user in self.all_data["users"] if user["id"] == user_id), 0)
                description += f"\n\n**Your Rank: #{user_position}** with **{user_amount:,.0f}** {stat_type}"
            
            embed = discord.Embed(
                title=f"{stat_icon} {scope_text} {title_text} Leaderboard",
                description=description,
                color=0x00FFAE if stat_type == "wins" else 0xFF5500
            )

            for i, user_data in enumerate(users_data):
                # Calculate actual position on leaderboard
                position = start_idx + i + 1

                # Format the amount with commas
                stat_value = f"{user_data['amount']:,.0f}"

                embed.add_field(
                    name=f"#{position}. {user_data['name']}",
                    value=f"{stat_icon} **{stat_value}** {stat_type}",
                    inline=False
                )

            # Add pagination details to footer
            footer_text = f"BetSync Casino • Page {self.current_page + 1} of {self.total_pages}"
            embed.set_footer(text=footer_text, icon_url=self.all_data.get("bot_avatar", ""))
            return embed

        def create_wagered_embed(self, users_data, start_idx):
            scope_text = self.scope.capitalize()
            
            # Find user's position in the full leaderboard
            user_id = self.all_data.get("author_id")
            user_position = None
            for i, user in enumerate(self.all_data["users"]):
                if user["id"] == user_id:
                    user_position = i + 1
                    break
            
            description = f"Top users ranked by total amount wagered"
            if user_position:
                user_amount = next((user["amount"] for user in self.all_data["users"] if user["id"] == user_id), 0)
                description += f"\n\n**Your Rank: #{user_position}** with **{user_amount:,.2f}** wagered"
            
            embed = discord.Embed(
                title=f"🔥 {scope_text} Wagering Leaderboard",
                description=description,
                color=0xFF5500
            )

            for i, user_data in enumerate(users_data):
                # Calculate actual position on leaderboard
                position = start_idx + i + 1

                # Format the amount with commas
                wagered = f"{user_data['amount']:,.2f}"

                embed.add_field(
                    name=f"#{position}. {user_data['name']}",
                    value=f"💸 **{wagered}** wagered",
                    inline=False
                )

            # Add pagination details to footer
            footer_text = f"BetSync Casino • Page {self.current_page + 1} of {self.total_pages}"
            embed.set_footer(text=footer_text, icon_url=self.all_data.get("bot_avatar", ""))
            return embed

        async def on_timeout(self):
            # Disable all buttons when the view times out
            for child in self.children:
                child.disabled = True

            if self.message:
                try:
                    await self.message.edit(view=self)
                except:
                    pass

    @commands.command(aliases=["lb", "top"])
    async def leaderboard(self, ctx, arg1: str = None, arg2: str = None):
        """View the leaderboard for wins, losses, or wagered amount

        Usage: !leaderboard [scope] [type] 
        Examples: 
        - !leaderboard global wins
        - !leaderboard server losses
        - !leaderboard wagered
        - !leaderboard server wagered
        """
        # If no arguments are provided, show usage information
        if arg1 is None and arg2 is None:
            return await self.show_leaderboard_usage(ctx)

        # Default values
        scope = "global"
        leaderboard_type = "stats"
        stat_type = "wins"

        # Parse arguments (flexible order)
        args = [a.lower() for a in [arg1, arg2] if a]

        # Check for scope
        if "global" in args:
            scope = "global"
            args.remove("global")
        elif "server" in args:
            scope = "server"
            args.remove("server")

        # Check for type
        if "wagered" in args:
            leaderboard_type = "wagered"
            args.remove("wagered")

        # Remaining arg should be stat type (if stats type)
        if args and leaderboard_type == "stats":
            if args[0] in ["wins", "losses"]:
                stat_type = args[0]
            else:
                return await self.show_leaderboard_usage(ctx)

        # If in DM and requesting server leaderboard
        if scope == "server" and ctx.guild is None:
            return await ctx.reply("Server leaderboard can only be viewed in a server.")

        # Get the leaderboard data
        if leaderboard_type == "stats":
            if scope == "global":
                await self.show_global_stats_leaderboard(ctx, stat_type)
            else:  # scope == "server"
                await self.show_server_stats_leaderboard(ctx, stat_type)
        else:  # leaderboard_type == "wagered"
            if scope == "global":
                await self.show_global_wagered_leaderboard(ctx)
            else:  # scope == "server"
                await self.show_server_wagered_leaderboard(ctx)

    async def show_leaderboard_usage(self, ctx):
        """Show usage information for leaderboard command"""
        embed = discord.Embed(
            title=":trophy: Leaderboard - Usage",
            description=(
                "View the top users by wins, losses, or wagered amount.\n\n"
                "**Usage:** `!leaderboard [scope] [type]`\n\n"
                "**Examples:**\n"
                "`!leaderboard global wins` - Global wins leaderboard\n"
                "`!leaderboard server losses` - Server losses leaderboard\n"
                "`!leaderboard wagered` - Global wagering leaderboard\n"
                "`!leaderboard server wagered` - Server wagering leaderboard\n\n"
                "**Available Scopes:**\n"
                "`global` - Show leaderboard across all servers\n"
                "`server` - Show leaderboard for the current server\n\n"
                "**Available Types:**\n"
                "`wins` - Show leaderboard by total wins\n"
                "`losses` - Show leaderboard by total losses\n"
                "`wagered` - Show leaderboard by total amount wagered"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        return await ctx.reply(embed=embed)

    async def show_global_stats_leaderboard(self, ctx, stat_type):
        """Show global leaderboard for wins or losses with pagination"""
        db = Users()

        # Get all users sorted by the specified stat
        field_name = "total_won" if stat_type == "wins" else "total_lost"
        users = list(db.collection.find().sort([(field_name, -1)]))

        if not users:
            return await ctx.reply("No users found in the leaderboard.")

        # Prepare data for pagination
        formatted_users = []
        for user_data in users:
            if user_data.get(field_name, 0) > 0: # Filter out users with 0 value
                try:
                    user = await self.bot.fetch_user(user_data["discord_id"])
                    user_name = user.name if user else f"User {user_data['discord_id']}"

                    formatted_users.append({
                        "name": user_name,
                        "amount": user_data.get(field_name, 0),
                        "id": user_data["discord_id"]
                    })
                except Exception as e:
                    print(f"Error getting user: {e}")
                    continue

        # Create the data structure for the paginated view
        leaderboard_data = {
            "users": formatted_users,
            "scope": "global",
            "type": "stats",
            "stat_type": stat_type,
            "bot_avatar": self.bot.user.avatar.url,
            "author_id": ctx.author.id
        }

        # Create and send the paginated view
        view = self.LeaderboardView(ctx.author.id, leaderboard_data)
        message = await ctx.reply(embed=view.get_current_page_embed(), view=view)
        view.message = message

    async def show_server_stats_leaderboard(self, ctx, stat_type):
        """Show server leaderboard for wins or losses with pagination"""
        db = Users()
        server_users = []

        # First get all users in the database
        all_users = list(db.collection.find())

        # Get all members in the server
        server_members = ctx.guild.members
        server_member_ids = [member.id for member in server_members]

        # Filter users who are in this server
        for user_data in all_users:
            if user_data["discord_id"] in server_member_ids:
                server_users.append(user_data)

        # Sort the filtered users by the specified stat
        field_name = "total_won" if stat_type == "wins" else "total_lost"
        server_users.sort(key=lambda x: x.get(field_name, 0), reverse=True)

        if not server_users:
            return await ctx.reply("No users found in the server leaderboard.")

        # Prepare data for pagination
        formatted_users = []
        for user_data in server_users:
            if user_data.get(field_name, 0) > 0: # Filter out users with 0 value
                try:
                    user = await self.bot.fetch_user(user_data["discord_id"])
                    user_name = user.name if user else f"User {user_data['discord_id']}"

                    formatted_users.append({
                        "name": user_name,
                        "amount": user_data.get(field_name, 0),
                        "id": user_data["discord_id"]
                    })
                except Exception as e:
                    print(f"Error getting user: {e}")
                    continue

        # Create the data structure for the paginated view
        leaderboard_data = {
            "users": formatted_users,
            "scope": "server",
            "type": "stats",
            "stat_type": stat_type,
            "bot_avatar": self.bot.user.avatar.url,
            "author_id": ctx.author.id
        }

        # Create and send the paginated view
        view = self.LeaderboardView(ctx.author.id, leaderboard_data)
        message = await ctx.reply(embed=view.get_current_page_embed(), view=view)
        view.message = message

    async def show_global_wagered_leaderboard(self, ctx):
        """Show global leaderboard for amount wagered with pagination"""
        db = Users()
        # Get all users, we'll sort by total_spent
        users = list(db.collection.find().sort([("total_spent", -1)]))

        if not users:
            return await ctx.reply("No users found in the leaderboard.")

        # Prepare data for pagination
        formatted_users = []
        for user_data in users:
            if user_data.get("total_spent", 0) > 0: #Filter out users with 0 value
                try:
                    user = await self.bot.fetch_user(user_data["discord_id"])
                    user_name = user.name if user else f"User {user_data['discord_id']}"

                    formatted_users.append({
                        "name": user_name,
                        "amount": user_data.get("total_spent", 0),
                        "id": user_data["discord_id"]
                    })
                except Exception as e:
                    print(f"Error getting user: {e}")
                    continue

        # Create the data structure for the paginated view
        leaderboard_data = {
            "users": formatted_users,
            "scope": "global",
            "type": "wagered",
            "bot_avatar": self.bot.user.avatar.url,
            "author_id": ctx.author.id
        }

        # Create and send the paginated view
        view = self.LeaderboardView(ctx.author.id, leaderboard_data)
        message = await ctx.reply(embed=view.get_current_page_embed(), view=view)
        view.message = message

    async def show_server_wagered_leaderboard(self, ctx):
        """Show server leaderboard for amount wagered with pagination"""
        db = Users()
        server_users = []

        # First get all users in the database
        all_users = list(db.collection.find())

        # Get all members in the server
        server_members = ctx.guild.members
        server_member_ids = [member.id for member in server_members]

        # Filter users who are in this server
        for user_data in all_users:
            if user_data["discord_id"] in server_member_ids:
                server_users.append(user_data)

        # Sort the filtered users by total_spent
        server_users.sort(key=lambda x: x.get("total_spent", 0), reverse=True)

        if not server_users:
            return await ctx.reply("No users found in the server leaderboard.")

        # Prepare data for pagination
        formatted_users = []
        for user_data in server_users:
            if user_data.get("total_spent", 0) > 0: #Filter out users with 0 value
                try:
                    user = await self.bot.fetch_user(user_data["discord_id"])
                    user_name = user.name if user else f"User {user_data['discord_id']}"

                    formatted_users.append({
                        "name": user_name,
                        "amount": user_data.get("total_spent", 0),
                        "id": user_data["discord_id"]
                    })
                except Exception as e:
                    print(f"Error getting user: {e}")
                    continue

        # Create the data structure for the paginated view
        leaderboard_data = {
            "users": formatted_users,
            "scope": "server",
            "type": "wagered",
            "bot_avatar": self.bot.user.avatar.url,
            "author_id": ctx.author.id
        }

        # Create and send the paginated view
        view = self.LeaderboardView(ctx.author.id, leaderboard_data)
        message = await ctx.reply(embed=view.get_current_page_embed(), view=view)
        view.message = message

    @commands.command(name="rank")
    async def rank(self, ctx, user: discord.Member = None):
        """View your current rank, progress, and benefits"""
        if not user:
            user = ctx.author
            
        db = Users()
        user_data = db.fetch_user(user.id)
        
        if not user_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Registered",
                description="This user doesn't have an account yet. Please wait for auto-registration or use commands to interact with the bot.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Load rank data from JSON
        with open('static_data/ranks.json', 'r') as f:
            rank_data = json.load(f)
            
        # Get current user level and XP
        current_level = user_data.get('level', 1)
        current_xp = user_data.get('xp', 0)
        current_rank_requirement = user_data.get('rank', 0)
        
        # Calculate XP needed for next level
        xp_limit = 10 * (1 + (current_level - 1) * 0.1)
        xp_limit = round(xp_limit)
        
        # Find current rank name and emoji
        current_rank_name = "None"
        current_emoji = ""
        current_rakeback = 0
        
        # Find next rank
        next_rank_name = None
        next_rank_level = float('inf')
        next_rank_emoji = None
        
        # Sort ranks by level requirement
        sorted_ranks = sorted(rank_data.items(), key=lambda x: x[1]['level_requirement'])
        
        # Find current rank and next rank
        for rank_name, rank_info in sorted_ranks:
            level_req = rank_info['level_requirement']
            
            # Check if this is the current rank
            if level_req == current_rank_requirement:
                current_rank_name = rank_name
                current_emoji = rank_info['emoji']
                current_rakeback = rank_info['rakeback_percentage']
            
            # Check if this is the next rank
            if level_req > current_level and level_req < next_rank_level:
                next_rank_name = rank_name
                next_rank_level = level_req
                next_rank_emoji = rank_info['emoji']
        
        # If we couldn't find a next rank, user is at max rank
        if next_rank_name is None:
            next_rank_name = "Max Rank"
            next_rank_level = current_level
            next_rank_emoji = "🔥"
            levels_needed = 0
        else:
            levels_needed = next_rank_level - current_level
        
        # Create embed
        embed = discord.Embed(
            title=f"{current_emoji} Rank Information for {user.name}",
            color=0x00FFAE,
            description=f"Your progress through the BetSync rank system"
        )
        
        # Current rank section
        embed.add_field(
            name="Current Rank",
            value=f"{current_emoji} **{current_rank_name}**\n"
                  f"Level: **{current_level}**\n"
                  f"XP: **{current_xp}/{xp_limit}**\n"
                  f"Rakeback: **{current_rakeback}%**",
            inline=True
        )
        
        # Next rank section
        embed.add_field(
            name="Next Rank",
            value=f"{next_rank_emoji} **{next_rank_name}**\n"
                  f"Required Level: **{next_rank_level}**\n"
                  f"Levels Needed: **{levels_needed}**",
            inline=True
        )
        
        # Progress bar
        progress = min(1.0, current_xp / xp_limit)
        bar_length = 12
        filled_bars = round(progress * bar_length)
        empty_bars = bar_length - filled_bars
        
        progress_bar = "**Level Progress:**\n"
        progress_bar += "```\n"
        progress_bar += f"[{'■' * filled_bars}{' ' * empty_bars}] {int(progress * 100)}%\n"
        progress_bar += "```"
        
        embed.add_field(
            name="Level Progress",
            value=progress_bar,
            inline=False
        )
        
        # All ranks section
        all_ranks = ""
        for rank_name, rank_info in sorted_ranks:
            emoji = rank_info['emoji']
            level_req = rank_info['level_requirement']
            rakeback = rank_info['rakeback_percentage']
            
            # Highlight current rank
            if rank_name == current_rank_name:
                all_ranks += f"➤ {emoji} **{rank_name}** (Lv. {level_req}) - {rakeback}% rakeback\n"
            else:
                all_ranks += f"{emoji} {rank_name} (Lv. {level_req}) - {rakeback}% rakeback\n"
        
        embed.add_field(
            name="All Ranks",
            value=all_ranks,
            inline=False
        )
        
        # Set thumbnail to user avatar
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
            
        embed.set_footer(text="BetSync Casino • Rank up by playing games", icon_url=self.bot.user.avatar.url)
        
        await ctx.reply(embed=embed)

    class RakebackButton(discord.ui.View):
        def __init__(self, cog, user_id, rakeback_amount):
            super().__init__(timeout=60)
            self.cog = cog
            self.user_id = user_id
            self.rakeback_amount = rakeback_amount
            
        @discord.ui.button(label="Claim Rakeback", style=discord.ButtonStyle.green, emoji="💰")
        async def claim_button(self, button, interaction):
            # Only the user who initiated can claim
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("You cannot claim someone else's rakeback!", ephemeral=True)
            
            # Process the claim
            db = Users()
            user_data = db.fetch_user(self.user_id)
            
            if not user_data:
                print(f"{Back.RED}  {Style.DIM}{self.user_id}{Style.RESET_ALL}{Back.RESET}{Fore.RED}    ERROR    {Fore.WHITE}User data not found when claiming rakeback{Style.RESET_ALL}")
                return await interaction.response.send_message("Error: User data not found.", ephemeral=True)
                
            rakeback_tokens = user_data.get("rakeback_tokens", 0)
            
            if rakeback_tokens <= 0:
                print(f"{Back.YELLOW}  {Style.DIM}{self.user_id}{Style.RESET_ALL}{Back.RESET}{Fore.YELLOW}    WARNING    {Fore.WHITE}Attempted to claim zero rakeback tokens{Style.RESET_ALL}")
                return await interaction.response.send_message("You don't have any rakeback tokens to claim!", ephemeral=True)
            
            # Log before claiming
            rn = datetime.datetime.now().strftime("%X")
            print(f"{Back.CYAN}  {Style.DIM}{self.user_id}{Style.RESET_ALL}{Back.RESET}{Fore.CYAN}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{Fore.GREEN}Claiming {rakeback_tokens:.2f} rakeback tokens{Style.RESET_ALL}  {Fore.MAGENTA}rakeback_claim{Fore.WHITE}")
            
            # Update rakeback tokens to 0
            update_result = db.collection.update_one(
                {"discord_id": self.user_id},
                {"$set": {"rakeback_tokens": 0}}
            )
            
            # Add the rakeback tokens to user's tokens
            balance_result = db.update_balance(self.user_id, rakeback_tokens)
            
            # Log after claiming
            print(f"{Back.GREEN}  {Style.DIM}{self.user_id}{Style.RESET_ALL}{Back.RESET}{Fore.GREEN}    SUCCESS    {Fore.WHITE}Rakeback claimed: {rakeback_tokens:.2f} points | DB updates: {update_result.modified_count}, {balance_result}{Style.RESET_ALL}")
            
            # Disable the button
            for child in self.children:
                child.disabled = True
            await interaction.response.defer()
            message = await interaction.original_response()
            await message.edit(view=self)
            
            # Send success message with enhanced styling
            claim_embed = discord.Embed(
                title="💰 Rakeback Claimed Successfully",
                description=f"You have successfully claimed your rakeback rewards!",
                color=0x00FFAE
            )
            
            # Add field for claimed amount with styled box
            claim_embed.add_field(
                name="🎉 Claimed Amount",
                value=f"```ini\n[{rakeback_tokens:,.2f} points added to your balance]\n```",
                inline=False
            )
            
            # Add a field showing new balance
            new_balance = db.fetch_user(self.user_id).get('points', 0)
            claim_embed.add_field(
                name="💵 New points Balance",
                value=f"**{new_balance:,.2f} tokens**",
                inline=True
            )
            
            claim_embed.set_footer(text="BetSync Casino • Rakeback Rewards", icon_url=self.cog.bot.user.avatar.url)
            
            await interaction.followup.send(embed=claim_embed)

    @commands.command(name="rakeback", aliases=["rb"])
    async def rakeback(self, ctx, user: discord.Member = None):
        """View and claim your rakeback rewards"""
        if not user:
            user = ctx.author
            
        db = Users()
        user_data = db.fetch_user(user.id)
        
        if not user_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Registered",
                description="This user doesn't have an account yet. Please wait for auto-registration or use commands to interact with the bot.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Get rakeback percentage from rank data
        with open('static_data/ranks.json', 'r') as f:
            rank_data = json.load(f)
            
        current_rank_requirement = user_data.get('rank', 0)
        rakeback_percentage = 0
        rank_name = "None"
        rank_emoji = ""
        
        # Find current rank and its rakeback percentage
        for name, info in rank_data.items():
            if info['level_requirement'] == current_rank_requirement:
                rakeback_percentage = info['rakeback_percentage']
                rank_name = name
                rank_emoji = info['emoji']
                break
        
        # Get accumulated rakeback tokens
        rakeback_tokens = user_data.get('rakeback_tokens', 0)
        
        # Format tokens with commas for better readability
        formatted_rakeback = f"{rakeback_tokens:,.2f}"
        
        # Create embed
        if user == ctx.author:
            title = f"💰 Rakeback Rewards"
        else:
            title = f"💰 {user.name}'s Rakeback Rewards"
            
        embed = discord.Embed(
            title=title,
            color=0x00FFAE,
            description=f"**Earn cashback rewards based on your betting activity**\nㅤㅤㅤ"
        )
        
        # Add a rank section with emoji and styled text
        embed.add_field(
            name="🏆 Current Rank",
            value=f"{rank_emoji} **{rank_name}**\nRakeback Rate: **{rakeback_percentage}%**",
            inline=True
        )
        
        # Add tokens section with styled text
        embed.add_field(
            name="💵 Available Rakeback",
            value=f"```ini\n[{formatted_rakeback} points]\n```",
            inline=True
        )
        
        # Add a spacer field to create 2 columns
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        # Create a progress-style display for claim eligibility
        if rakeback_tokens < 1:
            progress = min(rakeback_tokens, 1.0)
            bar_length = 10
            filled_bars = round(progress * bar_length)
            empty_bars = bar_length - filled_bars
            
            claim_status = (
                "🔒 **Claim Status: Locked**\n"
                f"Progress to claim: `{rakeback_tokens:.2f}/1.00`\n"
                f"```\n[{'■' * filled_bars}{' ' * empty_bars}] {int(progress * 100)}%\n```"
                "You need at least **1.00 rakeback points** to claim your rakeback rewards."
            )
        else:
            claim_status = (
                "✅ **Claim Status: Ready**\n"
                "Your rakeback points are ready to claim!\n"
                "Click the button below to add these tokens to your balance."
            )
        
        embed.add_field(
            name="📊 Claim Eligibility",
            value=claim_status,
            inline=False
        )
        
        # Add information on how rakeback works with improved formatting
        embed.add_field(
            name="ℹ️ About Rakeback",
            value=(
                "```\nRakeback is a loyalty reward system that returns a percentage of your bets.\n```\n"
                f"• Every bet earns {rank_emoji} **{rank_name}** rank members **{rakeback_percentage}%** rakeback\n"
                "• Higher ranks receive higher rakeback percentages\n"
                "• Claim your rakeback points to convert them to spendable points"
            ),
            inline=False
        )
        
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
            
        embed.set_footer(text="BetSync Casino • Rakeback Rewards", icon_url=self.bot.user.avatar.url)
        
        # If viewing someone else's rakeback, don't show any button
        if user.id != ctx.author.id:
            return await ctx.reply(embed=embed)
        
        # Create view with claim button
        view = self.RakebackButton(self, ctx.author.id, rakeback_tokens)
        
        # If rakeback tokens are less than 1, disable the button
        if rakeback_tokens < 1:
            for child in view.children:
                child.disabled = True
                child.label = "Insufficient Rakeback"
        
        # Send the message with the view and save the returned message object
        # This allows the view to properly reference the message for updates
        view.message = await ctx.reply(embed=embed, view=view)


def setup(bot):
    bot.add_cog(Fetches(bot))