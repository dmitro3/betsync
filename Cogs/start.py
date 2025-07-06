import discord
from discord.ext import commands
from Cogs.utils.emojis import emoji
from Cogs.utils.mongo import Users

class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="🔐 Authorize Account", style=discord.ButtonStyle.green, emoji="🚀")
    async def authorize(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔐 **Account Authorization**",
            description="**Click the link below to securely authorize your Discord account:**",
            color=0x00FFAE
        )
        embed.add_field(
            name="🔗 **Authorization Link**",
            value="[**Click Here to Authorize**](https://discord.com/oauth2/authorize?client_id=1336709318325833769&response_type=code&redirect_uri=https%3A%2F%2Fbetsync-admin.com%2Fauth%2Fcallback&scope=identify+guilds.join)",
            inline=False
        )
        embed.add_field(
            name="⚡ **After Authorization**",
            value="• Your account will be automatically registered\n• You'll have access to all casino features\n• You can start playing immediately",
            inline=False
        )
        embed.add_field(
            name="🛡️ **Privacy & Security**",
            value="We only request basic Discord profile information. Your data is secure and never shared with third parties.",
            inline=False
        )
        embed.set_footer(text="BetSync Casino • Secure OAuth Authorization")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class MainView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__()
        self.bot = bot
        self.user = user

    @discord.ui.button(label="🔐 Authorize Account", style=discord.ButtonStyle.green)
    async def signup(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if user is already registered
        response = Users().fetch_user(self.user.id)

        if response:
            embed = discord.Embed(
                title="✅ **Account Already Authorized**",
                color=0x00FFAE,
                description="**You are already registered and ready to play!**"
            )
            embed.add_field(
                name="🎰 Get Started",
                value="Type `!help` or `!guide` to start your casino journey!",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="🔐 **Account Authorization Required**",
                description="**Click the link below to securely authorize your Discord account:**",
                color=0x00FFAE
            )
            embed.add_field(
                name="🔗 **Authorization Link**",
                value="[**Click Here to Authorize**](https://discord.com/oauth2/authorize?client_id=1336709318325833769&response_type=code&redirect_uri=https%3A%2F%2Fbetsync-admin.com%2Fauth%2Fcallback&scope=identify+guilds.join)",
                inline=False
            )
            embed.add_field(
                name="⚡ **After Authorization**",
                value="• Your account will be automatically registered\n• You'll have access to all casino features\n• You can start playing immediately",
                inline=False
            )

        embed.set_footer(text="BetSync Casino • Secure OAuth Authorization", icon_url=self.user.avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class GamePaginator(discord.ui.View):
    def __init__(self, embeds):
        super().__init__(timeout=60)
        self.embeds = embeds
        self.current_page = 0

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.embeds[self.current_page])

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.embeds[self.current_page])

