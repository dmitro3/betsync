
import discord
from discord.ext import commands
import datetime
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
import re

class CopyStatusView(discord.ui.View):
    def __init__(self, required_status: str):
        super().__init__(timeout=300)
        self.required_status = required_status

    @discord.ui.button(label="Copy Status Text", style=discord.ButtonStyle.primary, emoji="📋")
    async def copy_status(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📋 | Copy This Status",
            description=f"Copy and paste this exact text into your Discord status:\n\n```{self.required_status}```",
            color=0x00FFAE
        )
        embed.add_field(
            name="How to set your status:",
            value="1. Click on your profile picture\n2. Click 'Set a custom status'\n3. Paste the text above\n4. Save your status",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _normalize_status_text(self, text: str) -> str:
        """Normalize status text by converting to lowercase and removing extra spaces"""
        if not text:
            return ""
        # Convert to lowercase and replace multiple spaces with single spaces
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        return normalized

    def _check_deposit_requirement(self, user_data: dict) -> tuple[bool, float]:
        """Check if user has deposited more than 1 point. Returns (requirement_met, total_points)"""
        # Check both history and a persistent deposit flag
        history = user_data.get('history', [])
        total_deposit_points = 0
        
        # Calculate total points from all deposit types in history
        for entry in history:
            if entry and entry.get('type') in ['btc_deposit', 'ltc_deposit', 'eth_deposit', 'usdt_deposit', 'sol_deposit']:
                # Get points from deposit entry - check both possible field names
                points_credited = entry.get('points_credited', entry.get('points_earned', 0))
                total_deposit_points += points_credited
        
        # Also check for a persistent deposit tracker (in case history is cleared)
        lifetime_deposits = user_data.get('lifetime_deposit_points', 0)
        
        # Use the higher of the two values
        final_deposit_total = max(total_deposit_points, lifetime_deposits)
        
        return final_deposit_total > 1, final_deposit_total

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

        # Check 1: Deposited more than 1 point (improved persistence)
        deposit_met, total_deposit_points = self._check_deposit_requirement(user_data)
        
        if deposit_met:
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

        # Check 4: Custom status must start with specified text (case-insensitive, space-tolerant)
        required_status_start = "Best Crypto Casino .gg/betsync"
        required_status_normalized = self._normalize_status_text(required_status_start)
        custom_status_met = False
        
        if member and member.activities:
            for activity in member.activities:
                if isinstance(activity, discord.CustomActivity) and activity.name:
                    user_status_normalized = self._normalize_status_text(activity.name)
                    if user_status_normalized.startswith(required_status_normalized):
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
            # Show requirements not met with copy button for status
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Daily Reward Requirements",
                description=f"You don't meet all requirements for the daily reward:\n\n{requirements_text}",
                color=0xFF0000
            )
            embed.set_footer(text="Complete all requirements to claim your daily reward")
            
            # Add copy button view if status requirement is not met
            view = None
            if not custom_status_met:
                view = CopyStatusView(required_status_start)
            
            await loading_message.edit(embed=embed, view=view)
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
