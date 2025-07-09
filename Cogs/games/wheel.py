import discord
import asyncio
import random
import time
import io
import math
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class WheelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        # Define color multipliers
        self.colors = {
            "gray": {"emoji": "⚪", "multiplier": 0, "chance": 50},
            "yellow": {"emoji": "🟡", "multiplier": 1.5, "chance": 25},
            "red": {"emoji": "🔴", "multiplier": 2, "chance": 15},
            "blue": {"emoji": "🔵", "multiplier": 3, "chance": 7},
            "green": {"emoji": "🟢", "multiplier": 5, "chance": 3}
        }
        # Calculate total chance to verify it sums to 100
        self.total_chance = sum(color["chance"] for color in self.colors.values())

    async def generate_wheel_image(self, result_color, bet_amount, winnings, spins=1):
        """Generate a visual wheel image with modern circular design"""
        # Create image with dark blue background like the reference
        width, height = 800, 700
        bg_color = (52, 73, 94)  # Dark blue-gray background
        image = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(image)

        # Try to load fonts
        try:
            title_font = ImageFont.truetype("arial.ttf", 32)
            large_font = ImageFont.truetype("arial.ttf", 24)
            medium_font = ImageFont.truetype("arial.ttf", 18)
            small_font = ImageFont.truetype("arial.ttf", 14)
            stats_font = ImageFont.truetype("arial.ttf", 16)
        except:
            title_font = ImageFont.load_default()
            large_font = ImageFont.load_default()
            medium_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
            stats_font = ImageFont.load_default()

        # Wheel parameters - centered higher up
        center_x, center_y = width//2, height//2 - 80
        outer_radius = 180
        inner_radius = 140
        
        # Define segments with proper colors and angles
        segments = [
            {"color": "gray", "rgb": (128, 128, 128), "start": 0, "size": 180},      # 50% - 180 degrees
            {"color": "yellow", "rgb": (255, 215, 0), "start": 180, "size": 90},    # 25% - 90 degrees  
            {"color": "red", "rgb": (220, 20, 60), "start": 270, "size": 54},       # 15% - 54 degrees
            {"color": "blue", "rgb": (30, 144, 255), "start": 324, "size": 25.2},   # 7% - 25.2 degrees
            {"color": "green", "rgb": (50, 205, 50), "start": 349.2, "size": 10.8}  # 3% - 10.8 degrees
        ]

        # Draw outer circle (rim)
        draw.ellipse([center_x - outer_radius, center_y - outer_radius,
                     center_x + outer_radius, center_y + outer_radius], 
                    fill=(70, 70, 70), outline=(100, 100, 100), width=3)

        # Draw segments as arcs on the rim
        for segment in segments:
            start_angle = segment["start"]
            end_angle = start_angle + segment["size"]
            
            # Draw the colored segment on the rim
            for r in range(inner_radius, outer_radius, 2):
                draw.arc([center_x - r, center_y - r, center_x + r, center_y + r],
                        start_angle, end_angle, fill=segment["rgb"], width=2)

        # Draw inner circle (darker)
        draw.ellipse([center_x - inner_radius, center_y - inner_radius,
                     center_x + inner_radius, center_y + inner_radius], 
                    fill=(40, 40, 40), outline=(80, 80, 80), width=2)

        # Draw center circle
        center_radius = 15
        draw.ellipse([center_x - center_radius, center_y - center_radius,
                     center_x + center_radius, center_y + center_radius], 
                    fill=(200, 200, 200), outline=(255, 255, 255), width=2)

        # Draw pointer at top (like the reference image)
        pointer_x = center_x
        pointer_y = center_y - outer_radius - 20
        
        # Draw pointer triangle (pointing down)
        triangle_size = 12
        draw.polygon([
            (pointer_x, pointer_y + triangle_size),
            (pointer_x - triangle_size//2, pointer_y - triangle_size//2),
            (pointer_x + triangle_size//2, pointer_y - triangle_size//2)
        ], fill=(0, 255, 0))  # Green pointer

        # Calculate which segment the pointer is pointing to
        pointer_angle = 270  # Top position (270 degrees)
        result_segment = None
        for segment in segments:
            start = segment["start"]
            end = start + segment["size"]
            # Normalize angles
            if start <= pointer_angle <= end or (start > end and (pointer_angle >= start or pointer_angle <= end)):
                result_segment = segment
                break

        # Draw stats boxes at bottom (like the reference)
        stats_y = height - 150
        box_width = 110
        box_height = 60
        box_spacing = 15
        
        # Calculate total width needed for all boxes
        total_boxes = len(self.colors)
        total_width = total_boxes * box_width + (total_boxes - 1) * box_spacing
        start_x = (width - total_width) // 2
        
        # Draw stats boxes for each color
        for i, (color_name, color_data) in enumerate(self.colors.items()):
            box_x = start_x + i * (box_width + box_spacing)
            
            # Box background - highlight the result color
            if color_name == result_color:
                box_color = (80, 200, 120)  # Bright green for result
                border_color = (0, 255, 0)
            else:
                box_color = (60, 60, 60)  # Dark gray for others
                border_color = (100, 100, 100)
            
            # Draw rounded rectangle for box
            self.draw_rounded_rectangle(draw, 
                [box_x, stats_y, box_x + box_width, stats_y + box_height],
                radius=8, fill=box_color, outline=border_color, width=2)
            
            # Add color indicator circle
            circle_radius = 8
            circle_x = box_x + 20
            circle_y = stats_y + 15
            
            # Get segment color
            segment_color = None
            for segment in segments:
                if segment["color"] == color_name:
                    segment_color = segment["rgb"]
                    break
            
            if segment_color:
                draw.ellipse([circle_x - circle_radius, circle_y - circle_radius,
                             circle_x + circle_radius, circle_y + circle_radius],
                            fill=segment_color, outline=(255, 255, 255), width=1)
            
            # Add multiplier text
            multiplier = color_data["multiplier"]
            mult_text = f"{multiplier}x" if multiplier > 0 else "0x"
            draw.text((box_x + box_width//2, stats_y + 35), mult_text, 
                     font=stats_font, fill=(255, 255, 255), anchor="mm")
            
            # Add percentage text
            percentage = color_data["chance"]
            perc_text = f"{percentage}%"
            draw.text((box_x + box_width//2, stats_y + 50), perc_text, 
                     font=small_font, fill=(200, 200, 200), anchor="mm")

        # Draw result information above the boxes
        result_y = stats_y - 80
        
        # Result background
        result_width = 400
        result_height = 50
        result_x = (width - result_width) // 2
        
        # Get result color
        result_rgb = None
        for segment in segments:
            if segment["color"] == result_color:
                result_rgb = segment["rgb"]
                break
        
        if result_rgb:
            self.draw_rounded_rectangle(draw, 
                [result_x, result_y, result_x + result_width, result_y + result_height],
                radius=10, fill=result_rgb, outline=(255, 255, 255), width=2)
        
        # Result text
        result_emoji = self.colors[result_color]["emoji"]
        result_multiplier = self.colors[result_color]["multiplier"]
        
        result_text = f"{result_emoji} {result_color.upper()} - {result_multiplier}x"
        draw.text((width//2, result_y + 25), result_text, font=large_font, fill=(255, 255, 255), anchor="mm")
        
        # Winnings text below result
        if winnings > 0:
            win_text = f"Won: {winnings:.2f} credits"
            win_color = (0, 255, 0)
        else:
            win_text = f"Lost: {bet_amount:.2f} tokens"
            win_color = (255, 100, 100)
            
        draw.text((width//2, result_y + 60), win_text, font=medium_font, fill=win_color, anchor="mm")

        # Add BetSync branding at top
        draw.text((width//2, 30), "BetSync Wheel", font=title_font, fill=(255, 255, 255), anchor="mm")

        # Save to buffer
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    def draw_rounded_rectangle(self, draw, xy, radius, fill=None, outline=None, width=1):
        """Draw a rounded rectangle"""
        x1, y1, x2, y2 = xy
        
        # Draw four corners
        draw.ellipse((x1, y1, x1 + radius * 2, y1 + radius * 2), fill=fill, outline=outline, width=width)
        draw.ellipse((x2 - radius * 2, y1, x2, y1 + radius * 2), fill=fill, outline=outline, width=width)
        draw.ellipse((x1, y2 - radius * 2, x1 + radius * 2, y2), fill=fill, outline=outline, width=width)
        draw.ellipse((x2 - radius * 2, y2 - radius * 2, x2, y2), fill=fill, outline=outline, width=width)
        
        # Draw four sides
        draw.rectangle((x1 + radius, y1, x2 - radius, y2), fill=fill, outline=None)
        draw.rectangle((x1, y1 + radius, x2, y2 - radius), fill=fill, outline=None)
        
        # Draw outline if specified
        if outline:
            draw.line((x1 + radius, y1, x2 - radius, y1), fill=outline, width=width)  # Top
            draw.line((x1 + radius, y2, x2 - radius, y2), fill=outline, width=width)  # Bottom
            draw.line((x1, y1 + radius, x1, y2 - radius), fill=outline, width=width)  # Left
            draw.line((x2, y1 + radius, x2, y2 - radius), fill=outline, width=width)  # Right

    @commands.command(aliases=["wh"])
    async def wheel(self, ctx, bet_amount: str = None, spins: int = 1):
        """Play the wheel game - bet on colors with different multipliers!"""
        # Limit the number of spins to 15
        if spins > 15:
            spins = 15
        elif spins < 1:
            spins = 1
        if not bet_amount:
            embed = discord.Embed(
                title="<a:hersheyparkSpin:1345317103158431805> How to Play Wheel",
                description=(
                    "**Wheel** is a game where you bet and win based on where the wheel lands.\n\n"
                    "**Usage:** `!wheel <amount> [currency_type]`\n"
                    "**Example:** `!wheel 100` or `!wheel 100 tokens`\n\n"
                    "**Colors and Multipliers:**\n"
                    "⚪ **Gray** - 0x (Loss)\n"
                    "🟡 **Yellow** - 1.5x\n"
                    "🔴 **Red** - 2x\n"
                    "🔵 **Blue** - 3x\n"
                    "🟢 **Green** - 5x\n\n"
                    "You bet using points.\n"
                    "- Winnings are always paid in points."
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
        #oading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Preparing Wheel Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount using currency_helper
        from Cogs.utils.currency_helper import process_bet_amount
        
        # First process the bet amount for a single spin
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount*spins, loading_message)
        
        # If processing failed, return the error
        if not success:
            await loading_message.delete() 
            return await ctx.reply(embed=error_embed)
            
        # Extract needed values from bet_info
        tokens_used = bet_info["tokens_used"]
        #credits_used = bet_info["credits_used"]
        total_bet = bet_info["total_bet_amount"]
        bet_amount_value = total_bet
        
        # Calculate total amounts for multiple spins
        total_tokens_used = tokens_used * spins
        #total_credits_used = credits_used * spins
        
        # Verify user has enough for all spins
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
            
        #tokens_balance = user_data['tokens']
        #credits_balance = user_data['credits']
        
        # Check if user has enough 
            
        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "bet_amount": bet_amount_value,
            "tokens_used": total_tokens_used,
            #"credits_used": total_credits_used,
            "spins": spins
        }
        

        # Delete loading message
        await loading_message.delete()

        # Calculate results for all spins with house edge (3-5%)
        house_edge = 0.04  # 4% house edge

        # Store results for all spins
        spin_results = []
        total_winnings = 0
        bet_total = tokens_used 
        total_bet_amount = bet_total * spins

        # Calculate results for each spin
        for _ in range(spins):
            # Apply house edge to outcome calculation
            if random.random() < house_edge:
                # Force a loss (gray) more often for house edge
                result_color = "gray"
            else:
                # Normal weighted random selection
                random_value = random.randint(1, self.total_chance)
                cumulative = 0
                result_color = None

                for color, data in self.colors.items():
                    cumulative += data["chance"]
                    if random_value <= cumulative:
                        result_color = color
                        break

            # Get multiplier for the result
            result_multiplier = self.colors[result_color]["multiplier"]
            result_emoji = self.colors[result_color]["emoji"]

            # Calculate winnings for this spin (always paid out in credits)
            winnings = bet_total * result_multiplier
            total_winnings += winnings

            # Add this result to our results list
            spin_results.append({
                "color": result_color,
                "emoji": result_emoji,
                "multiplier": result_multiplier,
                "winnings": winnings
            })

        # Generate wheel image with result
        # Use the first spin result for the main wheel display
        main_result = spin_results[0]
        wheel_image = await self.generate_wheel_image(
            main_result["color"], 
            bet_total, 
            main_result["winnings"], 
            spins
        )

        # Create result embed
        wheel_embed = discord.Embed(
            title="🎰 Wheel of Fortune Results",
            color=0x00FFAE
        )

        # Format bet description
        wheel_embed.description = f"**Bet:** {total_tokens_used:.2f} points"
        if spins > 1:
            wheel_embed.description += f" ({bet_total:.2f} per spin)"

        # Create a summary of all results for multiple spins
        if spins > 1:
            results_summary = ""
            wins_count = 0
            for i, result in enumerate(spin_results):
                if result["multiplier"] > 0:
                    wins_count += 1
                results_summary += f"Spin {i+1}: {result['emoji']} ({result['color'].capitalize()}) - {result['multiplier']}x - {result['winnings']:.2f} points\n"

            # Add overall results summary
            wheel_embed.add_field(
                name=f"Spin Results ({wins_count}/{spins} wins)",
                value=results_summary,
                inline=False
            )
        else:
            # Single spin - show main result
            main_result = spin_results[0]
            wheel_embed.add_field(
                name="Result",
                value=f"{main_result['emoji']} **{main_result['color'].capitalize()}** - {main_result['multiplier']}x multiplier",
                inline=False
            )

        # Add overall result field
        if total_winnings > 0:
            net_profit = total_winnings - total_bet_amount
            wheel_embed.add_field(
                name=f"🎉 Overall Results",
                value=f"**Total Bet:** {total_bet_amount:.2f}\n**Total Winnings:** {total_winnings:.2f} points\n**Net Profit:** {net_profit:.2f} points",
                inline=False
            )

            if net_profit > 0:
                wheel_embed.color = 0x00FF00  # Green for overall profit
            else:
                wheel_embed.color = 0xFFA500  # Orange for win but overall loss/breakeven

            # Update user's balance with winnings
            db.update_balance(ctx.author.id, total_winnings, "credits", "$inc")

            # Process stats and history for each spin
            server_db = Servers()
            server_data = server_db.fetch_server(ctx.guild.id) if ctx.guild else None

            # Track wins and losses for stats
            wins_count = 0
            losses_count = 0
            house_profit = 0

            # History entries for batch update
            history_entries = []
            server_history_entries = []

            for i, result in enumerate(spin_results):
                # Process individual spin history
                if result["multiplier"] > 0:
                    # This spin was a win
                    wins_count += 1
                    history_entry = {
                        "type": "win",
                        "game": "wheel",
                        "bet": bet_total,
                        "amount": result["winnings"],
                        "multiplier": result["multiplier"],
                        "timestamp": int(time.time()) + i  # Ensure unique timestamps
                    }

                    if server_data:
                        server_bet_history_entry = {
                            "type": "win",
                            "game": "wheel",
                            "user_id": ctx.author.id,
                            "user_name": ctx.author.name,
                            "bet": bet_total,
                            "amount": result["winnings"],
                            "multiplier": result["multiplier"],
                            "timestamp": int(time.time()) + i
                        }
                        server_history_entries.append(server_bet_history_entry)
                        house_profit += bet_total - result["winnings"]
                else:
                    # This spin was a loss
                    losses_count += 1
                    history_entry = {
                        "type": "loss",
                        "game": "wheel",
                        "bet": bet_total,
                        "amount": bet_total,
                        "multiplier": result["multiplier"],
                        "timestamp": int(time.time()) + i
                    }

                    if server_data:
                        server_bet_history_entry = {
                            "type": "loss",
                            "game": "wheel",
                            "user_id": ctx.author.id,
                            "user_name": ctx.author.name,
                            "bet": bet_total,
                            "amount": bet_total,
                            "multiplier": result["multiplier"],
                            "timestamp": int(time.time()) + i
                        }
                        server_history_entries.append(server_bet_history_entry)
                        house_profit += bet_total

                history_entries.append(history_entry)

            # Update user's stats with all spins
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$push": {"history": {"$each": history_entries, "$slice": -100}},
                    "$inc": {
                        "total_played": spins,
                        "total_won": wins_count,
                        "total_lost": losses_count,
                        "total_earned": total_winnings,
                        "total_spent": total_bet_amount - total_winnings if total_winnings < total_bet_amount else 0
                    }
                }
            )

            # Update server data with all spins
            if server_data and server_history_entries:
                server_db.update_server_profit(ctx, ctx.guild.id, house_profit, game="wheel")

            # Set final embed color based on overall result
            if total_winnings > total_bet_amount:
                wheel_embed.color = 0x00FF00  # Green for overall profit
            elif total_winnings > 0:
                wheel_embed.color = 0xFFA500  # Orange for some wins but overall loss
            else:
                wheel_embed.color = 0xFF0000  # Red for complete loss

        else:
            # Complete loss (all gray)
            wheel_embed.color = 0xFF0000
            wheel_embed.add_field(
                name="😢 Game Over",
                value=f"**Total Loss:** {total_bet_amount:.2f}",
                inline=False
            )

        # Create Discord file from image
        wheel_file = discord.File(wheel_image, filename="wheel_result.png")
        wheel_embed.set_image(url="attachment://wheel_result.png")

        # Send the result with image
        wheel_message = await ctx.reply(embed=wheel_embed, file=wheel_file)

        # Create play again view
        view = PlayAgainView(self, ctx, bet_total, spins=spins)
        await wheel_message.edit(view=view)
        view.message = wheel_message

        # Remove user from ongoing games
        self.ongoing_games.pop(ctx.author.id, None)


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=15, spins=1):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.spins = spins
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="play_again")
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Use the same bet amount and spins without specifying currency
        # The currency helper in the wheel command will handle balance checks and currency selection
        await self.cog.wheel(self.ctx, str(self.bet_amount), self.spins)

    async def on_timeout(self):
        # Disable the button when the view times out
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass


def setup(bot):
    bot.add_cog(WheelCog(bot))