import discord
import asyncio
import random
import datetime
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
import json

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄")
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Start a new game with the same bet amount
        await interaction.followup.send("Starting a new game...", ephemeral=True)
        await self.cog.tictactoe(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass

class TicTacToeAI:
    """AI opponent with different difficulty levels"""

    def __init__(self, difficulty="hard"):
        self.difficulty = difficulty
        self.player_symbol = "X"
        self.ai_symbol = "O"

    def get_best_move(self, board):
        """Get the best move based on difficulty - 70% optimal, 30% random"""
        if random.random() < 0.7:
            return self._get_hard_move(board)
        else:
            return self._get_random_move(board)

    def _get_random_move(self, board):
        """Random move for easy difficulty"""
        empty_cells = [(i, j) for i in range(3) for j in range(3) if board[i][j] is None]
        return random.choice(empty_cells) if empty_cells else None

    def _get_medium_move(self, board):
        """Medium difficulty - basic strategy"""
        # 70% chance to play optimally, 30% random
        if random.random() < 0.7:
            return self._get_hard_move(board)
        else:
            return self._get_random_move(board)

    def _get_hard_move(self, board):
        """Hard difficulty - minimax algorithm"""
        best_score = float('-inf')
        best_move = None

        for i in range(3):
            for j in range(3):
                if board[i][j] is None:
                    board[i][j] = self.ai_symbol
                    score = self._minimax(board, 0, False)
                    board[i][j] = None

                    if score > best_score:
                        best_score = score
                        best_move = (i, j)

        return best_move

    def _minimax(self, board, depth, is_maximizing):
        """Minimax algorithm implementation"""
        winner = self._check_winner(board)

        if winner == self.ai_symbol:
            return 1
        elif winner == self.player_symbol:
            return -1
        elif self._is_board_full(board):
            return 0

        if is_maximizing:
            best_score = float('-inf')
            for i in range(3):
                for j in range(3):
                    if board[i][j] is None:
                        board[i][j] = self.ai_symbol
                        score = self._minimax(board, depth + 1, False)
                        board[i][j] = None
                        best_score = max(score, best_score)
            return best_score
        else:
            best_score = float('inf')
            for i in range(3):
                for j in range(3):
                    if board[i][j] is None:
                        board[i][j] = self.player_symbol
                        score = self._minimax(board, depth + 1, True)
                        board[i][j] = None
                        best_score = min(score, best_score)
            return best_score

    def _check_winner(self, board):
        """Check if there's a winner"""
        # Check rows
        for row in board:
            if row[0] == row[1] == row[2] and row[0] is not None:
                return row[0]

        # Check columns
        for col in range(3):
            if board[0][col] == board[1][col] == board[2][col] and board[0][col] is not None:
                return board[0][col]

        # Check diagonals
        if board[0][0] == board[1][1] == board[2][2] and board[0][0] is not None:
            return board[0][0]
        if board[0][2] == board[1][1] == board[2][0] and board[0][2] is not None:
            return board[0][2]

        return None

    def _is_board_full(self, board):
        """Check if board is full"""
        for row in board:
            if None in row:
                return False
        return True

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x, y, game):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.game.player.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.game.game_over:
            return await interaction.response.send_message("Game is already over!", ephemeral=True)

        await self.game.make_move(interaction, self.x, self.y)

