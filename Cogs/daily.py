
import discord
from discord.ext import commands
import datetime
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji

class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["daily", "dr"])
    async def dailyreward(self, ctx):
        """Claim your daily reward - requires meeting all criteria"""
        # Get emojis
        emojis = emoji()
        loading_emoji = emojis["loading"]

        # Send loading message
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Checking Daily Reward Status...",
            description="Please wait while we verify your eligibility.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Get user data
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        
        if not user_data:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Required",
                description=f"{ctx.author.mention} needs an account to claim daily rewards. Use a command to create one.",
                color=0xFF0000
            )
            await loading_message.edit(embed=error_embed)
            return

        # Check if user has already claimed today
        last_daily_claim = user_data.get('last_daily_claim')
        today = datetime.datetime.now().date()
        
        if last_daily_claim:
            # Parse the stored date string
            try:
                last_claim_date = datetime.datetime.fromisoformat(last_daily_claim).date()
                if last_claim_date >= today:
                    error_embed = discord.Embed(
                        title="<:no:1344252518305234987> | Already Claimed",
                        description="You have already claimed your daily reward today. Come back tomorrow!",
                        color=0xFF0000
                    )
                    await loading_message.edit(embed=error_embed)
                    return
            except:
                # If parsing fails, allow the claim to proceed
                pass

        # Initialize requirement checks
        requirements = []
        all_met = True

        # Check 1: Deposited more than 1 point (check history for deposits)
        history = user_data.get('history', [])
        total_deposit_points = 0
        
        # Calculate total points from all deposit types
        for entry in history:
            if entry and entry.get('type') in ['btc_deposit', 'ltc_deposit', 'eth_deposit', 'usdt_deposit', 'sol_deposit']:
                # Get points from deposit entry
                points_earned = entry.get('points_earned', 0)
                total_deposit_points += points_earned
        
        if total_deposit_points > 1:
            requirements.append("✅ Deposited more than 1 point")
        else:
            requirements.append("❌ Deposited more than 1 point")
            all_met = False

        # Check 2: Minimum 1 point in balance
        points_balance = user_data.get('points', 0)
        if points_balance >= 1:
            requirements.append("✅ Minimum 1 point in balance")
        else:
            requirements.append("❌ Minimum 1 point in balance")
            all_met = False

        # Check 3: User must be online
        member = ctx.guild.get_member(ctx.author.id)
        if member and member.status != discord.Status.offline:
            requirements.append("✅ You must be online")
        else:
            requirements.append("❌ You must be online")
            all_met = False

        # Check 4: Custom status must start with specified text
        required_status_start = "Best Crypto Casino .gg/kNp4ZYDYSq"
        custom_status_met = False
        
        if member and member.activity:
            for activity in member.activities:
                if isinstance(activity, discord.CustomActivity) and activity.name:
                    if activity.name.startswith(required_status_start):
                        custom_status_met = True
                        break
        
        if custom_status_met:
            requirements.append(f"✅ Your custom status must start with `{required_status_start}`")
        else:
            requirements.append(f"❌ Your custom status must start with `{required_status_start}`")
            all_met = False

        # Create requirements display
        requirements_text = "\n".join(requirements)

        if not all_met:
            # Show requirements not met
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Daily Reward Requirements",
                description=f"You don't meet all requirements for the daily reward:\n\n{requirements_text}",
                color=0xFF0000
            )
            embed.set_footer(text="Complete all requirements to claim your daily reward")
            await loading_message.edit(embed=embed)
            return

        # All requirements met - give reward
        reward_amount = 1.0

        # Add the reward to user's points balance
        db.update_balance(ctx.author.id, reward_amount, "points", "$inc")

        # Update last daily claim date
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$set": {"last_daily_claim": datetime.datetime.now().isoformat()}}
        )

        # Success embed
        success_embed = discord.Embed(
            title="<:yes:1355501647538815106> | Daily Reward Claimed!",
            description=f"Congratulations! You've successfully claimed your daily reward of **{reward_amount} points**!\n\n{requirements_text}",
            color=0x00FFAE
        )
        success_embed.add_field(
            name="💰 Reward",
            value=f"**+{reward_amount} points** added to your balance!",
            inline=False
        )
        success_embed.set_footer(text="BetSync • Come back tomorrow for another daily reward!", icon_url=self.bot.user.avatar.url)
        
        await loading_message.edit(embed=success_embed)

def setup(bot):
    bot.add_cog(Daily(bot))
