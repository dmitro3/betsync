
import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import process_bet_amount


class SlotsPlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_used="points"):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.message = None
        self.author_id = ctx.author.id

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable the button to prevent spam clicks
        for item in self.children:
            item.disabled = True
        await interaction.response.defer()
        message = await interaction.original_response()
        await message.edit(view=self)

        # Run the command again
        await self.cog.slots(self.ctx, self.bet_amount)

    async def on_timeout(self):
        # Disable button after timeout
        for item in self.children:
            item.disabled = True

        # Try to update the message if it exists
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"Error updating message on timeout: {e}")


class SlotsView(discord.ui.View):
    def __init__(self, symbols):
        super().__init__(timeout=None)
        self.symbols = symbols
        
        # Create 15 buttons (5x3 grid)
        for i in range(15):
            button = discord.ui.Button(
                emoji="<:slots:1333757726437806111>",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=i // 5
            )
            self.add_item(button)

    def update_buttons(self, final_symbols=None, disabled=True):
        """Update buttons with final symbols or keep spinning animation"""
        for i, button in enumerate(self.children):
            if final_symbols:
                button.emoji = final_symbols[i]
            button.disabled = disabled


class SlotsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        
        # Slot symbols with their frequencies and payouts
        self.symbols = {
            "🍎": {"weight": 20, "payout": 1.5},
            "🍊": {"weight": 20, "payout": 1.5},
            "🍋": {"weight": 18, "payout": 2.0},
            "🍇": {"weight": 15, "payout": 2.5},
            "🍒": {"weight": 12, "payout": 3.0},
            "🔔": {"weight": 8, "payout": 5.0},
            "💎": {"weight": 4, "payout": 10.0},
            "🍀": {"weight": 2, "payout": 25.0},
            "🎰": {"weight": 1, "payout": 100.0}
        }

    def generate_slot_result(self):
        """Generate a 3x5 slot machine result"""
        symbol_list = []
        weights = []
        
        for symbol, data in self.symbols.items():
            symbol_list.append(symbol)
            weights.append(data["weight"])
        
        # Generate 15 symbols (3 rows x 5 columns)
        result = []
        for _ in range(15):
            symbol = random.choices(symbol_list, weights=weights)[0]
            result.append(symbol)
        
        return result

    def calculate_winnings(self, symbols, bet_amount):
        """Calculate winnings based on slot result"""
        # Convert 1D list to 3x5 grid for easier processing
        grid = [symbols[i:i+5] for i in range(0, 15, 5)]
        
        total_multiplier = 0
        winning_lines = []
        
        # Check horizontal lines (3 rows)
        for row_idx, row in enumerate(grid):
            line_multiplier = self.check_line_win(row)
            if line_multiplier > 0:
                total_multiplier += line_multiplier
                winning_lines.append(f"Row {row_idx + 1}")
        
        # Check vertical lines (5 columns)
        for col_idx in range(5):
            column = [grid[row][col_idx] for row in range(3)]
            line_multiplier = self.check_line_win(column)
            if line_multiplier > 0:
                total_multiplier += line_multiplier
                winning_lines.append(f"Column {col_idx + 1}")
        
        # Check diagonal lines
        # Main diagonal (top-left to bottom-right)
        main_diagonal = [grid[0][0], grid[1][1], grid[2][2]]
        line_multiplier = self.check_line_win(main_diagonal)
        if line_multiplier > 0:
            total_multiplier += line_multiplier
            winning_lines.append("Main Diagonal")
        
        # Anti diagonal (top-right to bottom-left)
        anti_diagonal = [grid[0][2], grid[1][1], grid[2][0]]
        line_multiplier = self.check_line_win(anti_diagonal)
        if line_multiplier > 0:
            total_multiplier += line_multiplier
            winning_lines.append("Anti Diagonal")
        
        # Apply house edge (reduce winnings by 10%)
        house_edge_multiplier = 0.90
        final_multiplier = total_multiplier * house_edge_multiplier
        
        winnings = bet_amount * final_multiplier
        return winnings, winning_lines, final_multiplier

    def check_line_win(self, line):
        """Check if a line of 3-5 symbols wins"""
        if len(line) < 3:
            return 0
        
        # Check for 3+ matching symbols
        for symbol, data in self.symbols.items():
            count = line.count(symbol)
            if count >= 3:
                base_payout = data["payout"]
                # Bonus for 4 or 5 matching symbols
                if count == 4:
                    return base_payout * 1.5
                elif count == 5:
                    return base_payout * 2.0
                else:
                    return base_payout
        
        return 0

    @commands.command(aliases=["slot"])
    async def slots(self, ctx, bet_amount: str = None):
        """Play slots - spin the reels and win big!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🎰 How to Play Slots",
                description=(
                    "**Slots** is a classic casino game where you spin reels to match symbols!\n\n"
                    "**Usage:** `!slots <amount>`\n"
                    "**Example:** `!slots 100`\n\n"
                    "**How to Win:**\n"
                    "- Match 3+ symbols in a line (horizontal, vertical, or diagonal)\n"
                    "- Different symbols have different payouts\n"
                    "- More rare symbols = bigger payouts!\n\n"
                    "**Symbol Payouts (3 matches):**\n"
                    "🍎🍊 - 1.5x | 🍋 - 2.0x | 🍇 - 2.5x\n"
                    "🍒 - 3.0x | 🔔 - 5.0x | 💎 - 10.0x\n"
                    "🍀 - 25.0x | 🎰 - 100.0x\n\n"
                    "*4 matches = 1.5x bonus, 5 matches = 2.0x bonus*"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if the user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Send loading message
        loading_embed = discord.Embed(
            title="<:loading:1344611780638412811> | Spinning",
            description="The reels are spinning...",
            color=0x00FFAE
        )
        
        # Create spinning view
        spinning_view = SlotsView([])
        loading_message = await ctx.reply(embed=loading_embed, view=spinning_view)

        # Process bet amount
        db = Users()
        user_data = db.fetch_user(ctx.author.id)

        if user_data == False:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="You don't have an account. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Process bet using currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        # Successful bet processing
        tokens_used = bet_info["tokens_used"]
        bet_amount_value = bet_info["total_bet_amount"]
        currency_used = "points"
        currency_display = f"`{bet_amount_value} {currency_used}`"

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "bet_amount": bet_amount_value
        }

        try:
            # Wait for spinning animation
            await asyncio.sleep(3)

            # Generate slot result
            slot_symbols = self.generate_slot_result()
            
            # Calculate winnings
            winnings, winning_lines, multiplier = self.calculate_winnings(slot_symbols, bet_amount_value)
            
            # Determine if user won
            user_won = winnings > 0

            # Add winnings if user won
            if user_won:
                db = Users()
                db.update_balance(ctx.author.id, winnings, "points", "$inc")
                # Update server profit
                server_db = Servers()
                server_db.update_server_profit(ctx, ctx.guild.id, (bet_amount_value - winnings), game="slots")
            else:
                server_db = Servers()
                server_db.update_server_profit(ctx, ctx.guild.id, bet_amount_value, game="slots")

            # Add to user history
            timestamp = int(time.time())
            if user_won:
                history_entry = {
                    "type": "win",
                    "game": "slots",
                    "amount": winnings,
                    "bet": bet_amount_value,
                    "multiplier": multiplier,
                    "timestamp": timestamp
                }
            else:
                history_entry = {
                    "type": "loss",
                    "game": "slots",
                    "amount": bet_amount_value,
                    "bet": bet_amount_value,
                    "multiplier": 0,
                    "timestamp": timestamp
                }

            db = Users()
            db.update_history(ctx.author.id, history_entry)

            # Create result embed
            if user_won:
                result_embed = discord.Embed(
                    title="<:yes:1355501647538815106> | You Won!",
                    description=(
                        f"**Bet:** {currency_display}\n"
                        f"**Multiplier:** {multiplier:.2f}x\n"
                        f"**Winnings:** `{winnings:.2f} points`\n"
                        f"**Winning Lines:** {', '.join(winning_lines) if winning_lines else 'None'}"
                    ),
                    color=0x00FF00
                )
            else:
                result_embed = discord.Embed(
                    title="<:no:1344252518305234987> | You Lost",
                    description=(
                        f"**Bet:** {currency_display}\n"
                        f"Better luck next time!"
                    ),
                    color=0xFF0000
                )

            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Update view with final symbols
            final_view = SlotsView(slot_symbols)
            final_view.update_buttons(slot_symbols, disabled=True)

            # Create play again view
            play_again_view = SlotsPlayAgainView(self, ctx, bet_amount_value, currency_used)

            # Edit message with result
            await loading_message.edit(embed=result_embed, view=final_view)
            
            # Send play again button as a separate message
            play_again_message = await ctx.followup.send("Want to spin again?", view=play_again_view)
            play_again_view.message = play_again_message

            # Clear ongoing game
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

        except Exception as e:
            # Handle any errors
            print(f"Error in slots game: {e}")
            error_embed = discord.Embed(
                title="❌ | Error",
                description="An error occurred while playing slots. Please try again later.",
                color=0xFF0000
            )
            await ctx.send(embed=error_embed)

            # Make sure to clean up
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]


def setup(bot):
    bot.add_cog(SlotsCog(bot))
