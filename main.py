import datetime
import os
import time
os.system("pip uninstall discord.py discord py-cord -y && pip install py-cord")
time.sleep(3)
os.system("clear")
import discord
import asyncio
from colorama import Fore, Back, Style
from discord.ext import commands
from pymongo import ReturnDocument
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
from dotenv import load_dotenv


"""
1 point = 0.00000024 btc
1 point = 0.00023 ltc
1 point = 0.000010 eth
1 point = 0.0212 usdt
1 point = 0.0001442 sol
"""

# Load environment variables
load_dotenv()

# Improved logging setup
print(f"{Fore.CYAN}[*] {Fore.WHITE}Starting BetSync Casino Bot...")

# Check if token exists
if not os.environ.get('TOKEN'):
    print(f"{Fore.RED}[!] {Fore.WHITE}ERROR: Discord token not found in environment variables!")
    print(f"{Fore.YELLOW}[*] {Fore.WHITE}Please make sure you have added a TOKEN secret in the Secrets tab.")
    exit(1)

# Initialize bot with intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["!", "."], intents=intents, case_insensitive=True)
bot.remove_command("help")

# List of cogs to load
print("DEBUG: Loading cogs...")
cogs = [
    "Cogs.guide", "Cogs.fetches", "Cogs.profile",
    "Cogs.start", "Cogs.currency", "Cogs.history", "Cogs.admin",
    "Cogs.deposit", "Cogs.withdraw",
    "Cogs.servers", "Cogs.tip", "Cogs.ltc_deposit", "Cogs.ltc_withdraw", "Cogs.btc_deposit", "Cogs.btc_withdraw", "Cogs.eth_usdt_deposit", "Cogs.games.crash", "Cogs.games.dice",
    "Cogs.games.coinflip", "Cogs.games.mines", "Cogs.games.penalty",
    "Cogs.games.wheel", "Cogs.games.progressivecf", "Cogs.games.crosstheroad", 
    "Cogs.games.tower", "Cogs.games.pump", "Cogs.games.limbo", 
    "Cogs.games.race", "Cogs.games.cases",
    "Cogs.games.hilo", "Cogs.games.poker", "Cogs.games.plinko", 
    "Cogs.games.keno", "Cogs.games.blackjack", "Cogs.games.baccarat",
    "Cogs.games.match", "Cogs.sol_deposit" # Added sol_deposit cog
]
# Import RegistrationView after bot initialization
from Cogs.start import RegistrationView

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="<:no:1344252518305234987> | invalid command",
            description="No such command found, type `!help` to get started",
            color=0xFF0000
        )
        await ctx.reply(embed=embed, delete_after=5)
        #print(f"{Fore.RED}[-] {Fore.WHITE} User {Fore.BLACK}{ctx.message.author}{Fore.WHITE} tried to use a non-existent command")
    else:
        
        print(f"{Fore.RED}[!] {Fore.WHITE}Command error: {Fore.RED}{error}")

@bot.event
async def on_guild_join(guild):
    try:
        db = Servers()
        dump = {
            "server_id": guild.id,
            "server_name": guild.name,
            "wallet":{
                "BTC":0,
                "LTC":0,
                "ETH":0,
                "SOL":0,
                "USDT":0
            },
            "giveaway_channel": None,
            "server_admins": [],
            "server_bet_history": [],
        }
        resp = db.new_server(dump)
        if resp:
            #print(f"{Fore.GREEN}[+] {Fore.WHITE}New Server Registered: {Fore.GREEN}{guild.name} ({guild.id}){Fore.WHITE}")
            rn = datetime.datetime.now().strftime("%X")
            print(f"{Back.CYAN}  {Style.DIM}{guild.id}{Style.RESET_ALL}{Back.RESET}{Fore.CYAN}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{Fore.GREEN}{dump} ({resp}){Fore.WHITE}{Style.RESET_ALL}  {Fore.MAGENTA}{guild.name}, new_sv{Fore.WHITE}")
    except Exception as e:
        pass #print(f"{Fore.RED}[!] {Fore.WHITE}Error registering server: {Fore.RED}{e}")

