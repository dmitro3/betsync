import discord
from discord.ext import commands

class Deposit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="deposit", aliases=["dep", "depo"])
    async def deposit(self, ctx, currency: str = None):
        """Route to the appropriate deposit command based on currency"""
        if not currency:
            # Show general deposit menu
            embed = discord.Embed(
                title="<:wallet:1339343483089063976> Cryptocurrency Deposits",
                description="Deposit supported cryptocurrencies to receive points",
                color=0x00FFAE
            )
            embed.add_field(
                name="Supported Cryptocurrencies",
                value=(
                    "<:btc:1339343483089063976> BTC (`.dep btc`)\n"
                    "<:ltc:1339343445675868191> LTC (`.dep ltc`)\n"
                    "<:eth:1340981832799485985> ETH\n"
                    "<:usdt:1340981835563401217> USDT\n"
                    "<:sol:1340981839497793556> SOL"
                ),
                inline=True
            )
            embed.add_field(
                name="Conversion Rates",
                value=(
                    "1 point = 0.00000024 BTC\n"
                    "1 point = 0.00023 LTC\n"
                    "1 point = 0.000010 ETH\n"
                    "1 point = 0.0212 USDT\n"
                    "1 point = 0.0001442 SOL"
                ),
                inline=True
            )
            embed.set_footer(text="BetSync Casino")
            return await ctx.reply(embed=embed)

        currency = currency.lower()
        if currency == "btc":
            # Get BTC deposit command and invoke it
            btc_cog = self.bot.get_cog("BtcDeposit")
            if btc_cog:
                await btc_cog.deposit_btc(ctx, currency)
        elif currency == "ltc":
            # Get LTC deposit command and invoke it
            ltc_cog = self.bot.get_cog("LtcDeposit")
            if ltc_cog:
                await ltc_cog.deposit_ltc(ctx, currency)

def setup(bot):
    bot.add_cog(Deposit(bot))