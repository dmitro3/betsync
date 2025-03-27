import discord
import datetime
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji


class Tip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.point_value = 0.0212  # USD value of 1 point

    @commands.command(aliases=["give", "donate"])
    async def tip(self, ctx, user: discord.Member = None, amount=None):
        """Tip other users with points

        Usage:
        - !tip @user <amount>
        - !tip <user_id> <amount>
        - Reply to a message with !tip <amount>
        """
        if ctx.message.reference and ctx.message.reference.resolved:
            # Handle reply-based tip
            recipient = ctx.message.reference.resolved.author
            if amount is None and user is not None:
                # In reply mode, the first argument is the amount
                amount = user
                user = None
            elif amount is None and user is None:
                return await self.show_usage(ctx)
        else:
            # Handle regular command
            if user is None:
                return await self.show_usage(ctx)
            
            if amount is None:
                return await self.show_usage(ctx)

            recipient = user

        # Prevent self-tips
        if recipient.id == ctx.author.id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Cannot Tip Yourself",
                description="You cannot tip yourself. Please select another user.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Prevent bot tips
        if recipient.bot:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Cannot Tip Bots",
                description="You cannot tip bot accounts.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Try to parse amount
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Amount",
                description="Please enter a valid positive number for the tip amount.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check if sender has an account
        db = Users()
        sender_data = db.fetch_user(ctx.author.id)
        if not sender_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Required",
                description="You need an account to tip others. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check if recipient has an account
        recipient_data = db.fetch_user(recipient.id)
        if not recipient_data:
            # Auto-register recipient
            dump = {"discord_id": recipient.id, "points": 0, "history": [], 
                   "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, 
                   "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost': 0}
            db.register_new_user(dump)
            recipient_data = db.fetch_user(recipient.id)

        # Check if sender has enough balance
        sender_balance = sender_data.get("points", 0)
        if sender_balance < amount:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Balance",
                description=f"You don't have enough points. Your balance: **{sender_balance:.2f} points**",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Process the tip
        # Get sender's primary currency
        sender_primary_coin = sender_data.get("primary_coin", "BTC")
        
        # Deduct from sender
        db.update_balance(ctx.author.id, sender_balance - amount, "points", "$set")
        
        # Instead of adding to recipient's primary currency, add directly to their wallet in sender's currency
        # First get recipient's wallet
        recipient_wallet = recipient_data.get("wallet", {
            "BTC": 0,
            "SOL": 0,
            "ETH": 0,
            "LTC": 0,
            "USDT": 0
        })
        
        # Calculate crypto value of the amount
        crypto_values = {
            "BTC": 0.00000024,   # 1 point = 0.00000024 btc
            "LTC": 0.00023,      # 1 point = 0.00023 ltc
            "ETH": 0.000010,     # 1 point = 0.000010 eth
            "USDT": 0.0212,      # 1 point = 0.0212 usdt
            "SOL": 0.0001442     # 1 point = 0.0001442 sol
        }
        
        # Calculate crypto amount to add to recipient's wallet
        crypto_amount = amount * crypto_values[sender_primary_coin]
        
        # Add to recipient's wallet in sender's currency
        current_wallet_amount = recipient_wallet.get(sender_primary_coin, 0)
        new_wallet_amount = current_wallet_amount + crypto_amount
        
        # Update recipient's wallet
        db.collection.update_one(
            {"discord_id": recipient.id},
            {"$set": {f"wallet.{sender_primary_coin}": new_wallet_amount}}
        )
        
        # If the recipient's primary coin is the same as the sender's,
        # we also need to update their points to reflect the new wallet value
        recipient_primary_coin = recipient_data.get("primary_coin", "BTC")
        if recipient_primary_coin == sender_primary_coin:
            recipient_points = recipient_data.get("points", 0)
            new_recipient_points = recipient_points + amount
            db.update_balance(recipient.id, new_recipient_points, "points", "$set")
        
        # Record in history for both users
        timestamp = int(datetime.datetime.now().timestamp())

        # Sender history (sent tip)
        sender_history = {
            "type": "tip_sent",
            "amount": amount,
            "currency": "points",
            "recipient": recipient.id,
            "timestamp": timestamp
        }
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$push": {"history": {"$each": [sender_history], "$slice": -100}}}
        )

        # Recipient history (received tip)
        recipient_history = {
            "type": "tip_received",
            "amount": amount,
            "currency": "points",
            "sender": ctx.author.id,
            "timestamp": timestamp
        }
        db.collection.update_one(
            {"discord_id": recipient.id},
            {"$push": {"history": {"$each": [recipient_history], "$slice": -100}}}
        )

        # Send success message
        embed = discord.Embed(
            title=":gift: Tip Sent Successfully!",
            description=f"You sent **{amount:.2f} points** to {recipient.mention}",
            color=0x00FFAE
        )
        embed.add_field(
            name="Your New Balance",
            value=f"**{(sender_balance - amount):.2f} points** ({sender_primary_coin})",
            inline=True
        )
        embed.add_field(
            name="USD Value",
            value=f"**${(amount * self.point_value):.2f}**",
            inline=True
        )
        embed.add_field(
            name="Currency Sent",
            value=f"The points were added to {recipient.mention}'s **{sender_primary_coin}** wallet.",
            inline=False
        )
        embed.set_footer(text="BetSync Casino • Tipping System", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)

        # Notify recipient
        try:
            crypto_amount = amount * crypto_values[sender_primary_coin]
            recipient_embed = discord.Embed(
                title=":tada: You Received a Tip!",
                description=f"{ctx.author.mention} sent you **{amount:.2f} points** in **{sender_primary_coin}**!",
                color=0x00FFAE
            )
            recipient_embed.add_field(
                name="Added to Your Wallet",
                value=f"**{crypto_amount:.8f} {sender_primary_coin}**",
                inline=True
            )
            recipient_embed.add_field(
                name="USD Value",
                value=f"**${(amount * self.point_value):.2f}**",
                inline=True
            )
            recipient_embed.add_field(
                name="How to View",
                value=f"Use `!bal {sender_primary_coin}` to switch to this currency and see your updated balance.",
                inline=False
            )
            recipient_embed.set_footer(text="BetSync Casino • Tipping System", icon_url=self.bot.user.avatar.url)
            await recipient.send(embed=recipient_embed)
        except:
            # If DM fails, just continue without notification
            pass

    async def show_usage(self, ctx):
        """Show command usage information"""
        embed = discord.Embed(
            title=":bulb: How to Use `!tip`",
            description="Send points to another user.",
            color=0xFFD700
        )
        embed.add_field(
            name="Usage Options",
            value=(
                "**Direct Mention:**\n`!tip @user 100`\n\n"
                "**User ID:**\n`!tip 123456789012345678 50`\n\n"
                "**Reply to Message:**\n`!tip 75` (as a reply)\n\n"
                "**Shortcuts:**\n"
                "`!give` and `!donate` also work as aliases."
            ),
            inline=False
        )
        embed.add_field(
            name="Tips",
            value=(
                "• Amount must be a positive number\n"
                "• You can't tip yourself or bots\n"
                "• The recipient will be notified by DM"
            ),
            inline=False
        )
        embed.set_footer(text="BetSync Casino • Tipping System", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Tip(bot))