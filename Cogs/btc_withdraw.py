import discord
from discord.ext import commands
import os
import asyncio
import datetime
from Cogs.utils.mongo import Users
from Cogs.fetches import Fetches

BTC_CONVERSION_RATE = 0.00000024  # 1 point = 0.00000024 BTC (as defined in main.py)

class WithdrawView(discord.ui.View):
    def __init__(self, cog, user_id: int, amount: float, address: str, btc_amount: float, usd_value: float):
        super().__init__(timeout=None)
        self.cog = cog
        self.user_id = user_id
        self.amount = amount
        self.address = address
        self.btc_amount = btc_amount
        self.usd_value = usd_value
        self.message = None
        self.txid = None

    async def get_txid(self, interaction: discord.Interaction):
        # Fallback for older discord.py versions without Modals
        embed = discord.Embed(
            title="ℹ️ | Transaction ID Needed",
            description="Please reply with the BTC transaction ID:",
            color=0x3498db
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
            
        try:
            msg = await self.cog.bot.wait_for('message', check=check, timeout=300)
            self.txid = msg.content.strip()
            return True
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Timed Out",
                description="Timed out waiting for transaction ID",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return False

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, emoji="✅", custom_id="withdraw_approve")
    async def approve_button(self, interaction_or_button, button=None):
        interaction = interaction_or_button if isinstance(interaction_or_button, discord.Interaction) else button
        if isinstance(interaction, discord.Interaction):
            await interaction.response.defer()
        else:
            await interaction.respond(type=6)  # DEFER
        
        if not await self.get_txid(interaction):
            return
            
        try:
            # Update embed
            embed = self.message.embeds[0]
            embed.title = "<:yes:1355501647538815106> | Withdrawal Completed"
            embed.color = discord.Color.green()
            embed.clear_fields()
            embed.add_field(name="Amount", value=f"{self.btc_amount:.8f} BTC", inline=True)
            embed.add_field(name="Address", value=f"`{self.address}`", inline=True)
            embed.add_field(name="Transaction", value=f"[{self.txid[:12]}...](https://blockstream.info/tx/{self.txid})", inline=False)
            
            # Log completion
            log_embed = discord.Embed(
                title="<:yes:1355501647538815106> | Withdrawal Completed",
                description=f"**User:** <@{self.user_id}>\n"
                          f"**Amount:** {self.amount:,.2f} points\n"
                          f"**BTC:** {self.btc_amount:.8f}\n"
                          f"**TXID:** [{self.txid[:12]}...](https://blockstream.info/tx/{self.txid})",
                color=discord.Color.green()
            )
            log_embed.set_footer(text=f"Approved by {interaction.user.name}")
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
                
            await self.message.edit(embed=embed, view=self)
            await self.cog.bot.get_channel(int(os.environ.get("LOGS"))).send(embed=log_embed)
            
            # Notify user with embed
            user = self.cog.bot.get_user(self.user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="<:yes:1355501647538815106> | Withdrawal Completed",
                        description=f"Your withdrawal of {self.amount:,.2f} points is complete!",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Amount Sent", value=f"{self.btc_amount:.8f} BTC")
                    embed.add_field(name="Transaction", value=f"[View on Explorer](https://blockstream.info/tx/{self.txid})")
                    await user.send(embed=embed)
                except discord.Forbidden:
                    pass
                    
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Withdrawal Logged",
                description="The withdrawal has been processed and logged.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.cog.pending_withdrawals.discard(self.user_id)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="<no:1344252518305234987> | Withdrawal Error",
                description=f"Error processing withdrawal:\n```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            self.cog.users_db.update_balance(self.user_id, self.amount)
            self.cog.pending_withdrawals.discard(self.user_id)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, emoji="❌", custom_id="withdraw_deny")
    async def deny_button(self, interaction_or_button, button=None):
        interaction = interaction_or_button if isinstance(interaction_or_button, discord.Interaction) else button
        if isinstance(interaction, discord.Interaction):
            await interaction.response.defer()
        else:
            await interaction.respond(type=6)  # DEFER
        
        # Refund points
        self.cog.users_db.update_balance(self.user_id, self.amount)
        self.cog.pending_withdrawals.discard(self.user_id)
        
        # Update embed
        embed = self.message.embeds[0]
        embed.title = "<:no:1344252518305234987> | Withdrawal Denied"
        embed.color = discord.Color.red()
        embed.description = f"Denied by {interaction.user.mention}. Points refunded."
        
        # Log denial
        log_embed = discord.Embed(
            title="<:no:1344252518305234987> | Withdrawal Denied",
            description=f"**User:** <@{self.user_id}>\n"
                      f"**Amount:** {self.amount:,.2f} points\n"
                      f"**Reason:** Denied by {interaction.user.name}",
            color=discord.Color.red()
        )
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
            
        await self.message.edit(embed=embed, view=self)
        await self.cog.bot.get_channel(int(os.environ.get("LOGS"))).send(embed=log_embed)
        
        # Notify user with embed
        user = self.cog.bot.get_user(self.user_id)
        if user:
            try:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Withdrawal Denied",
                    description=f"Your withdrawal of {self.amount:,.2f} points was denied.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Status", value="Points have been refunded to your account")
                await user.send(embed=embed)
            except discord.Forbidden:
                pass
                
        embed = discord.Embed(
            title="<:no:1344252518305234987> | Withdrawal Denied",
            description="The withdrawal was denied and points have been refunded.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class BtcWithdraw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users_db = Users()
        self.fetches = Fetches(bot)
        self.pending_withdrawals = set()

    async def get_btc_price(self) -> float:
        prices = self.fetches.get_crypto_prices()
        return prices.get("bitcoin", {}).get("usd", 0) if prices else 0

    def validate_btc_address(self, address: str) -> bool:
        """Validate Bitcoin address format"""
        if not address:
            return False
        # Check for common BTC address formats
        return (address.startswith('1') or
                address.startswith('3') or
                address.startswith('bc1')) and len(address) >= 26

    @commands.command(name="withdraw", aliases=["btcwithdraw", "btcw"])
    async def withdraw(self, ctx, *, args: str = None):
        """Withdraw BTC points to a Bitcoin address (manual processing)\n
        Commands: .withdraw, .btcwithdraw, .btcw\n
        Requires BTC as primary currency (!bal BTC)"""
        print(f"DEBUG: Executing btcwithdraw command for user {ctx.author.id}")
        user_id = ctx.author.id
        
        if not args:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Missing Information",
                description="Please provide both amount and Bitcoin address\n\n"
                          "**Usage:** `!withdraw <amount> <BTC address>`\n"
                          "**Example:** `!withdraw 1000 bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq`",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        user_data = self.users_db.fetch_user(ctx.author.id)
            
        # Split args into amount and address
        parts = args.split()
        if len(parts) < 2:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Format",
                description="Please provide both amount and address separated by space\n\n"
                          "**Usage:** `!withdraw <amount> <BTC address>`",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        # Try to parse amount
        try:
            amount = float(parts[0])
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Amount",
                description="Please provide a valid number for the amount\n\n"
                          f"Received: `{parts[0]}`\n"
                          "Example: `!withdraw 1000 bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq`",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        # Rest of the input is the address
        address = ' '.join(parts[1:])
        
        if amount is None or address is None:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Missing Information",
                description="Please provide both amount and Bitcoin address\n\n"
                          "**Usage:** `!withdraw <amount> <BTC address>`\n"
                          "**Example:** `!withdraw 1000 bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq`\n\n"
                          "**Requirements:**\n"
                          "- Minimum: 50 points\n"
                          "- Valid Bitcoin address required\n"
                          "- BTC must be primary currency",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        if not self.validate_btc_address(address):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid BTC Address",
                description="Invalid Bitcoin address format\n\n"
                          "Valid BTC addresses must be:\n"
                          "- 26-35 characters long\n"
                          "- Start with: 1, 3, or bc1\n"
                          "- Only contain valid base58 or bech32 characters\n\n"
                          "Example valid address:\n"
                          "`bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq`",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        if user_id in self.pending_withdrawals:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Pending Withdrawal",
                description="You already have a pending withdrawal request.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        if amount < 50:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Amount",
                description="Minimum withdrawal is 50 points.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        user_data = self.users_db.fetch_user(user_id)
        if not user_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Not Found",
                description="No account found. Please play a game first.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        # Allow withdrawal if primary is BTC
        if user_data.get("primary_coin") == "BTC":
            btc_amount = amount * BTC_CONVERSION_RATE
            usd_value = btc_amount * (await self.get_btc_price())
            
            # Deduct points
            self.users_db.update_balance(user_id, -amount)
            self.pending_withdrawals.add(user_id)
            
            embed = discord.Embed(
                title="⏳ | Withdrawal Request",
                description=f"**User:** {ctx.author.mention}\n"
                          f"**Amount:** {amount:,.2f} points\n"
                          f"**BTC Value:** {btc_amount:.8f} BTC (${usd_value:.2f})\n"
                          f"**Address:** `{address}`",
                color=0x00FFAE
            )
            
            view = WithdrawView(self, user_id, amount, address, btc_amount, usd_value)
            channel = self.bot.get_channel(int(os.environ.get("WITH_CHAN_ID")))
            message = await channel.send(embed=embed, view=view)
            view.message = message
            
            embed = discord.Embed(
                title="⏳ | Withdrawal Submitted",
                description=f"Your request for {amount:,.2f} points has been submitted.\n"
                          f"{amount:,.2f} points have been temporarily deducted.",
                color=0x00FFAE
            )
            return await ctx.reply(embed=embed)
        else:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Wrong Currency",
                description="Set BTC as primary currency first using `!bal BTC`",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        if user_data.get("points", 0) < amount:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Balance",
                description=f"You only have {user_data.get('points', 0):,.2f} points but tried to withdraw {amount:,.2f}.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        btc_amount = amount * BTC_CONVERSION_RATE
        usd_value = btc_amount * (await self.get_btc_price())
        
        # Deduct points
        self.users_db.update_balance(user_id, -amount)
        self.pending_withdrawals.add(user_id)
        
        embed = discord.Embed(
            title="⏳ | Withdrawal Request",
            description=f"**User:** {ctx.author.mention}\n"
                      f"**Amount:** {amount:,.2f} points\n"
                      f"**BTC Value:** {btc_amount:.8f} BTC (${usd_value:.2f})\n"
                      f"**Address:** `{address}`",
            color=0x00FFAE
        )
        
        view = WithdrawView(self, user_id, amount, address, btc_amount, usd_value)
        channel = self.bot.get_channel(int(os.environ.get("WITH_CHAN_ID")))
        message = await channel.send(embed=embed, view=view)
        view.message = message
        
        embed = discord.Embed(
            title="⏳ | Withdrawal Submitted",
            description=f"Your request for {amount:,.2f} points has been submitted.\n"
                      f"{amount:,.2f} points have been temporarily deducted.",
            color=0x00FFAE
        )
        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(BtcWithdraw(bot))