@bot.event
async def on_command(ctx):
    # Check if user is blacklisted
    async def bg():
        try:
            admin_cog = bot.get_cog("AdminCommands")
            if admin_cog and hasattr(admin_cog, 'blacklisted_ids') and ctx.author.id in admin_cog.blacklisted_ids:
                embed = discord.Embed(
                title="🚫 Access Denied",
                description="You have been blacklisted from using this bot.",
                color=0xFF0000
                )
                await ctx.reply(embed=embed)
                return

            # Check if user is registered
            db = Users()
            if not db.fetch_user(ctx.author.id):
                # Show registration panel instead of auto-registering
                embed = discord.Embed(
                    title="🔐 **Account Registration Required**",
                    description="**Welcome to BetSync Casino!** To start playing, you need to authorize your Discord account through our secure OAuth system.",
                    color=0x00FFAE
                )
                embed.add_field(
                    name="🎯 **Why Authorization?**",
                    value="• Secure account protection\n• Cross-platform synchronization\n• Enhanced security features\n• Backup & recovery options",
                    inline=False
                )
                embed.add_field(
                    name="🚀 **Get Started**",
                    value="Click the button below to authorize your account and start your casino journey!",
                    inline=False
                )
                embed.set_footer(text="BetSync Casino • Secure & Trusted")
                
                # Create view with authorization button
                view = RegistrationView()
                await ctx.reply(embed=embed, view=view)
                return
                
        except Exception as e:
            print(e)
    bg_task = asyncio.create_task(bg())
    await bg_task


@bot.event
async def on_ready():
    try:
        print(f"{Fore.GREEN}[+] {Fore.WHITE}Bot is online as {Fore.GREEN}{bot.user.name} ({bot.user.id}){Fore.WHITE}")
        print(f"{Fore.GREEN}[+] {Fore.WHITE}Servers: {Fore.GREEN}{len(bot.guilds)}{Fore.WHITE}")

        # Set bot status
        await bot.change_presence(activity=discord.Game(name="!help | BetSync Casino"))

        # Load cogs
        print(f"{Fore.CYAN}[*] {Fore.WHITE}Loading cogs...")
        for cog in cogs:
            try:
                bot.load_extension(cog)
                print(f"{Fore.GREEN}[+] {Fore.WHITE}Loaded Cog: {Fore.GREEN}{cog}{Fore.WHITE}")
            except Exception as e:
                print(f"{Fore.RED}[-] {Fore.WHITE}Failed to load cog {Fore.RED}{cog}{Fore.WHITE}: {e}")

        print(f"{Fore.GREEN}[+] {Fore.WHITE}Bot initialization complete!")
        await asyncio.sleep(3)
        os.system("clear")
        print("""

  ____       _    _____                  _____  ____  
 |  _ \     | |  / ____|                |  __ \|  _ \ 
 | |_) | ___| |_| (___  _   _ _ __   ___| |  | | |_) |
 |  _ < / _ \ __|\___ \| | | | '_ \ / __| |  | |  _ < 
 | |_) |  __/ |_ ____) | |_| | | | | (__| |__| | |_) |
 |____/ \___|\__|_____/ \__, |_| |_|\___|_____/|____/ 
                         __/ |                        
                        |___/                         
                        """)
        now = datetime.datetime.now()
        rn = now.strftime("%X")
        print(f"{Back.CYAN}     {Style.DIM}NOHASH{Style.RESET_ALL}{Back.RESET}{Fore.CYAN}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}BetsyncDB Initialized{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[!] {Fore.WHITE}Error in on_ready: {Fore.RED}{e}")

# Start the bot
print(f"{Fore.CYAN}[*] {Fore.WHITE}Starting bot...")
try:
    bot.run(os.environ['TOKEN'])
except discord.errors.LoginFailure:
    print(f"{Fore.RED}[!] {Fore.WHITE}ERROR: Invalid token provided. Please check your TOKEN in the Secrets tab.")
except Exception as e:
    print(f"{Fore.RED}[!] {Fore.WHITE}Error starting bot: {Fore.RED}{e}")