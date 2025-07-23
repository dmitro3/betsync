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
            "ids": "bitcoin,ethereum,litecoin,solana,tether,dogecoin",
            "vs_currencies": "usd"
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"{Fore.RED}[-] {Fore.WHITE}Failed to fetch crypto prices. Status Code: {Fore.RED}{response.status_code}{Fore.WHITE}")
            return None

    def calculate_total_usd(self, user_data):
        """Calculate total USD value for a user's wallet including all cryptos"""
        prices = self.get_crypto_prices()
        if not prices:
            print(f"{Fore.RED}[-] {Fore.WHITE}Failed to get crypto prices for USD calculation{Style.RESET_ALL}")
            return 0.0

        wallet = user_data.get("wallet", {})
        total_usd = 0.0

        # Supported cryptos and their API ids
        crypto_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "LTC": "litecoin",
            "SOL": "solana",
            "USDT": "tether",
            "DOGE": "dogecoin"
        }

        for coin, amount in wallet.items():
            if coin in crypto_map:
                api_id = crypto_map[coin]
                if api_id in prices:
                    rate = 1.0 if coin == "USDT" else prices[api_id].get("usd", 0)
                    total_usd += amount * rate

        return float(f"{total_usd:.2f}")

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
        db.save(ctx.author.id)
        #Check if a user was mentioned or ID provided
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
            # Create embed with appropriate message based on whether it's the author or mentioned user
            if user == ctx.author:
                description = "You need an account to check your balance."
            else:
                description = f"{user.mention} hasn't registered yet."

            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Required",
                description=description,
                color=0xFF0000
            )
            await ctx.reply(embed=embed)
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

            # Check if currency is disabled
            if currency in ["ETH", "USDT"]:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Currency Coming Soon",
                    description=f"**{currency}** will be available as a primary currency soon!\n\nPlease use a different currency for now.",
                    color=0xFF0000
                )
                embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
                await ctx.reply(embed=embed)
                return

            #Calculate how much of the specified currency the user has based on points
            currency_rate = crypto_values.get(currency, 0)
            currency_value = points * currency_rate

            #Prepare currency emojis
            emoji_map = {
                "BTC": "<:btc:1339343483089063976>",
                "LTC": "<:ltc:1339343445675868191>", 
                "ETH": "<:eth:1340981832799485985>",
                "USDT": "<:usdt:1340981835563401217>",
                "SOL": "<:sol:1340981839497793556>"
            }

            #Create embed to display the balance in the specified currency
            money = emoji()["money"]
            embed = discord.Embed(title=f"{money} | {user.name}'s Balance in {currency}", color=discord.Color.blue())
            embed.add_field(
                name=f"{currency} Balance",
                value=f"`{currency_value:.8f} {currency}`",
                inline=False
            )
            embed.set_footer(text="Use !setbal to change your primary currency", icon_url=self.bot.user.avatar.url)
            await ctx.reply(embed=embed)
            return


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
        emoji_map = {
            "BTC": "<:btc:1339343483089063976>",
            "LTC": "<:ltc:1339343445675868191>", 
            "ETH": "<:eth:1340981832799485985>",
            "USDT": "<:usdt:1340981835563401217>",
            "SOL": "<:sol:1340981839497793556>"
        }

        # Conversion rates
        crypto_values = {
            "BTC": 0.00000024,
            "LTC": 0.00023,
            "ETH": 0.000010,
            "USDT": 0.0212,
            "SOL": 0.0001442
        }

        # Get the user data and points
        #tokens = info.get("points", 0)

        # Current primary coin balance and conversion
        primary_rate = crypto_values.get(current_primary_coin, 0)
        primary_value = points * primary_rate
        primary_emoji = emoji_map.get(current_primary_coin, "")

        # Main balance display - clean and minimalistic
        embed.add_field(
            name="Points",
            value=f"`{points:.2f}` `({usd_value:.2f}$)`",
            inline=False
        )

        # Add USD value if available


        # Currency info field - simplified
        embed.add_field(
            name="Primary Currency", 
            value=f"`{current_primary_coin} (1 Point => {primary_rate:.8f} {current_primary_coin})`",
            inline=False
        )

        # The information is already displayed in the main balance field,
        # so we don't need these redundant fields anymore.

        embed.set_footer(text="Use !setbal to change your primary currency", icon_url=self.bot.user.avatar.url)
        db.save(ctx.author.id)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["wa"]) # Added alias for convenience
    async def wallet(self, ctx, user: discord.Member = None):
        """Shows the user's full cryptocurrency wallet balances and total USD value."""
        target_user = user or ctx.author # Default to command author if no user is mentioned
        db = Users()

        info = db.fetch_user(target_user.id)
        if not info:
            # Use a more informative embed for non-registered users
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Not Found",
                description=f"**{target_user.mention}** does not have a BetSync account yet.",
                color=0xFF0000
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)
            await ctx.reply(embed=embed)
            return

        # Fetch the wallet, providing defaults if it doesn't exist or is incomplete
        wallet_data = info.get("wallet", {})
        balances = {
            "BTC": wallet_data.get("BTC", 0),
            "LTC": wallet_data.get("LTC", 0),
            "ETH": wallet_data.get("ETH", 0),
            "USDT": wallet_data.get("USDT", 0),
            "SOL": wallet_data.get("SOL", 0),
            "DOGE": wallet_data.get("DOGE", 0) # Added DOGE based on calculate_total_usd
        }

        # Calculate total USD value
        total_usd = self.calculate_total_usd(info)

        # Prepare currency emojis (ensure consistency)
        emoji_map = {
            "BTC": "<:btc:1339343483089063976>",
            "LTC": "<:ltc:1339343445675868191>",
            "ETH": "<:eth:1340981832799485985>",
            "USDT": "<:usdt:1340981835563401217>",
            "SOL": "<:sol:1340981839497793556>",
            "DOGE": "<:doge:1344252518305234987>" # Placeholder emoji, replace if available
        }

        # Create enhanced embed
        embed = discord.Embed(
            title=f"{target_user.display_name}'s Wallet",
            color=discord.Color.blue() # Consistent color
        )
        # Set author to show user's avatar
        embed.set_author(name=target_user.name, icon_url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)

        # Add Total Value Field
        embed.add_field(
            name="💰 Total Wallet Value (USD)",
            value=f"**${total_usd:,.2f}**",
            inline=False
        )

        # Add a separator for clarity
        embed.add_field(name="\u200b", value="**Individual Balances**", inline=False) # Invisible separator field

        # Add individual balances
        balance_lines = []
        for coin, balance in balances.items():
            if balance > 0: # Only show currencies with a balance > 0
                coin_emoji = emoji_map.get(coin, "❓") # Default emoji if not found
                # Format balance to appropriate decimal places (e.g., 8 for crypto, 2 for USDT)
                decimal_places = 2 if coin == "USDT" else 8
                balance_lines.append(f"{coin_emoji} **{coin}**: `{balance:,.{decimal_places}f}`")

        if not balance_lines:
            embed.add_field(name="Empty Wallet", value="No cryptocurrency balances found.", inline=False)
        else:
            # Join balances into a single field value for better spacing control
            embed.add_field(name="Cryptocurrencies", value="\n".join(balance_lines), inline=False)

        # Updated footer
        embed.set_footer(text="BetSync Wallet | All values are approximate.", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)

        await ctx.reply(embed=embed)

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
            balance_result = db.update_balance(self.user_id, rakeback_tokens, operation="$inc")

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

        embed = discordini\n[{formatted_rakeback} points]\n```",
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
                "```\nRakeback is a loyalty reward system that returns a percentage of your bets.\n