class TicTacToeGame:
    def __init__(self, cog, ctx, player, bet_amount):
        self.cog = cog
        self.ctx = ctx
        self.player = player
        self.bet_amount = bet_amount
        self.difficulty = "hard"
        self.board = [[None, None, None], [None, None, None], [None, None, None]]
        self.current_player = "player"  # Player always starts
        self.game_over = False
        self.winner = None
        self.ai = TicTacToeAI(self.difficulty)
        self.message = None
        self.view = None
        self.timeout_task = None
        self.timeout_time = 60

    def create_game_view(self):
        """Create the game view with buttons"""
        view = discord.ui.View(timeout=self.timeout_time)
        for y in range(3):
            for x in range(3):
                button = TicTacToeButton(x, y, self)
                if self.board[y][x] is not None:
                    button.disabled = True
                    if self.board[y][x] == "X":
                        button.label = "❌"
                        button.style = discord.ButtonStyle.danger
                    else:
                        button.label = "⭕"
                        button.style = discord.ButtonStyle.primary
                elif self.current_player == "ai" or self.game_over:
                    button.disabled = True
                view.add_item(button)

        self.view = view
        return view

    async def start_game(self):
        """Start the game"""
        embed = discord.Embed(
            title="🎮 Tic Tac Toe vs AI",
            description=(
                f"**{self.player.display_name}** (❌) vs **AI Bot** (⭕)\n\n"
                f"**Bet Amount:** {self.bet_amount:.2f} points\n"
                f"**Win Multiplier:** 1.92x\n\n"
                f"**Your turn!** Click a button to make your move."
            ),
            color=0x00FFAE
        )

        self.message = await self.ctx.reply(embed=embed, view=self.create_game_view())
        self.timeout_task = asyncio.create_task(self.handle_timeout())

    async def make_move(self, interaction, x, y):
        """Handle player move"""
        if self.board[y][x] is not None:
            return await interaction.response.send_message("That spot is already taken!", ephemeral=True)

        # Player makes move
        self.board[y][x] = "X"
        await interaction.response.defer()

        # Check for game end
        winner = self.check_winner()
        if winner or self.is_board_full():
            await self.end_game(winner)
            return

        # Switch to AI turn
        self.current_player = "ai"

        # Update view to show player's move
        embed = discord.Embed(
            title="🎮 Tic Tac Toe vs AI",
            description=(
                f"**{self.player.display_name}** (❌) vs **AI Bot** (⭕)\n\n"
                f"**Bet Amount:** {self.bet_amount:.2f} points\n"
                f"**Win Multiplier:** 1.92x\n\n"
                f"**AI is thinking...** 🤖"
            ),
            color=0x00FFAE
        )

        await interaction.edit_original_response(embed=embed, view=self.create_game_view())

        # AI makes move after a short delay for realism
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await self.ai_move()

    async def ai_move(self):
        """Handle AI move"""
        if self.game_over:
            return

        ai_move = self.ai.get_best_move(self.board)
        if ai_move:
            y, x = ai_move
            self.board[y][x] = "O"

        # Check for game end
        winner = self.check_winner()
        if winner or self.is_board_full():
            await self.end_game(winner)
            return

        # Switch back to player
        self.current_player = "player"

        # Update view
        embed = discord.Embed(
            title="🎮 Tic Tac Toe vs AI",
            description=(
                f"**{self.player.display_name}** (❌) vs **AI Bot** (⭕)\n\n"
                f"**Bet Amount:** {self.bet_amount:.2f} points\n"
                f"**Win Multiplier:** 1.92x\n\n"
                f"**Your turn!** Click a button to make your move."
            ),
            color=0x00FFAE
        )

        await self.message.edit(embed=embed, view=self.create_game_view())

    def check_winner(self):
        """Check if there's a winner"""
        # Check rows
        for row in self.board:
            if row[0] == row[1] == row[2] and row[0] is not None:
                return row[0]

        # Check columns
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] and self.board[0][col] is not None:
                return self.board[0][col]

        # Check diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            return self.board[0][2]

        return None

    def is_board_full(self):
        """Check if board is full"""
        for row in self.board:
            if None in row:
                return False
        return True

    async def end_game(self, winner):
        """End the game and process results"""
        self.game_over = True

        if self.timeout_task:
            self.timeout_task.cancel()

        # Process rewards and history
        db = Users()

        if winner == "X":  # Player wins
            winnings = self.bet_amount * 1.92
            db.update_balance(self.player.id, winnings, "points", "$inc")

            # Add to history
            history_entry = {
                "type": "win",
                "game": "tictactoe",
                "bet": self.bet_amount,
                "amount": winnings,
                "multiplier": 1.92,
                "timestamp": int(datetime.datetime.now().timestamp())
            }

            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Victory!",
                description=(
                    f"**{self.player.display_name}** defeated the AI!\n\n"
                    f"**Winnings:** {winnings:.2f} points (1.92x)\n"
                ),
                color=0x00FF00
            )

        elif winner == "O":  # AI wins
            # Add to history
            history_entry = {
                "type": "loss",
                "game": "tictactoe",
                "bet": self.bet_amount,
                "amount": self.bet_amount,
                "timestamp": int(datetime.datetime.now().timestamp())
            }

            embed = discord.Embed(
                title="<:no:1344252518305234987> | Defeat!",
                description=(
                    f"**AI Bot** defeated **{self.player.display_name}**!\n\n"
                    f"**Lost:** {self.bet_amount:.2f} points\n\n"
                    f"Try again!"
                ),
                color=0xFF0000
            )

        else:  # Draw
            # Refund bet
            db.update_balance(self.player.id, self.bet_amount, "points", "$inc")

            # Add to history
            history_entry = {
                "type": "push",
                "game": "tictactoe",
                "bet": self.bet_amount,
                "amount": self.bet_amount,
                "timestamp": int(datetime.datetime.now().timestamp())
            }

            embed = discord.Embed(
                title="🔄 | Draw!",
                description=(
                    f"**{self.player.display_name}** and **AI Bot** tied!\n\n"
                    f"**Refunded:** {self.bet_amount:.2f} points\n"
                ),
                color=0xFFD700
            )

        # Update history
        db.collection.update_one(
            {"discord_id": self.player.id},
            {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
        )

        # Update user stats
        if winner == "X":
            db.collection.update_one(
                {"discord_id": self.player.id},
                {"$inc": {"total_won": 1, "total_earned": winnings}}
            )
        else:
            db.collection.update_one(
                {"discord_id": self.player.id},
                {"$inc": {"total_lost": 1, "total_spent": self.bet_amount}}
            )

        db.collection.update_one(
            {"discord_id": self.player.id},
            {"$inc": {"total_played": 1}}
        )

        # Create final view with disabled buttons
        final_view = self.create_game_view()
        for item in final_view.children:
            item.disabled = True

        # Create play again view
        play_again_view = PlayAgainView(self.cog, self.ctx, self.bet_amount, timeout=15)
        embed.set_footer(text="BetSync Casino", icon_url=self.cog.bot.user.avatar.url)
        
        await self.message.edit(embed=embed, view=play_again_view)
        play_again_view.message = self.message

    async def handle_timeout(self):
        """Handle game timeout"""
        try:
            await asyncio.sleep(self.timeout_time)
            if not self.game_over:
                self.game_over = True

                # Player loses bet on timeout - no refund
                db = Users()

                # Add loss to history
                history_entry = {
                    "type": "loss",
                    "game": "tictactoe",
                    "bet": self.bet_amount,
                    "amount": self.bet_amount,
                    "timestamp": int(datetime.datetime.now().timestamp())
                }

                # Update history and stats
                db.collection.update_one(
                    {"discord_id": self.player.id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )

                db.collection.update_one(
                    {"discord_id": self.player.id},
                    {"$inc": {"total_lost": 1, "total_spent": self.bet_amount, "total_played": 1}}
                )

                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Game Timed Out",
                    description=(
                        f"**{self.player.display_name}** took too long to respond.\n"
                        f"**Lost:** {self.bet_amount:.2f} points"
                    ),
                    color=0xFF0000
                )

                # Create final view with disabled buttons
                final_view = self.create_game_view()
                for item in final_view.children:
                    item.disabled = True

                embed.set_footer(text="BetSync Casino", icon_url=self.cog.bot.user.avatar.url)
                await self.message.edit(embed=embed, view=final_view)
        except asyncio.CancelledError:
            pass

class TicTacToeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["ttt"])
    async def tictactoe(self, ctx, bet_amount: str = None):
        """Play Tic Tac Toe against an AI opponent!"""

        # Show help if no arguments
        if not bet_amount:
            embed = discord.Embed(
                title=":information_source: | How to Play Tic Tac Toe",
                description=(
                    "Challenge our AI bot to a game of Tic Tac Toe!\n\n"
                    "**Usage:** `!tictactoe <amount>`\n"
                    "**Example:** `!tictactoe 10`\n\n"
                    "**Rewards:**\n"
                    "• Win: **1.92x** your bet\n"
                    "• Draw: Full refund\n"
                    "• Loss: Lose your bet\n\n"
                    "You play as ❌ and go first!"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Parse bet amount
        try:
            bet_amount_float = float(bet_amount)
            if bet_amount_float <= 0:
                raise ValueError("Bet must be positive")
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Bet Amount",
                description="Please enter a valid positive number for your bet.",
                color=0xFF0000
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Show loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Preparing Tic Tac Toe Game...",
            description="Please wait while we set up your game against the AI.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Get user data
        db = Users()
        db.save(ctx.author.id)
        user_data = db.fetch_user(ctx.author.id)

        if not user_data:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Required",
                description="You need an account to play. Please wait for auto-registration.",
                color=0xFF0000
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if user has enough balance
        current_balance = user_data.get("points", 0)
        if current_balance < bet_amount_float:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Balance",
                description=f"You need {bet_amount_float:.2f} points to play.\nYour balance: {current_balance:.2f} points",
                color=0xFF0000
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Deduct bet amount
        db.update_balance(ctx.author.id, -bet_amount_float, "points", "$inc")

        # Add rakeback
        user_data = db.fetch_user(ctx.author.id)
        with open('static_data/ranks.json', 'r') as f:
            rank_data = json.load(f)

        current_rank_requirement = user_data.get('rank', 0)
        rakeback_percentage = 0

        for name, info in rank_data.items():
            if info['level_requirement'] == current_rank_requirement:
                rakeback_percentage = info['rakeback_percentage']
                break

        rakeback_amount = bet_amount_float * (rakeback_percentage / 100)
        if rakeback_amount > 0:
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"rakeback_tokens": rakeback_amount}}
            )

        # Delete loading message and start game
        await loading_message.delete()

        # Create and start game
        game = TicTacToeGame(self, ctx, ctx.author, bet_amount_float)
        await game.start_game()

def setup(bot):
    bot.add_cog(TicTacToeCog(bot))