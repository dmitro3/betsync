import discord
import random
import time
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount):
        super().__init__(timeout=15)  # 15 second timeout
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄")
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Start a new game with the same bet
        # Using followup instead of defer to ensure the command triggers correctly
        await interaction.followup.send("Starting new game...", ephemeral=True)
        await self.cog.dicegame(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        # Disable button after timeout
        for item in self.children:
            item.disabled = True

        # Try to update the message if it exists
        try:
            await self.message.edit(view=self)
        except Exception as e:
            print(f"Error updating message on timeout: {e}")

class DiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["dice", "roll", "d"])
    async def dicegame(self, ctx, bet_amount: str = None):
        """Play the dice game - roll higher than the dealer to win!"""
        if not bet_amount:
            embed = discord.Embed(
                title=":game_die: How to Play Dice",
                description=(
                    "**Dice** is a game where you roll against the dealer. Higher number wins!\n\n"
                    "**Usage:** `!dicegame <amount>`\n"
                    "**Example:** `!dicegame 100`\n\n"
                    "- **You and the dealer each roll a dice (1-6)**\n"
                    "- **If your number is higher, you win!**\n"
                    "- **If there's a tie or dealer wins, you lose your bet**\n"

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
        #loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Preparing Dice Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount using currency_helper
        from Cogs.utils.currency_helper import process_bet_amount
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

        # If processing failed, return the error
        if not success:
            return await loading_message.edit(embed=error_embed)

        # Extract needed values from bet_info
        tokens_used = bet_info["tokens_used"]
        #credits_used = bet_info["credits_used"]
        total_bet = bet_info["total_bet_amount"]
        bet_amount_value = total_bet #added for consistency


        bet_description = f"**Bet Amount:** {tokens_used} points"

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
           # "credits_used": credits_used,
            "bet_amount": total_bet
        }

        # Delete loading message
        await loading_message.delete()

        try:
            # Create initial embed with rolling animation
            rolling_dice = "<a:rollingdice:1344966270629576734>"
            initial_embed = discord.Embed(
                title="🎲 | Dice Game",
                description=f"{bet_description}\n\n{rolling_dice}",
                color=0x00FFAE
            )
            initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Send initial message
            message = await ctx.reply(embed=initial_embed)

            # Wait for dramatic effect
            await asyncio.sleep(2)

            # Roll the dice
            user_roll = random.randint(1, 6)
            dealer_roll = random.randint(1, 6)

            # Use custom dice emojis
            dice_emojis = {
                1: "<:d1:1344966667628970025>",
                2: "<:d2:1344966647798300786>",
                3: "<:d3:1344966630458789919>",
                4: "<:d4:1344966603544199258>",
                5: "<:d5:1344966572883574835>",
                6: "<:d6:1344966538775629965>"
            }

            user_dice = dice_emojis.get(user_roll, "🎲")
            dealer_dice = dice_emojis.get(dealer_roll, "🎲")

            # Determine the winner or if it's a draw
            is_draw = user_roll == dealer_roll
            user_won = user_roll > dealer_roll

            # Define the multiplier (for a win)
            # House edge of at least 4%
            multiplier = 1.95  # With 6 sides, fair would be 2.0, so 1.95 gives 2.5% house edge

            # Create result embed
            if is_draw:
                # Return the bet for a draw
                result_embed = discord.Embed(
                    title="🎲 | Dice Game - It's a Draw!",
                    description=(
                        f"{bet_description}\n\n"
                        f"Your Roll: {user_dice} ({user_roll})\n"
                        f"Dealer Roll: {dealer_dice} ({dealer_roll})\n\n"
                        f"**Result:** Your bet has been returned!"
                    ),
                    color=0xFFD700  # Gold color for draws
                )

                # Return the bet to the user
                db = Users()
                db.update_balance(ctx.author.id, tokens_used, "credits", "$inc")

                # Add to history as a draw

            elif user_won:
                # Calculate winnings
                winnings = round(total_bet * multiplier, 2)
                profit = winnings - total_bet

                result_embed = discord.Embed(
                    title="🎲 | Dice Game - You Won! 🎉",
                    description=(
                        f"{bet_description}\n\n"
                        f"Your Roll: {user_dice} ({user_roll})\n"
                        f"Dealer Roll: {dealer_dice} ({dealer_roll})\n\n"
                        f"**Multiplier:** {multiplier}x\n"
                        f"**Winnings:** `{round(winnings,2)} points`\n"
                        f"**Profit:** `{round(profit, 2)} points`"
                    ),
                    color=0x00FF00
                )

                # Update user balance
                db = Users()
                db.update_balance(ctx.author.id, winnings, "credits", "$inc")

                # Update server profit (negative value because server loses when player wins)
                servers_db = Servers()
                server_profit = -profit  # Server loses money when player wins
                servers_db.update_server_profit(ctx, ctx.guild.id, server_profit, game="dice")

                # Add to history
                

            else:
                result_embed = discord.Embed(
                    title="🎲 | Dice Game - You Lost 😢",
                    description=(
                        f"{bet_description}\n\n"
                        f"Your Roll: {user_dice} ({user_roll})\n"
                        f"Dealer Roll: {dealer_dice} ({dealer_roll})\n\n"
                        f"**Result:** You lost your bet!"
                    ),
                    color=0xFF0000
                )

                # Update history for loss
                db = Users()
                servers_db = Servers()

                

                # Update server profit
                servers_db.update_server_profit(ctx, ctx.guild.id, total_bet, game="dice")

            currency_used = "points"

            bet_display = f"`{total_bet} {currency_used}`"


            # Add play again button that expires after 15 seconds
            play_again_view = PlayAgainView(self, ctx, total_bet)

            # Update the message with result
            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            await message.edit(embed=result_embed, view=play_again_view)

            # Store message reference in view for timeout handling
            play_again_view.message = message

        except Exception as e:
            print(f"Error in dice game: {e}")
            # Try to send error message to user
            
        finally:
            # Remove the game from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

def setup(bot):
    bot.add_cog(DiceCog(bot))