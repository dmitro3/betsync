import discord
import json
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Load titles from static_data/titles.json
        with open('static_data/titles.json', 'r') as f:
            self.titles_data = json.load(f)

    def get_user_title(self, total_wagered):
        """Determine user's title based on total amount wagered"""
        titles = self.titles_data.get("titles", {})
        current_title = "Beginner"  # Default title

        # Find the highest title threshold the user has reached
        for title, data in titles.items():
            if total_wagered >= data.get("wagered", 0):
                if titles.get(current_title, {}).get("wagered", 0) <= data.get("wagered", 0):
                    current_title = title

        return current_title, titles.get(current_title, {}).get("description", "")

    def create_progress_bar(self, current, maximum, length=10):
        """Create a text-based progress bar"""
        filled_length = int(length * current / maximum) if maximum > 0 else 0
        bar = '█' * filled_length + '░' * (length - filled_length)
        percent = current / maximum * 100 if maximum > 0 else 0
        return f"{bar} {percent:.1f}%"

    @commands.command(aliases=["prof"])
    async def profile(self, ctx, user: discord.Member = None):
        """View your or another user's profile with stats and title"""
        # Get emojis
        emojis = emoji()
        loading_emoji = emojis["loading"]

        # Send loading message
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Loading Profile...",
            description="Please wait while we fetch the profile data.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # If no user is specified, use the command author
        if user is None:
            user = ctx.author

        # Fetch user data from database
        db = Users()
        user_data = db.fetch_user(user.id)

        if user_data == False:
            # User not found in database
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="This user doesn't have an account. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)

        # Calculate title and XP info
        total_wagered = user_data.get("total_spent", 0)
        title, title_description = self.get_user_title(total_wagered)
        current_xp = user_data.get('xp', 0)
        current_level = user_data.get('level', 1)
        xp_limit = round(10 * (1 + (current_level - 1) * 0.1))

        # Create minimalist embed with user information
        embed = discord.Embed(
            title=f"{user.name}'s Profile",
            color=0x00FFAE
        )

        # Set user avatar as thumbnail if available
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)

        # Create XP progress bar
        xp_progress = self.create_progress_bar(current_xp, xp_limit, length=15)

        # Add core profile info
        embed.add_field(
            name="Stats",
            value=(
                f"**Rank:** {user_data.get('rank', 0)}\n"
                f"**Level:** {current_level}\n"
                f"**XP Progress:** {current_xp}/{xp_limit}\n"
                f"```{xp_progress}```"
            ),
            inline=False
        )

        # Add balance information
        embed.add_field(
            name="Balance",
            value=(
                f"**Tokens:** {user_data.get('tokens', 0):.2f}\n"
                f"**Credits:** {user_data.get('credits', 0):.2f}"
            ),
            inline=True
        )

        # Add title information
        embed.add_field(
            name="Title",
            value=f"**{title}**",
            inline=True
        )

        # Set footer
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Delete loading message and send the profile
        await loading_message.delete()
        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(Profile(bot))