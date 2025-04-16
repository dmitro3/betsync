import discord
from discord.ext import commands
import requests
import json
from decimal import Decimal
from datetime import datetime
from dotenv import load_dotenv
import os
from Cogs.utils.mongo import Users
from Cogs.utils.notifier import Notifier
from Cogs.utils.emojis import emoji

load_dotenv()

# Constants
LTC_CONVERSION_RATE = Decimal('0.00023')  # 1 point = 0.00023 LTC
LTC_SEED = os.environ.get("LTC_SEED")
WITHREQ_WEBHOOK = os.environ.get("WITHREQ_WEBHOOK")
WITHSUCC_WEBHOOK = os.environ.get("WITHSUCC_WEBHOOK")
ADMINS_FILE = "admins.txt"

class WithdrawView(discord.ui.View):
    def __init__(self, cog_instance, user_id: int, amount: Decimal, address: str):
        super().__init__(timeout=None)  # No timeout - buttons never expire
        self.cog = cog_instance
        self.user_id = user_id
        self.amount = amount
        self.address = address
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow admins to interact"""
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("Only admins can approve withdrawals", ephemeral=True)
            return False
        return True

    def is_admin(self, user_id: int) -> bool:
        """Check if user is in admins.txt"""
        try:
            with open(ADMINS_FILE) as f:
                admins = [int(line.strip()) for line in f if line.strip()]
                return user_id in admins
        except:
            return False

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_withdraw")
    async def approve_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle withdrawal approval"""
        await interaction.response.defer()
        
        # Process withdrawal
        success, txid = await self.cog.process_withdrawal(
            self.user_id, 
            self.amount, 
            self.address
        )
        
        if success:
            # Update embed
            embed = interaction.message.embeds[0]
            embed.title = "✅ Withdrawal Approved"
            embed.color = discord.Color.green()
            embed.add_field(name="TXID", value=f"`{txid}`", inline=False)
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.message.edit(embed=embed, view=self)
            
            # Send success DM to user
            user = self.cog.bot.get_user(self.user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="Withdrawal Completed",
                        description=f"Your withdrawal of {self.amount} LTC has been processed",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Amount", value=f"{self.amount} LTC")
                    embed.add_field(name="Address", value=f"`{self.address}`")
                    embed.add_field(name="TXID", value=f"`{txid}`")
                    await user.send(embed=embed)
                except:
                    pass
            
            # Send success webhook
            await self.cog.send_success_webhook(self.user_id, self.amount, self.address, txid)
        else:
            await interaction.followup.send("Failed to process withdrawal", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id="reject_withdraw")
    async def reject_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle withdrawal rejection"""
        await interaction.response.defer()
        
        # Refund points to user
        self.cog.users_db.collection.update_one(
            {"discord_id": self.user_id},
            {"$inc": {"points": float(self.amount / LTC_CONVERSION_RATE)}}
        )
        
        # Update embed
        embed = interaction.message.embeds[0]
        embed.title = "❌ Withdrawal Rejected"
        embed.color = discord.Color.red()
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.message.edit(embed=embed, view=self)
        
        # Send rejection DM to user
        user = self.cog.bot.get_user(self.user_id)
        if user:
            try:
                embed = discord.Embed(
                    title="Withdrawal Rejected",
                    description=f"Your withdrawal request for {self.amount} LTC has been rejected",
                    color=discord.Color.red()
                )
                embed.add_field(name="Amount", value=f"{self.amount} LTC")
                embed.add_field(name="Address", value=f"`{self.address}`")
                embed.add_field(name="Refunded", value=f"{self.amount / LTC_CONVERSION_RATE:.2f} points")
                await user.send(embed=embed)
            except:
                pass

class LtcWithdraw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users_db = Users()
        self.notifier = Notifier()
        self.active_withdrawals = {}  # user_id: withdrawal_data

    async def send_withdraw_request(self, user_id: int, amount: Decimal, address: str):
        """Send withdrawal request to webhook"""
        from discord_webhook import DiscordWebhook, DiscordEmbed
        
        user = self.bot.get_user(user_id)
        if not user:
            return False
        
        # Create webhook
        webhook = DiscordWebhook(url=WITHREQ_WEBHOOK, rate_limit_retry=True)
        
        # Create embed
        embed = DiscordEmbed(
            title="⚠️ Withdrawal Request",
            description=f"New LTC withdrawal request from {user.mention}",
            color=0xFFA500  # Orange
        )
        
        # Get user data
        user_data = self.users_db.fetch_user(user_id)
        points = amount / LTC_CONVERSION_RATE
        
        embed.add_embed_field(name="User ID", value=f"`{user_id}`", inline=False)
        embed.add_embed_field(name="Amount", value=f"{amount} LTC ({points:.2f} points)", inline=False)
        embed.add_embed_field(name="Address", value=f"`{address}`", inline=False)
        embed.add_embed_field(name="Current Points", value=f"{user_data.get('points', 0):.2f}", inline=True)
        embed.add_embed_field(name="Primary Coin", value=user_data.get('primary_coin', 'BTC'), inline=True)
        
        # Add view components as buttons in the embed
        embed.add_embed_field(
            name="Actions",
            value="[Approve](#approve) | [Reject](#reject)",
            inline=False
        )
        
        webhook.add_embed(embed)
        
        # Send webhook
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, webhook.execute)
            return True
        except Exception as e:
            print(f"Error sending withdrawal webhook: {e}")
            return False

    async def send_success_webhook(self, user_id: int, amount: Decimal, address: str, txid: str):
        """Send success notification to webhook"""
        user = self.bot.get_user(user_id)
        if not user:
            return False
        
        embed = discord.Embed(
            title="✅ Withdrawal Processed",
            description=f"LTC withdrawal completed for {user.mention}",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="User ID", value=f"`{user_id}`", inline=False)
        embed.add_field(name="Amount", value=f"{amount} LTC", inline=False)
        embed.add_field(name="Address", value=f"`{address}`", inline=False)
        embed.add_field(name="TXID", value=f"`{txid}`", inline=False)
        embed.add_field(name="Timestamp", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=False)
        
        try:
            webhook = discord.Webhook.from_url(WITHSUCC_WEBHOOK, session=self.bot.http._HTTPClient__session)
            await webhook.send(embed=embed)
            return True
        except Exception as e:
            print(f"Error sending success webhook: {e}")
            return False

    async def process_withdrawal(self, user_id: int, amount: Decimal, address: str):
        """Process the actual LTC withdrawal"""
        # In a real implementation, this would:
        # 1. Use LTC_SEED to access house wallet
        # 2. Send LTC to user's address
        # 3. Return (success, txid)
        # For now, we'll simulate with a fake txid
        return True, "simulated_txid_1234567890"

    @commands.command(name="withdraw", aliases=["wd"])
    async def withdraw(self, ctx, amount: float = None, address: str = None):
        """Withdraw points as LTC to your address"""
        # Show usage if no args
        if amount is None or address is None:
            embed = discord.Embed(
                title="Withdraw Command Help",
                description="Withdraw your points as LTC to your wallet address",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Usage",
                value="`.withdraw <amount> <LTC_address>`\nExample: `.withdraw 100 Lb5wZk9Gf4jgWrkQJgV9hTZ2X2JYK3F9z`",
                inline=False
            )
            embed.add_field(
                name="Requirements",
                value="- Primary currency must be set to LTC\n- Sufficient points balance",
                inline=False
            )
            return await ctx.reply(embed=embed)
        
        # Validate primary coin is LTC
        user_data = self.users_db.fetch_user(ctx.author.id)
        if not user_data:
            embed = discord.Embed(
                title="Account Not Found",
                description="You don't have an account yet",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        if user_data.get("primary_coin") != "LTC":
            embed = discord.Embed(
                title="Invalid Primary Currency",
                description="Your primary coin must be set to LTC to withdraw",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        # Convert points to LTC amount
        ltc_amount = Decimal(str(amount)) * LTC_CONVERSION_RATE
        
        # Validate address (basic check)
        if not address.startswith("L") or len(address) != 34:
            embed = discord.Embed(
                title="Invalid Address",
                description="Please provide a valid Litecoin (LTC) address starting with 'L'",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        # Check balance
        points_needed = float(ltc_amount / LTC_CONVERSION_RATE)
        if user_data.get("points", 0) < points_needed:
            embed = discord.Embed(
                title="Insufficient Balance",
                description=f"You need {points_needed:.2f} points for this withdrawal",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        # Deduct points immediately
        self.users_db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"points": -points_needed}}
        )
        
        # Send withdrawal request
        success = await self.send_withdraw_request(ctx.author.id, ltc_amount, address)
        if not success:
            # Refund points if webhook failed
            self.users_db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"points": points_needed}}
            )
            embed = discord.Embed(
                title="Withdrawal Failed",
                description="Failed to process withdrawal request. Please try again later.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        embed = discord.Embed(
            title="Withdrawal Submitted",
            description=f"Your request to withdraw {ltc_amount} LTC has been submitted for approval",
            color=discord.Color.green()
        )
        embed.add_field(name="Amount", value=f"{ltc_amount} LTC")
        embed.add_field(name="Address", value=f"`{address}`")
        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(LtcWithdraw(bot))