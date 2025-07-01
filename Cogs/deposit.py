import discord
from discord.ext import commands

class Deposit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dep", aliases=["deposit"])
    async def deposit(self, ctx, currency: str = None):
        """Main deposit command that routes to specific currency deposit commands."""
        if not currency:
            embed = discord.Embed(
                title="💰 Deposit Commands",
                description="Choose a currency to deposit:",
                color=0x00FF00
            )
            embed.add_field(name="Bitcoin", value="`!dep btc`", inline=True)
            embed.add_field(name="Litecoin", value="`!dep ltc`", inline=True)
            embed.add_field(name="Ethereum", value="`!dep eth`", inline=True)
            embed.add_field(name="USDT", value="`!dep usdt`", inline=True)
            embed.add_field(name="Solana", value="`!dep sol`", inline=True)
            embed.set_footer(text="BetSync Casino")
            await ctx.reply(embed=embed)
            return

        currency = currency.upper()
        
        if currency == "BTC":
            btc_cog = self.bot.get_cog("BtcDeposit")
            if btc_cog:
                await btc_cog.deposit_btc(ctx)
            else:
                await ctx.reply("BTC deposit is currently unavailable.")
                
        elif currency == "LTC":
            ltc_cog = self.bot.get_cog("LtcDeposit")
            if ltc_cog:
                await ltc_cog.deposit_ltc(ctx)
            else:
                await ctx.reply("LTC deposit is currently unavailable.")
                
        elif currency in ["ETH", "USDT"]:
            eth_cog = self.bot.get_cog("EthUsdtDeposit")
            if eth_cog:
                await eth_cog.deposit_eth_usdt(ctx, currency)
            else:
                await ctx.reply(f"{currency} deposit is currently unavailable.")
                
        elif currency == "SOL":
            sol_cog = self.bot.get_cog("SolDeposit")
            if sol_cog:
                await sol_cog.deposit_sol(ctx)
            else:
                await ctx.reply("SOL deposit is currently unavailable.")
                
        else:
            embed = discord.Embed(
                title="❌ Invalid Currency",
                description="Supported currencies: BTC, LTC, ETH, USDT, SOL",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)

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
                    "<:eth:1340981832799485985> ETH (`.dep eth`)\n"
                    "<:usdt:1340981835563401217> USDT (`.dep usdt`)\n"
                    "<:sol:1340981839497793556> SOL (`.dep sol`)" # Added command usage
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
        elif currency in ["eth", "usdt"]:
            # Get ETH/USDT deposit command and invoke it
            eth_usdt_cog = self.bot.get_cog("EthUsdtDeposit")
            if eth_usdt_cog:
                if currency == "eth":
                    await eth_usdt_cog.deposit_eth(ctx, currency)
                else:
                    await eth_usdt_cog.deposit_usdt(ctx, currency)
        elif currency == "sol":
            # Get SOL deposit command and invoke it
            sol_cog = self.bot.get_cog("SolDeposit")
            if sol_cog:
                await sol_cog.deposit_sol(ctx, currency)

def setup(bot):
    bot.add_cog(Deposit(bot))