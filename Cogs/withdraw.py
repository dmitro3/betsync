
import discord
from discord.ext import commands
from Cogs.utils.mongo import Users

class Withdraw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users_db = Users()

    @commands.command(name="withdraw", aliases=["w"])
    async def withdraw(self, ctx, *, args: str = None):
        """Unified withdraw command that routes to BTC or LTC based on primary currency"""
        user_id = ctx.author.id
        user_data = self.users_db.fetch_user(user_id)
        
        if not user_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Not Found",
                description="No account found. Please play a game first.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        primary_coin = user_data.get("primary_coin")
        
        if primary_coin == "BTC":
            # Route to BTC withdraw
            btc_cog = self.bot.get_cog("BtcWithdraw")
            if btc_cog:
                await btc_cog.withdraw(ctx, args=args)
            else:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Service Unavailable",
                    description="BTC withdrawal service is currently unavailable.",
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
        elif primary_coin == "LTC":
            # Route to LTC withdraw
            ltc_cog = self.bot.get_cog("LtcWithdraw")
            if ltc_cog:
                await ltc_cog.ltcwithdraw(ctx, args=args)
            else:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Service Unavailable",
                    description="LTC withdrawal service is currently unavailable.",
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
        else:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | No Primary Currency",
                description="Please set your primary currency first:\n\n"
                          "• For BTC: `!bal BTC`\n"
                          "• For LTC: `!bal LTC`\n\n"
                          "Then use `!withdraw <amount> <address>`",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(Withdraw(bot))
