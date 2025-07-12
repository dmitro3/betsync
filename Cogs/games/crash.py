#put only game commands here
import discord
import random
import asyncio
import matplotlib.pyplot as plt
import io
import numpy as np
import time
import math
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
from PIL import Image, ImageDraw


class CrashGame:

    def __init__(self, cog, ctx, bet_amount, user_id):
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.user_id = user_id
        self.crashed = False
        self.cashed_out = False
        self.current_multiplier = 1.0
        self.cash_out_multiplier = 0.0
        self.tokens_used = 0
        #self.credits_used = 0
        self.message = None


class PlayAgainView(discord.ui.View):

    def __init__(self, cog, ctx, bet_amount, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = None

    @discord.ui.button(label="Play Again",
                       style=discord.ButtonStyle.primary,
                       emoji="🔄")
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Check if user can afford the same bet
        db = Users()
        user_data = db.fetch_user(interaction.user.id)
        if not user_data:
            return await interaction.followup.send(
                "Your account couldn't be found. Please try again later.",
                ephemeral=True)

        await interaction.followup.send(
            "Starting a new game with the same bet...", ephemeral=True)
        await self.cog.crash(self.ctx, str(self.bet_amount))


class CrashCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Check if this is a cash out reaction for a crash game
        if str(reaction.emoji) == "💰" and user.id in self.ongoing_games:
            game_data = self.ongoing_games.get(user.id)
            if game_data and "crash_game" in game_data:
                crash_game = game_data["crash_game"]
                # Only process if it's the game owner and the game is still active
                if (user.id == crash_game.user_id
                        and reaction.message.id == crash_game.message.id
                        and not crash_game.crashed
                        and not crash_game.cashed_out):
                    # Set cash out values
                    crash_game.cashed_out = True
                    crash_game.cash_out_multiplier = crash_game.current_multiplier

    @commands.command(aliases=["cr"])
    async def crash(self, ctx, bet_amount: str = None):
        """Play the crash game - bet before the graph crashes!"""
        if not bet_amount:
            embed = discord.Embed(
                title=":bulb: How to Play Crash",
                description=
                ("**Crash** is a multiplier game where you place a bet and cash out before the graph crashes.\n\n"
                 "**Usage:** `!crash <amount>`\n"
                 "**Example:** `!crash 100`\n\n"
                 "- Watch as the multiplier increases in real-time\n"
                 "- React with 💰 before it crashes to cash out and win\n"
                 "- If it crashes before you cash out, you lose your bet\n"
                 "- The longer you wait, the higher the potential reward!\n\n"
                 "You can bet using tokens (T) or credits (C):\n"
                 "- If you have enough tokens, they will be used first\n"
                 "- If you don't have enough tokens, credits will be used\n"
                 "- If needed, both will be combined to meet your bet amount"),
                color=0x00FFAE)
            embed.set_footer(text="BetSync Casino",
                             icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if user already has a game in progress
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game in Progress",
                description="You already have a crash game in progress.",
                color=0xFF0000)
            return await ctx.reply(embed=embed)

        # Send loading message
        #loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Processing Crash Bet...",
            description="Please wait while we process your request...",
            color=0x00FFAE)
        loading_message = await ctx.reply(embed=loading_embed)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process the bet amount using the currency helper
        success, bet_info, error_embed = await process_bet_amount(
            ctx, bet_amount, loading_message)

        # If processing failed, return the error
        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        # Successful bet processing - extract relevant information
        tokens_used = bet_info["tokens_used"]
        #credits_used = bet_info["credits_used"]
        total_bet = bet_info["total_bet_amount"]

        # Get database instance for game stats update
        db = Users()

        

        # Create CrashGame object
        crash_game = CrashGame(self, ctx, total_bet, ctx.author.id)
        crash_game.tokens_used = tokens_used
        #crash_game.credits_used = credits_used

        # Generate crash point with a more balanced distribution
        # House edge is around 4-5% with this implementation
        try:
            # Adjust the minimum crash point to ensure some minimum payout
            min_crash = 1.0

            # Use a better distribution to increase median crash points
            # Lower alpha value (1.7 instead of 2) means higher multipliers are more common
            alpha = 1.7

            # Generate base crash point, modified for fairer distribution
            r = random.random()

            # House edge factor (0.96 gives ~4% edge to house in the long run)
            house_edge = 0.96

            # Calculate crash point using improved formula
            # This gives better distribution with more points between 1.5x-3x
            if r < 0.01:  # 1% chance for instant crash (higher house edge)
                crash_point = 1.0
            else:
                # Main distribution calculation
                crash_point = min_crash + (
                    (1 / (1 - r))**(1 / alpha) - 1) * house_edge

                # Round to 2 decimal places
                crash_point = math.floor(crash_point * 100) / 100

            # We don't want unrealistically high crash points
            crash_point = min(crash_point,
                              30.0)  # Increased max from 20x to 30x

            # Ensure crash point is at least 1.0
            crash_point = max(crash_point, 1.0)

        except Exception as e:
            print(f"Error generating crash point: {e}")
            crash_point = random.uniform(1.0, 3.0)  # Fallback

        # Format bet amount description

        bet_description = f"**Bet Amount:** `{tokens_used} points`"

        # Create initial graph
        try:
            initial_embed, initial_file = self.generate_crash_graph(1.0, False, target_multiplier=crash_point)
            initial_embed.title = "🚀 | Crash Game Started"
            initial_embed.description = (
                f"{bet_description}\n"
                f"**Current Multiplier:** 1.00x\n\n"
                "React with 💰 to cash out before it crashes!")
        except Exception as e:
            print(f"Error generating crash graph: {e}")
            # Create a simple embed if graph fails
            initial_embed = discord.Embed(
                title="🚀 | Crash Game Started",
                description=(f"{bet_description}\n"
                             f"**Current Multiplier:** 1.00x\n\n"
                             "Click **Cash Out** before it crashes to win!"),
                color=0x00FFAE)
            initial_file = None

        # Delete loading message and send initial game message
        await loading_message.delete()

        # Send message with file attachment if available
        if initial_file:
            message = await ctx.reply(embed=initial_embed, file=initial_file)
        else:
            message = await ctx.reply(embed=initial_embed)

        # Add cash out reaction
        await message.add_reaction("💰")

        # Store message in the crash game object
        crash_game.message = message

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "message": message,
            "crash_game": crash_game,
            "tokens_used": tokens_used,
            #"credits_used": credits_used
        }

        # Track the currency used for winning calculation
        crash_game.tokens_used = tokens_used
        #crash_game.credits_used = credits_used

        # Start the game
        await self.run_crash_game(ctx, message, crash_game, crash_point,
                                  total_bet)

    async def run_crash_game(self, ctx, message, crash_game, crash_point,
                             bet_amount):
        """Run the crash game animation and handle the result"""
        try:
            multiplier = 1.0
            growth_rate = 0.05  # Controls how fast the multiplier increases

            bet_description = f"**Bet Amount:** `{bet_amount} points`"

            # Create an event to track reaction cash out
            cash_out_event = asyncio.Event()

            # Set up reaction check
            def reaction_check(reaction, user):
                # Only check reactions from the game owner on the game message with 💰 emoji
                return (user.id == ctx.author.id
                        and reaction.message.id == message.id
                        and str(reaction.emoji) == "💰"
                        and not crash_game.crashed)

            # Start reaction listener task
            async def reaction_listener():
                try:
                    # Wait for the cash out reaction
                    reaction, user = await self.bot.wait_for(
                        'reaction_add', check=reaction_check)
                    if not crash_game.crashed and not crash_game.cashed_out:
                        # Set cash out values
                        crash_game.cashed_out = True
                        crash_game.cash_out_multiplier = crash_game.current_multiplier
                        # Set the event to notify the main loop
                        cash_out_event.set()

                        # Send immediate feedback to player
                        winnings = round(bet_amount *
                                         crash_game.cash_out_multiplier,
                                         2)  # Round to 2 decimal places
                        feedback_embed = discord.Embed(
                            title="<:yes:1355501647538815106> Cash Out Successful!",
                            description=
                            f"You cashed out at **{crash_game.cash_out_multiplier:.2f}x**\nWinnings: `{round(winnings, 2)} points`",
                            color=0x00FF00)
                        await ctx.send(embed=feedback_embed, delete_after=5)
                except Exception as e:
                    print(f"Error in reaction listener: {e}")

            # Start the reaction listener in the background
            reaction_task = asyncio.create_task(reaction_listener())

            # Continue incrementing the multiplier until crash or cash out
            while multiplier < crash_point and not crash_game.cashed_out:
                # Wait a bit between updates (faster at the start, slower as multiplier increases)
                delay = 1.0 / (1 + multiplier * 0.5)
                delay = max(0.1, min(
                    delay, 0.5))  # Shorter delays for more responsive cash out

                # Check for cash out BEFORE waiting
                if cash_out_event.is_set():
                    # Cash out was triggered, exit loop immediately
                    break

                # Wait for either the delay to pass or cash out event to be triggered
                try:
                    await asyncio.wait_for(cash_out_event.wait(),
                                           timeout=delay)
                    # If we get here, the cash out event was triggered
                    break
                except asyncio.TimeoutError:
                    # Check once more after timeout just to be sure
                    if cash_out_event.is_set():
                        break
                    # Timeout means the delay passed normally, continue with game
                    pass

                # Increase multiplier with a bit of randomness
                multiplier += growth_rate * (1 + random.uniform(-0.2, 0.2))
                crash_game.current_multiplier = multiplier

                try:
                    # Generate updated graph and embed
                    embed, file = self.generate_crash_graph(multiplier, False, target_multiplier=crash_point)
                    embed.title = "🚀 | Crash Game In Progress"
                    embed.description = (
                        f"{bet_description}\n"
                        f"**Current Multiplier:** {multiplier:.2f}x\n\n"
                        "React with 💰 to cash out before it crashes!")

                    # Update the message with new graph
                    view = discord.ui.View()  # Added view creation here.
                    await message.edit(embed=embed, files=[file], view=view)
                except Exception as graph_error:
                    print(f"Error updating graph: {graph_error}")
                    # Simple fallback in case graph generation fails
                    try:
                        embed = discord.Embed(
                            title="🚀 | Crash Game In Progress",
                            description=(
                                f"{bet_description}\n"
                                f"**Current Multiplier:** {multiplier:.2f}x\n\n"
                                "React with 💰 to cash out before it crashes!"),
                            color=0x00FFAE)
                        view = discord.ui.View()  # Added view creation here.
                        await message.edit(embed=embed, view=view)
                    except Exception as fallback_error:
                        print(
                            f"Error updating fallback message: {fallback_error}"
                        )

            # Cancel the reaction task if it's still running
            if not reaction_task.done():
                reaction_task.cancel()

            # Game ended - either crashed or cashed out
            crash_game.crashed = True

            # Try to clear reactions
            try:
                await message.clear_reactions()
            except:
                pass

            # Get database connection
            db = Users()

            # Handle crash
            if not crash_game.cashed_out:
                try:
                    # Generate crash graph
                    embed, file = self.generate_crash_graph(multiplier, True, target_multiplier=crash_point)
                    embed.title = "<:no:1344252518305234987> | CRASHED!"
                    embed.description = (
                        f"{bet_description}\n"
                        f"**Crashed At:** {multiplier:.2f}x\n\n")
                        #f"**Result:** You lost your bet!")
                    embed.color = 0xFF0000

                    # Add to history
                    from Cogs.utils.mongo import Servers
                    dbb = Servers()
                    dbb.update_server_profit(ctx, ctx.guild.id,
                                             bet_amount,
                                             game="crash")

                    #from Cogs.utils.mongo import Servers
                    #dbb = Servers()

                    # Update stats

                    # Create Play Again view with button
                    play_again_view = discord.ui.View()
                    play_again_button = discord.ui.Button(
                        label="Play Again",
                        style=discord.ButtonStyle.primary
                        )

                    async def play_again_callback(interaction):
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message(
                                "This is not your game!", ephemeral=True)

                        # Start a new game with the same bet
                        await interaction.response.defer()
                        await self.crash(ctx, str(bet_amount))

                    play_again_button.callback = play_again_callback
                    play_again_view.add_item(play_again_button)

                    # Update message with crash result and Play Again button
                    await message.edit(embed=embed,
                                       files=[file],
                                       view=play_again_view)
                #except: pass

                except Exception as crash_error:
                    print(f"Error handling crash: {crash_error}")
                    # Simple fallback
                    try:
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | CRASHED!",
                            description=(
                                f"{bet_description}\n"
                                f"**Crashed At:** {multiplier:.2f}x\n\n"),
                                #f"**Result:** You lost your bet!"),
                            color=0xFF0000)
                        # Add Play Again button
                        play_again_view = discord.ui.View()
                        play_again_button = discord.ui.Button(
                            label="Play Again",
                            style=discord.ButtonStyle.primary
                            )

                        async def play_again_callback(interaction):
                            if interaction.user.id != ctx.author.id:
                                return await interaction.response.send_message(
                                    "This is not your game!", ephemeral=True)

                            # Start a new game with the same bet
                            await interaction.response.defer()
                            await self.crash(ctx, str(bet_amount))

                        play_again_button.callback = play_again_callback
                        play_again_view.add_item(play_again_button)

                        await message.edit(embed=embed, view=play_again_view)

                    except Exception as fallback_error:
                        print(
                            f"Error updating fallback crash message: {fallback_error}"
                        )

            else:
                try:
                    # User cashed out successfully
                    cash_out_multiplier = crash_game.cash_out_multiplier
                    winnings = round(bet_amount * cash_out_multiplier,
                                     2)  # Round to 2 decimal places
                    profit = winnings - bet_amount

                    # Generate success graph
                    embed, file = self.generate_crash_graph(
                        cash_out_multiplier, False, cash_out=True, target_multiplier=crash_point)
                    embed.title = "<:yes:1355501647538815106> | CASHED OUT!"
                    embed.description = (
                        f"{bet_description}\n"
                        f"**Cashed Out At:** {cash_out_multiplier:.2f}x\n"
                        f"**Winnings:** `{round(winnings, 2)} points`\n"
                        f"**Profit:** `{round(profit, 2)} points`")
                    embed.color = 0x00FF00

                    # Update server profit (negative value because server loses when player wins)
                    from Cogs.utils.mongo import Servers
                    servers_db = Servers()
                    server_profit = -profit  # Server loses money when player wins
                    servers_db.update_server_profit(ctx, ctx.guild.id,
                                                    server_profit,
                                                    game="crash")

                    # Add credits to user balance
                    db.update_balance(ctx.author.id, winnings, "credits",
                                      "$inc")

                    # Add to history
                    from Cogs.utils.mongo import Servers
                    dbb = Servers()

                    # Update server profit (negative value because server loses when player wins)
                    # from Cogs.utils.mongo import Servers
                    #servers_db = Servers()
                    # server_profit = -profit  # Server loses money when player wins
                    # servers_db.update_server_profit(ctx.guild.id, server_profit)

                    # Create Play Again view with button
                    play_again_view = discord.ui.View()
                    play_again_button = discord.ui.Button(
                        label="Play Again",
                        style=discord.ButtonStyle.primary,
                    )

                    async def play_again_callback(interaction):
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message(
                                "This is not your game!", ephemeral=True)

                        # Start a new game with the same bet
                        await interaction.response.defer()
                        await self.crash(ctx, str(bet_amount))

                    play_again_button.callback = play_again_callback
                    play_again_view.add_item(play_again_button)

                    # Update message with win result and Play Again button
                    await message.edit(embed=embed,
                                       files=[file],
                                       view=play_again_view)

                except Exception as win_error:
                    print(f"Error handling win: {win_error}")
                    # Simple fallback
                    try:
                        embed = discord.Embed(
                            title="<:yes:1355501647538815106> | CASHED OUT!",
                            description=
                            (f"{bet_description}\n"
                             f"**Cashed Out At:** {cash_out_multiplier:.2f}x\n"
                             f"**Winnings:** `{winnings} points`\n"
                             f"**Profit:** `{profit} points`"),
                            color=0x00FF00)
                        # Add Play Again button
                        play_again_view = discord.ui.View()
                        play_again_button = discord.ui.Button(
                            label="Play Again",
                            style=discord.ButtonStyle.primary,
                            )

                        async def play_again_callback(interaction):
                            if interaction.user.id != ctx.author.id:
                                return await interaction.response.send_message(
                                    "This is not your game!", ephemeral=True)

                            # Start a new game with the same bet
                            await interaction.response.defer()
                            await self.crash(ctx, str(bet_amount))

                        play_again_button.callback = play_again_callback
                        play_again_view.add_item(play_again_button)

                        # Make sure winnings are credited even if graph fails
                        db.update_balance(ctx.author.id, winnings, "credits",
                                          "$inc")

                        await message.edit(embed=embed, view=play_again_view)

                    except Exception as fallback_error:
                        print(
                            f"Error updating fallback win message: {fallback_error}"
                        )

        except Exception as e:
            print(f"Error in crash game: {e}")
            # Try to send error message to user
            try:
                error_embed = discord.Embed(
                    title="❌ | Game Error",
                    description=
                    "An error occurred during the game. Your bet has been refunded.",
                    color=0xFF0000)
                await ctx.reply(embed=error_embed)

                # Refund the bet if there was an error
                db = Users()

                db.update_balance(ctx.author.id, crash_game.tokens_used,
                                  "points")

                # Log the refund
                print(
                    f"Refunded {crash_game.tokens_used} tokens and {crash_game.credits_used} credits to {ctx.author.name}"
                )
            except Exception as refund_error:
                print(f"Error refunding bet: {refund_error}")
        finally:
            # Remove the game from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

    def generate_crash_graph(self,
                             current_multiplier,
                             crashed=False,
                             cash_out=False,
                             target_multiplier=2.0):
        """Generate a modern crash game UI using Pillow"""
        try:
            # Image dimensions
            width, height = 800, 400
            
            # Color scheme based on multiplier and state
            bg_color = (52, 73, 94)  # Dark blue-gray #34495e
            
            # Progress bar colors based on multiplier ranges
            if current_multiplier < 2.0:
                bar_color = (255, 165, 0)  # Orange #ffa500
                text_color = (255, 165, 0)  # Orange text
            elif current_multiplier < 10.0:
                bar_color = (52, 152, 219)  # Blue #3498db
                text_color = (52, 152, 219)  # Blue text
            else:
                bar_color = (155, 89, 182)  # Purple #9b59b6
                text_color = (155, 89, 182)  # Purple text
            
            # Override colors for special states
            if crashed:
                text_color = (231, 76, 60)  # Red #e74c3c
            elif cash_out:
                text_color = (46, 204, 113)  # Green #2ecc71
                
            # Create image
            img = Image.new('RGB', (width, height), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Try to load fonts, fallback to default if not available
            try:
                # Try to load custom fonts
                title_font = ImageFont.truetype("arial.ttf", 32)
                multiplier_font = ImageFont.truetype("arial.ttf", 80)
                watermark_font = ImageFont.truetype("arial.ttf", 20)
                target_font = ImageFont.truetype("arial.ttf", 20)
            except:
                try:
                    # Fallback to other font files
                    title_font = ImageFont.truetype("Helvetica.ttf", 32)
                    multiplier_font = ImageFont.truetype("Helvetica-Bold.ttf", 80)
                    watermark_font = ImageFont.truetype("Helvetica.ttf", 20)
                    target_font = ImageFont.truetype("Helvetica.ttf", 20)
                except:
                    # Use default font
                    title_font = ImageFont.load_default()
                    multiplier_font = ImageFont.load_default()
                    watermark_font = ImageFont.load_default()
                    target_font = ImageFont.load_default()
            
            # Draw BetSync watermark (top left)
            watermark_text = "BetSync"
            watermark_color = (255, 255, 255, 100)  # Semi-transparent white
            draw.text((30, 30), watermark_text, fill=watermark_color, font=watermark_font)
            
            # Draw target multiplier (top right)
            target_text = f"Target: {target_multiplier:.2f}x"
            target_bbox = draw.textbbox((0, 0), target_text, font=target_font)
            target_width = target_bbox[2] - target_bbox[0]
            draw.text((width - target_width - 30, 30), target_text, fill=(255, 255, 255, 120), font=target_font)
            
            # Draw title text
            if crashed:
                title_text = "CRASHED AT"
            elif cash_out:
                title_text = "CASHED OUT AT"
            else:
                title_text = "CURRENT MULTIPLIER"
                
            title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (width - title_width) // 2
            title_y = 80
            draw.text((title_x, title_y), title_text, fill=(255, 255, 255, 180), font=title_font)
            
            # Draw main multiplier text
            multiplier_text = f"{current_multiplier:.2f}x"
            multiplier_bbox = draw.textbbox((0, 0), multiplier_text, font=multiplier_font)
            multiplier_width = multiplier_bbox[2] - multiplier_bbox[0]
            multiplier_x = (width - multiplier_width) // 2
            multiplier_y = 140
            
            # Add glow effect for multiplier text
            glow_offsets = [(2, 2), (-2, -2), (2, -2), (-2, 2), (0, 2), (0, -2), (2, 0), (-2, 0)]
            glow_color = tuple(list(text_color) + [80])  # Semi-transparent version
            for offset in glow_offsets:
                draw.text((multiplier_x + offset[0], multiplier_y + offset[1]), 
                         multiplier_text, fill=glow_color, font=multiplier_font)
            
            # Main multiplier text
            draw.text((multiplier_x, multiplier_y), multiplier_text, fill=text_color, font=multiplier_font)
            
            # Draw progress bar background
            bar_y = height - 80
            bar_height = 12
            bar_margin = 60
            bar_bg_color = (44, 62, 80)  # Darker blue-gray
            
            # Background bar (full width)
            draw.rectangle([bar_margin, bar_y, width - bar_margin, bar_y + bar_height], 
                          fill=bar_bg_color)
            
            # Progress bar fill
            bar_width = width - (2 * bar_margin)
            
            # Calculate progress based on target
            if target_multiplier > 0:
                progress = min(current_multiplier / target_multiplier, 1.0)
            else:
                progress = min(current_multiplier / 10.0, 1.0)  # Fallback
                
            fill_width = int(bar_width * progress)
            
            if fill_width > 0:
                draw.rectangle([bar_margin, bar_y, bar_margin + fill_width, bar_y + bar_height], 
                              fill=bar_color)
            
            # Draw progress indicator circle
            circle_x = bar_margin + fill_width
            circle_y = bar_y + (bar_height // 2)
            circle_radius = 8
            
            # Circle background (dark)
            draw.ellipse([circle_x - circle_radius, circle_y - circle_radius,
                         circle_x + circle_radius, circle_y + circle_radius], 
                        fill=(255, 255, 255))
            
            # Inner circle with bar color
            inner_radius = 5
            draw.ellipse([circle_x - inner_radius, circle_y - inner_radius,
                         circle_x + inner_radius, circle_y + inner_radius], 
                        fill=bar_color)
            
            # Add special effects for crashed state
            if crashed:
                # Add some red overlay effects
                overlay = Image.new('RGBA', (width, height), (231, 76, 60, 30))
                img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
            
            # Add special effects for cash out state
            elif cash_out:
                # Add some green overlay effects  
                overlay = Image.new('RGBA', (width, height), (46, 204, 113, 20))
                img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
            
            # Convert to bytes
            buf = io.BytesIO()
            img.save(buf, format='PNG', quality=95)
            buf.seek(0)
            
            # Create discord File object
            file = discord.File(buf, filename="crash_game.png")
            
            # Create embed
            embed = discord.Embed(color=0x2B2D31)
            embed.set_image(url="attachment://crash_game.png")
            
            return embed, file
            
        except Exception as e:
            print(f"Error generating crash image: {e}")
            
            # Simple fallback
            embed = discord.Embed(
                title="Crash Game",
                description=f"Current Multiplier: {current_multiplier:.2f}x",
                color=0x2B2D31)
                
            return embed, None


def setup(bot):
    bot.add_cog(CrashCog(bot))
