
import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class WheelSelectionView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, spins, game_id, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.spins = spins
        self.game_id = game_id
        self.message = None

    @discord.ui.button(label="🎰 SPIN THE WHEEL", style=discord.ButtonStyle.primary, emoji="🎰", custom_id="spin_wheel")
    async def spin_wheel(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)
        
        # Start the wheel spin animation
        await self.cog.start_wheel_spin(self.ctx, interaction, self.bet_amount, self.spins, self.game_id)

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
                
                # Remove from ongoing games
                if self.game_id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.game_id]
            except:
                pass


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
        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Start a new game with the same parameters
        await self.cog.wheel(self.ctx, str(self.bet_amount), self.spins)

    async def on_timeout(self):
        # Disable the button when the view times out
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass


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
                title="🎰 **WHEEL OF FORTUNE** 🎰",
                description=(
                    "```\n"
                    "🎯 Spin the Wheel & Win Big!\n"
                    "```\n"
                    "**📋 How to Play:**\n"
                    "> Basic: `!wheel <amount> [spins]`\n"
                    "> Example: `!wheel 100 5`\n\n"
                    
                    "**🎨 Colors and Multipliers:**\n"
                    "> ⚪ **Gray** - 0x (Loss) - 50% chance\n"
                    "> 🟡 **Yellow** - 1.5x - 25% chance\n"
                    "> 🔴 **Red** - 2x - 15% chance\n"
                    "> 🔵 **Blue** - 3x - 7% chance\n"
                    "> 🟢 **Green** - 5x - 3% chance\n\n"
                    
                    "**💰 Betting Info:**\n"
                    "> • You bet using points\n"
                    "> • Winnings are always paid in points\n"
                    "> • Multiple spins available (max 15)\n\n"
                    
                    "```diff\n"
                    "+ The higher the multiplier, the rarer the color!\n"
                    "```"
                ),
                color=0x00FFAE
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1345317103158431805.png")
            embed.set_footer(text="🎰 BetSync Casino • Ready to spin?", icon_url=self.bot.user.avatar.url)
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
            title="🎰 **Setting Up The Wheel...**",
            description=(
                "```\n"
                "🔄 Processing your bet...\n"
                "📊 Checking balance...\n"
                "🎰 Preparing the wheel...\n"
                "```"
            ),
            color=0xFFD700
        )
        loading_embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1345317103158431805.png")
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
        total_bet = bet_info["total_bet_amount"]
        bet_amount_value = total_bet
        
        # Calculate total amounts for multiple spins
        total_tokens_used = tokens_used * spins
        
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

        # Generate unique game ID
        import uuid
        game_id = str(uuid.uuid4())
            
        # Mark game as ongoing
        self.ongoing_games[game_id] = {
            "user_id": ctx.author.id,
            "bet_amount": bet_amount_value,
            "tokens_used": total_tokens_used,
            "spins": spins
        }

        # Create wheel selection embed
        embed = discord.Embed(
            title="🎰 **WHEEL OF FORTUNE** 🎰",
            description=(
                f"```\n"
                f"💰 Your Bet: {total_tokens_used:,.2f} points\n"
                f"🎰 Spins: {spins}\n"
                f"```\n"
                f"**🎨 The Wheel Colors:**\n\n"
                
                f"⚪ **Gray Zone** - 0x (50% chance)\n"
                f"> The danger zone - lose it all!\n\n"
                
                f"🟡 **Yellow Zone** - 1.5x (25% chance)\n"
                f"> Small but sweet victory!\n\n"
                
                f"🔴 **Red Zone** - 2x (15% chance)\n"
                f"> Double your money!\n\n"
                
                f"🔵 **Blue Zone** - 3x (7% chance)\n"
                f"> Triple threat reward!\n\n"
                
                f"🟢 **Green Zone** - 5x (3% chance)\n"
                f"> The jackpot zone!\n\n"
                
                f"```diff\n"
                f"🎰 Ready to test your luck? Click to spin!\n"
                f"```"
            ),
            color=0x00FFAE
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1345317103158431805.png")
        embed.set_footer(text="🎰 BetSync Casino • Fortune favors the bold!", icon_url=self.bot.user.avatar.url)

        # Create view with spin button
        view = WheelSelectionView(self, ctx, bet_amount_value, spins, game_id, timeout=30)
        
        # Update the loading message
        message = await loading_message.edit(embed=embed, view=view)
        view.message = message

    async def start_wheel_spin(self, ctx, interaction, bet_amount, spins, game_id):
        """Start the wheel spinning animation and process results"""
        # Remove from ongoing games
        if game_id in self.ongoing_games:
            del self.ongoing_games[game_id]

        # Calculate results for all spins with house edge (3-5%)
        house_edge = 0.04  # 4% house edge

        # Store results for all spins
        spin_results = []
        total_winnings = 0
        bet_total = bet_amount / spins if spins > 1 else bet_amount
        total_bet_amount = bet_total * spins

        # Calculate results for each spin
        for spin_num in range(spins):
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

            # Calculate winnings for this spin
            winnings = bet_total * result_multiplier
            total_winnings += winnings

            # Add this result to our results list
            spin_results.append({
                "color": result_color,
                "emoji": result_emoji,
                "multiplier": result_multiplier,
                "winnings": winnings,
                "spin_number": spin_num + 1
            })

        # Show spinning animation
        await self.show_spinning_animation(interaction, spins)

        # Show results
        await self.show_wheel_results(ctx, interaction, spin_results, bet_total, total_bet_amount, total_winnings, spins)

    async def show_spinning_animation(self, interaction, spins):
        """Show spinning wheel animation"""
        spin_frames = ["🎰", "🔄", "⚡", "✨", "🎯"]
        
        for i in range(8):  # 8 animation frames
            frame = spin_frames[i % len(spin_frames)]
            
            embed = discord.Embed(
                title=f"{frame} **THE WHEEL IS SPINNING!** {frame}",
                description=(
                    f"```\n"
                    f"🌪️ The wheel spins faster and faster...\n"
                    f"🎰 Where will it land?\n"
                    f"⏳ {8-i} seconds remaining...\n"
                    f"```\n"
                    f"**🎨 Possible Outcomes:**\n"
                    f"> ⚪ Gray (0x) • 🟡 Yellow (1.5x) • 🔴 Red (2x)\n"
                    f"> 🔵 Blue (3x) • 🟢 Green (5x)\n\n"
                    f"```diff\n"
                    f"+ The suspense builds...\n"
                    f"```"
                ),
                color=0xFFD700
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1345317103158431805.png")
            embed.set_footer(text="🎰 BetSync Casino • The wheel decides your fate!", icon_url=interaction.client.user.avatar.url)
            
            try:
                await interaction.message.edit(embed=embed, view=None)
                if i < 7:  # Don't sleep on the last frame
                    await asyncio.sleep(0.8)
            except:
                break

    async def show_wheel_results(self, ctx, interaction, spin_results, bet_total, total_bet_amount, total_winnings, spins):
        """Show the final wheel results"""
        # Determine overall result
        net_profit = total_winnings - total_bet_amount
        
        # Create result embed
        if total_winnings > 0:
            if net_profit > 0:
                title = "🎉 **CONGRATULATIONS! BIG WIN!** 🎉"
                color = 0x00FF00
                result_icon = "<:yes:1355501647538815106>"
            else:
                title = "🎰 **PARTIAL WIN!** 🎰"
                color = 0xFFA500
                result_icon = "🟡"
        else:
            title = "💸 **BETTER LUCK NEXT TIME!** 💸"
            color = 0xFF4444
            result_icon = "<:no:1344252518305234987>"

        embed = discord.Embed(
            title=f"{result_icon} | {title}",
            color=color
        )

        # Format bet description
        embed.description = f"**💰 Total Bet:** {total_bet_amount:.2f} points"
        if spins > 1:
            embed.description += f" ({bet_total:.2f} per spin)"

        # Create a summary of all results for multiple spins
        if spins > 1:
            results_summary = ""
            wins_count = 0
            
            # Group results by color for cleaner display
            color_counts = {}
            for result in spin_results:
                color = result['color']
                if color not in color_counts:
                    color_counts[color] = {'count': 0, 'total_winnings': 0, 'emoji': result['emoji'], 'multiplier': result['multiplier']}
                color_counts[color]['count'] += 1
                color_counts[color]['total_winnings'] += result['winnings']
                if result['multiplier'] > 0:
                    wins_count += 1

            # Display grouped results
            for color, data in color_counts.items():
                if data['count'] > 0:
                    results_summary += f"{data['emoji']} **{color.capitalize()}** x{data['count']} - {data['multiplier']}x each - {data['total_winnings']:.2f} points total\n"

            embed.add_field(
                name=f"🎰 Spin Results ({wins_count}/{spins} wins)",
                value=results_summary,
                inline=False
            )
        else:
            # Single spin - show main result
            main_result = spin_results[0]
            embed.add_field(
                name="🎯 Result",
                value=f"{main_result['emoji']} **{main_result['color'].capitalize()}** - {main_result['multiplier']}x multiplier",
                inline=False
            )

        # Add overall result field
        if total_winnings > 0:
            embed.add_field(
                name=f"🏆 Final Results",
                value=(
                    f"**Total Winnings:** {total_winnings:.2f} points\n"
                    f"**Net Profit:** {net_profit:+.2f} points\n"
                    f"**Return:** {(total_winnings/total_bet_amount)*100:.1f}%"
                ),
                inline=False
            )

            # Update user's balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, total_winnings, "credits", "$inc")

            # Process stats and history
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
                        "timestamp": int(time.time()) + i
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

        else:
            # Complete loss (all gray)
            embed.add_field(
                name="💸 Game Over",
                value=f"**Total Loss:** {total_bet_amount:.2f} points\n**Better luck next time!**",
                inline=False
            )

        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1345317103158431805.png")
        embed.set_footer(text="🎰 BetSync Casino • Want to spin again?", icon_url=interaction.client.user.avatar.url)

        # Create play again view
        view = PlayAgainView(self, ctx, bet_total, spins=spins)
        await interaction.message.edit(embed=embed, view=view)
        view.message = interaction.message

        # Remove user from ongoing games
        self.ongoing_games.pop(ctx.author.id, None)


def setup(bot):
    bot.add_cog(WheelCog(bot))
