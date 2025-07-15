
import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import process_bet_amount


class SlotsResultView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, slot_symbols, currency_used="points"):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.slot_symbols = slot_symbols
        self.author_id = ctx.author.id
        
        # Create 15 buttons (3 rows x 5 columns) with the final symbols
        for i in range(15):
            row = i // 5
            symbol = slot_symbols[i] if slot_symbols else "🎰"
            
            button = discord.ui.Button(
                emoji=symbol,
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=row
            )
            self.add_item(button)

    @discord.ui.button(label="🎰 Play Again", style=discord.ButtonStyle.success, row=3)
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ This is not your game!", ephemeral=True)

        # Disable the button to prevent spam
        button.disabled = True
        button.label = "⏳ Starting..."
        await interaction.response.edit_message(view=self)

        # Start a new game
        await self.cog.slots(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        # Disable all buttons after timeout
        for item in self.children:
            item.disabled = True


class SlotsSpinningView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
        # Create 15 spinning buttons
        for i in range(15):
            row = i // 5
            button = discord.ui.Button(
                emoji="<:slots:1333757726437806111>",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=row
            )
            self.add_item(button)


class SlotsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        
        # Premium slot symbols with better balance and visual appeal
        self.symbols = {
            "🍎": {"weight": 25, "payout": 1.2, "rarity": "Common"},
            "🍊": {"weight": 25, "payout": 1.2, "rarity": "Common"},
            "🍋": {"weight": 20, "payout": 1.5, "rarity": "Common"},
            "🍇": {"weight": 18, "payout": 2.0, "rarity": "Uncommon"},
            "🍒": {"weight": 15, "payout": 2.5, "rarity": "Uncommon"},
            "🔔": {"weight": 10, "payout": 4.0, "rarity": "Rare"},
            "💎": {"weight": 5, "payout": 8.0, "rarity": "Epic"},
            "🍀": {"weight": 1.5, "payout": 20.0, "rarity": "Legendary"},
            "🎰": {"weight": 0.5, "payout": 50.0, "rarity": "Mythic"}
        }

    def generate_slot_result(self):
        """Generate optimized 3x5 slot machine result"""
        symbol_list = []
        weights = []
        
        for symbol, data in self.symbols.items():
            symbol_list.append(symbol)
            weights.append(data["weight"])
        
        # Generate 15 symbols with slight bias for better player experience
        result = []
        for _ in range(15):
            symbol = random.choices(symbol_list, weights=weights)[0]
            result.append(symbol)
        
        return result

    def calculate_winnings(self, symbols, bet_amount):
        """Enhanced winning calculation with multiple paylines"""
        grid = [symbols[i:i+5] for i in range(0, 15, 5)]
        
        total_multiplier = 0
        winning_combinations = []
        
        # Horizontal paylines (3 rows)
        for row_idx, row in enumerate(grid):
            line_wins = self.check_payline(row, f"Row {row_idx + 1}")
            for win in line_wins:
                total_multiplier += win["multiplier"]
                winning_combinations.append(win)
        
        # Vertical paylines (5 columns)
        for col_idx in range(5):
            column = [grid[row][col_idx] for row in range(3)]
            line_wins = self.check_payline(column, f"Column {col_idx + 1}")
            for win in line_wins:
                total_multiplier += win["multiplier"]
                winning_combinations.append(win)
        
        # Diagonal paylines
        diagonals = [
            ([grid[0][0], grid[1][1], grid[2][2]], "Main Diagonal"),
            ([grid[0][2], grid[1][1], grid[2][0]], "Anti Diagonal"),
            ([grid[0][1], grid[1][2], grid[2][3]], "Upper Diagonal"),
            ([grid[0][3], grid[1][2], grid[2][1]], "Lower Diagonal")
        ]
        
        for diagonal_symbols, name in diagonals:
            line_wins = self.check_payline(diagonal_symbols, name)
            for win in line_wins:
                total_multiplier += win["multiplier"]
                winning_combinations.append(win)
        
        # Apply house edge (10% reduction)
        house_edge = 0.90
        final_multiplier = total_multiplier * house_edge
        winnings = bet_amount * final_multiplier
        
        return winnings, winning_combinations, final_multiplier

    def check_payline(self, line, line_name):
        """Check for winning combinations in a payline"""
        wins = []
        
        for symbol, data in self.symbols.items():
            count = line.count(symbol)
            if count >= 3:
                base_payout = data["payout"]
                
                # Bonus multipliers for 4+ matches
                if count == 4:
                    multiplier = base_payout * 1.5
                elif count == 5:
                    multiplier = base_payout * 2.5
                else:
                    multiplier = base_payout
                
                wins.append({
                    "symbol": symbol,
                    "count": count,
                    "multiplier": multiplier,
                    "line": line_name,
                    "rarity": data["rarity"]
                })
        
        return wins

    def create_beautiful_embed(self, title, description, color, bet_amount=None, winnings=None, 
                             multiplier=None, winning_combinations=None, footer_text=None):
        """Create a polished, professional-looking embed"""
        embed = discord.Embed(title=title, description=description, color=color)
        
        if bet_amount:
            embed.add_field(
                name="💰 Bet Amount", 
                value=f"`{bet_amount:.0f} points`", 
                inline=True
            )
        
        if winnings is not None:
            profit = winnings - (bet_amount or 0)
            profit_indicator = "📈" if profit > 0 else "📉" if profit < 0 else "➖"
            embed.add_field(
                name="🎉 Total Winnings", 
                value=f"`{winnings:.0f} points`", 
                inline=True
            )
            embed.add_field(
                name=f"{profit_indicator} Net Profit", 
                value=f"`{profit:+.0f} points`", 
                inline=True
            )
        
        if multiplier is not None and multiplier > 0:
            embed.add_field(
                name="🔥 Total Multiplier", 
                value=f"`{multiplier:.2f}x`", 
                inline=True
            )
        
        if winning_combinations:
            combinations_text = ""
            for combo in winning_combinations[:5]:  # Show max 5 combinations
                rarity_emoji = {
                    "Common": "⚪", "Uncommon": "🟢", "Rare": "🔵", 
                    "Epic": "🟣", "Legendary": "🟡", "Mythic": "🔴"
                }.get(combo["rarity"], "⚪")
                
                combinations_text += f"{rarity_emoji} **{combo['count']}x {combo['symbol']}** on {combo['line']} - `{combo['multiplier']:.1f}x`\n"
            
            if len(winning_combinations) > 5:
                combinations_text += f"*+{len(winning_combinations) - 5} more combinations...*"
            
            embed.add_field(
                name="🏆 Winning Combinations", 
                value=combinations_text or "None", 
                inline=False
            )
        
        embed.set_footer(
            text=footer_text or "🎰 BetSync Casino • Premium Slots Experience", 
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        
        return embed

    @commands.command(aliases=["slot"])
    async def slots(self, ctx, bet_amount: str = None):
        """🎰 Premium Slots - Spin the reels and win big!"""
        
        if not bet_amount:
            # Create beautiful help embed
            help_embed = discord.Embed(
                title="🎰 Premium Slots Machine",
                description=(
                    "**Experience the thrill of our premium slot machine!**\n"
                    "Match symbols across multiple paylines to win big!\n\n"
                    "**How to Play:**\n"
                    "• Use `!slots <amount>` to place your bet\n"
                    "• Match 3+ symbols on any payline to win\n"
                    "• Multiple paylines = bigger wins!\n\n"
                    "**Paylines Include:**\n"
                    "• 3 Horizontal rows\n"
                    "• 5 Vertical columns  \n"
                    "• 4 Diagonal lines\n\n"
                    "**Symbol Rarities & Base Payouts:**"
                ),
                color=0x00FFAE
            )
            
            # Add symbol information in a clean format
            symbol_info = ""
            for symbol, data in self.symbols.items():
                rarity_colors = {
                    "Common": "⚪", "Uncommon": "🟢", "Rare": "🔵",
                    "Epic": "🟣", "Legendary": "🟡", "Mythic": "🔴"
                }
                color_indicator = rarity_colors.get(data["rarity"], "⚪")
                symbol_info += f"{color_indicator} {symbol} **{data['rarity']}** - `{data['payout']:.1f}x`\n"
            
            help_embed.add_field(name="🎯 Symbols", value=symbol_info, inline=False)
            help_embed.add_field(
                name="💡 Pro Tips", 
                value="• 4 matches = 1.5x bonus\n• 5 matches = 2.5x bonus\n• Multiple wins stack!", 
                inline=False
            )
            help_embed.set_footer(text="🎰 Good luck and spin responsibly!")
            
            return await ctx.reply(embed=help_embed)

        # Check for ongoing games
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="⚠️ Game In Progress",
                description="You already have a slots game running! Please finish it first.",
                color=0xFFAA00
            )
            return await ctx.reply(embed=embed, delete_after=5)

        # Create initial loading embed
        loading_embed = discord.Embed(
            title="🎰 Initializing Slot Machine...",
            description="Setting up your premium gaming experience...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount
        db = Users()
        user_data = db.fetch_user(ctx.author.id)

        if not user_data:
            await loading_message.delete()
            embed = discord.Embed(
                title="❌ Account Not Found",
                description="Please create an account first or wait for auto-registration.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Validate and process bet
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)
        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        bet_amount_value = bet_info["total_bet_amount"]
        tokens_used = bet_info["tokens_used"]

        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "bet_amount": bet_amount_value
        }

        try:
            # Update to spinning state
            spinning_embed = self.create_beautiful_embed(
                title="🎰 SPINNING...",
                description="✨ **The reels are spinning!** ✨\n🎲 Calculating your fortune...",
                color=0x00FFAE,
                bet_amount=bet_amount_value,
                footer_text="🎰 BetSync Casino • Spinning in progress..."
            )
            
            spinning_view = SlotsSpinningView()
            await loading_message.edit(embed=spinning_embed, view=spinning_view)

            # Dramatic pause for anticipation
            await asyncio.sleep(3.5)

            # Generate results
            slot_symbols = self.generate_slot_result()
            winnings, winning_combinations, multiplier = self.calculate_winnings(slot_symbols, bet_amount_value)
            user_won = winnings > 0

            # Update balances and stats
            if user_won:
                db.update_balance(ctx.author.id, winnings, "points", "$inc")
                server_db = Servers()
                server_db.update_server_profit(ctx, ctx.guild.id, (bet_amount_value - winnings), game="slots")
            else:
                server_db = Servers()
                server_db.update_server_profit(ctx, ctx.guild.id, bet_amount_value, game="slots")

            # Add to history
            history_entry = {
                "type": "win" if user_won else "loss",
                "game": "slots",
                "amount": winnings if user_won else bet_amount_value,
                "bet": bet_amount_value,
                "multiplier": multiplier,
                "timestamp": int(time.time())
            }
            db.update_history(ctx.author.id, history_entry)

            # Create result embed
            if user_won:
                title = "🎉 JACKPOT! YOU WON! 🎉"
                description = f"🌟 **Congratulations!** You hit winning combinations! 🌟"
                color = 0x00FF00
            else:
                title = "😔 No Win This Time"
                description = "🎲 Better luck on your next spin! The reels are waiting..."
                color = 0xFF6B6B

            result_embed = self.create_beautiful_embed(
                title=title,
                description=description,
                color=color,
                bet_amount=bet_amount_value,
                winnings=winnings if user_won else 0,
                multiplier=multiplier if user_won else 0,
                winning_combinations=winning_combinations if user_won else None
            )

            # Create final view with results and play again button
            result_view = SlotsResultView(self, ctx, bet_amount_value, slot_symbols)
            await loading_message.edit(embed=result_embed, view=result_view)

        except Exception as e:
            print(f"Slots game error: {e}")
            error_embed = discord.Embed(
                title="⚠️ Game Error",
                description="An unexpected error occurred. Your bet has been refunded.",
                color=0xFF0000
            )
            await ctx.reply(embed=error_embed)
            
            # Refund the bet
            if user_won is False:  # Only refund if we haven't already processed winnings
                db.update_balance(ctx.author.id, bet_amount_value, "points", "$inc")

        finally:
            # Clean up ongoing game
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]


def setup(bot):
    bot.add_cog(SlotsCog(bot))