class Start(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.command_descriptions = {
            # Profile & Stats
            "profile": "View your casino profile and statistics",
            #"history": "View your transaction history",
            #"stats": "View your gambling statistics",
            "leaderboard": "View top players and your rank.",

            # Currency & Banking
            "deposit": "Deposit currency for tokens",
            "withdraw": "Withdraw your credits to crypto",
            "tip": "Send tokens to other players",

            # Information
            #"guide": "View the complete casino guide",
            "help": "Quick overview of main commands",
            "commands": "Show all available commands",

            # Account Management
            #"signup": "Create a new casino account",
            "rakeback": "Get cashback on your bets",

            # Server Features
            #"serverstats": "View server statistics and earnings",
            #"serverbethistory": "View server's betting history",
            #"airdrop": "Create a token/credit airdrop",

            # Lottery System
            #"loterry": "View or participate in the current lottery",
            #"loterryhistory": "View past lottery results",

            # Games List 
            "games": "List all available casino games",
            #"multiplayer": "View available PvP games"
        }

        self.game_descriptions = {
            "blackjack": "A classic casino card game where you compete against the dealer to get closest to 21",
            "baccarat": "An elegant card game where you bet on either the Player or Banker hand",
            "coinflip": "A simple heads or tails game with 2x payout",
            "crash": "Watch the multiplier rise and cash out before it crashes",
            #"carddraw": "Higher card wielder wins (PvP Only)",
            "cases": "Draw multipliers from cases",
            "crosstheroad": "Guide your character across increasing multipliers without crashing",
            "dice": "Roll the dice and win based on the number prediction",
            "hilo": "Predict if the next card will be higher or lower",
            "keno": "Pick numbers and win based on how many match the draw",
            "limbo": "Choose a target multiplier and win if the result goes over it",
            "match": "Match pairs of cards to win prizes",
            "mines": "Navigate through a minefield collecting gems without hitting mines",
            "penalty": "Score penalty kicks to win tokens",
            "plinko": "Drop balls through pegs for random multipliers",
            "poker": "Classic Texas Hold'em poker against other players",
            "progressivecf": "Coinflip with increasing multipliers on win streaks",
            "pump": "Pump up the balloon but don't let it pop",
            "race": "Bet on racers and win based on their position",
            #"rockpaperscissors": "Play the classic game against other players (PvP + PvE)",
            #'tictactoe': "Play classic tictactoe with friends (PvP Only)",
            "tower": "Climb the tower avoiding wrong choices",
            "wheel": "Spin the wheel for various multipliers"
        }


    @commands.command(name="tnc", aliases=["terms", "tos"])
    async def tnc(self, ctx):
        embeds = []
        fields_per_page = 4

        tnc_fields = [
            ("1. Introduction", "Welcome to betsync – a Discord bot designed to simulate betting and gambling-style games on Discord servers. By using betsync, you agree to abide by these Terms & Conditions ('Terms'). If you do not agree with any part of these Terms, please do not use the bot."),
            ("2. Acceptance of Terms", "By accessing or using betsync, you confirm that you have read, understood, and agree to be bound by these Terms and any future amendments."),
            ("3. Eligibility", "• You must be at least 18 years old, or the legal age in your jurisdiction, to use betsync.\n• By using betsync, you confirm that you meet this age requirement and have the legal capacity to enter this agreement."),
            ("4. Use of betsync", "• Purpose: betsync is intended for entertainment purposes only.\n• Betting Simulation: The bot simulates gambling activities with an RTP of 98.5%.\n• Randomness: All game outcomes are determined by a Random Number Generator (RNG)."),
            ("5. Virtual Currency & Wagering", "• Virtual Nature: Any currency or points used by betsync are virtual and hold no real-world monetary value.\n• Wagering: All bets placed are for simulation purposes only."),
            ("6. Responsible Gambling", "• Gambling—even in a simulated environment—carries inherent risks.\n• Please use betsync responsibly.\n• If you suspect you have a gambling problem, please seek professional help."),
            ("7. Limitation of Liability", "• 'As Is' Service: betsync is provided on an 'as is' basis without warranties.\n• No Liability: The creators will not be liable for any damages arising from your use."),
            ("8. Modifications and Termination", "• Changes: We reserve the right to modify these Terms at any time.\n• Termination: We may suspend or terminate your access at our sole discretion."),
            ("9. Intellectual Property", "All content, trademarks, and intellectual property related to betsync are owned by its creators. You are granted a non-exclusive license to use betsync solely for personal purposes."),
            ("10. Governing Law", "These Terms are governed by applicable laws and any disputes shall be resolved through informal negotiations first.")
        ]

        # Create pages
        for i in range(0, len(tnc_fields), fields_per_page):
            page_fields = tnc_fields[i:i + fields_per_page]

            embed = discord.Embed(
                title="BetSync Terms & Conditions",
                description="Last Updated: March 2025",
                color=0x00FFAE
            )

            for name, value in page_fields:
                embed.add_field(name=name, value=value, inline=False)

            embed.set_footer(text=f"Page {i//fields_per_page + 1}/{(len(tnc_fields) + fields_per_page - 1)//fields_per_page}")
            embeds.append(embed)

        view = GamePaginator(embeds)
        await ctx.reply(embed=embeds[0], view=view)

    @commands.command(name="signup")
    async def signup(self, ctx):
        # Check if user is already registered
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        
        if user_data:
            embed = discord.Embed(
                title="✅ **Account Already Authorized**",
                description="**You are already registered and ready to play!**",
                color=0x00FFAE
            )
            embed.add_field(
                name="🎰 Get Started",
                value="Type `!help` or `!guide` to start your casino journey!",
                inline=False
            )
            await ctx.reply(embed=embed)
        else:
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
            embed.set_footer(text="BetSync Casino • Secure & Trusted", icon_url=self.bot.user.avatar.url)
            
            view = RegistrationView()
            await ctx.reply(embed=embed, view=view)

def setup(bot):
    bot.add_cog(Start(bot))