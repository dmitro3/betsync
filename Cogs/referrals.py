
import discord
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
import os
import datetime
import json
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

class ReferralView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
    
    @discord.ui.button(label="Referral Rewards", style=discord.ButtonStyle.green, emoji="💰")
    async def referral_rewards(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only view your own referral rewards!", ephemeral=True)
            return
        
        # Create coming soon embed
        embed = discord.Embed(
            title=":information_source: | Coming Soon",
            description="Referral rewards are currently under development and will be available soon!",
            color=0xFFAA00
        )
        
        embed.add_field(
            name="💰 What to Expect",
            value="• Earn rewards based on your invited members' activity\n• Different reward rates based on your rank\n• Claimable LTC and BTC points\n• Community bonus system",
            inline=False
        )
        
        embed.add_field(
            name="🔔 Stay Tuned",
            value="Keep inviting members and leveling up your account!\nRewards will be calculated retroactively when the system launches.",
            inline=False
        )
        
        embed.set_footer(
            text="BetSync Casino • Feature coming soon",
            icon_url=self.cog.bot.user.avatar.url
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Leaderboard", style=discord.ButtonStyle.secondary, emoji="🏆")
    async def referral_leaderboard(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            # Get top 10 users by current invites
            leaderboard = list(self.cog.referral_collection.find().sort("current_invites", -1).limit(10))
            
            if not leaderboard:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | No Data",
                    description="No referral data found.",
                    color=0xFF0000
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Create leaderboard embed
            embed = discord.Embed(
                title="🏆 | Referral Leaderboard",
                description="Top inviters by current invites",
                color=0x00FFAE
            )
            
            leaderboard_text = ""
            medals = ["🥇", "🥈", "🥉"]
            
            for i, data in enumerate(leaderboard):
                rank = i + 1
                user_id = data.get("user_id")
                current_invites = data.get("current_invites", 0)
                
                # Skip users with 0 invites
                if current_invites == 0:
                    continue
                
                # Get medal or number
                if rank <= 3:
                    rank_emoji = medals[rank - 1]
                else:
                    rank_emoji = f"`{rank}.`"
                
                # Format the line
                leaderboard_text += f"{rank_emoji} <@{user_id}> - **{current_invites:,}** invites\n"
            
            if not leaderboard_text:
                embed.add_field(
                    name="📊 Rankings",
                    value="No users with invites found.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📊 Rankings",
                    value=leaderboard_text,
                    inline=False
                )
            
            # Add user's position if not in top 10
            if interaction.user.id != self.user_id:
                target_user_id = interaction.user.id
            else:
                target_user_id = self.user_id
            
            user_in_top_10 = any(data.get("user_id") == target_user_id for data in leaderboard[:10])
            
            if not user_in_top_10:
                all_users = list(self.cog.referral_collection.find().sort("current_invites", -1))
                user_rank = next((i + 1 for i, data in enumerate(all_users) if data.get("user_id") == target_user_id), None)
                
                if user_rank:
                    user_data = next((data for data in all_users if data.get("user_id") == target_user_id), None)
                    if user_data:
                        user_invites = user_data.get("current_invites", 0)
                        embed.add_field(
                            name="📍 Your Position",
                            value=f"`{user_rank}.` <@{target_user_id}> - **{user_invites:,}** invites",
                            inline=False
                        )
            
            embed.set_footer(
                text="BetSync Casino • Referral System",
                icon_url=self.cog.bot.user.avatar.url
            )
            embed.timestamp = discord.utils.utcnow()
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while fetching leaderboard: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    def get_rank_info(self, level):
        """Get rank information based on level"""
        if level >= 40:
            return {"name": "Diamond Elite", "emoji": "💎", "percentage": 0.08}
        elif level >= 25:
            return {"name": "Platinum Master", "emoji": "🏆", "percentage": 0.06}
        elif level >= 15:
            return {"name": "Gold Expert", "emoji": "🥇", "percentage": 0.04}
        elif level >= 5:
            return {"name": "Silver Pro", "emoji": "🥈", "percentage": 0.02}
        else:
            return {"name": "Bronze Member", "emoji": "🥉", "percentage": 0.01}
    
    def get_xp_for_level(self, level):
        """Calculate XP required for a specific level"""
        if level <= 1:
            return 0
        # Exponential XP curve: level^2 * 100
        return (level - 1) ** 2 * 100

class ReferralClaimView(discord.ui.View):
    def __init__(self, cog, user_id, ltc_points, btc_points):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.ltc_points = ltc_points
        self.btc_points = btc_points
        self.ltc_claimed = False
        self.btc_claimed = False
    
    @discord.ui.button(label="Claim LTC Reward", style=discord.ButtonStyle.secondary, emoji="🪙")
    async def claim_ltc(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only claim your own rewards!", ephemeral=True)
            return
        
        if self.ltc_claimed:
            await interaction.response.send_message("You have already claimed your LTC reward!", ephemeral=True)
            return
        
        if self.ltc_points < 50:
            await interaction.response.send_message("You need at least 50 LTC points to claim!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Add points to user balance
            users_db = Users()
            users_db.update_balance(self.user_id, self.ltc_points, "points", "$inc")
            
            # Reset LTC points in database
            self.cog.referral_collection.update_one(
                {"user_id": self.user_id, "type": "rewards"},
                {"$set": {"ltc_points": 0}}
            )
            
            self.ltc_claimed = True
            button.disabled = True
            button.label = "LTC Claimed ✓"
            
            await interaction.edit_original_response(view=self)
            
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | LTC Reward Claimed",
                description=f"Successfully claimed **{self.ltc_points} points** as LTC community bonus!",
                color=0x00FFAE
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to claim LTC reward: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Claim BTC Reward", style=discord.ButtonStyle.secondary, emoji="₿")
    async def claim_btc(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only claim your own rewards!", ephemeral=True)
            return
        
        if self.btc_claimed:
            await interaction.response.send_message("You have already claimed your BTC reward!", ephemeral=True)
            return
        
        if self.btc_points < 50:
            await interaction.response.send_message("You need at least 50 BTC points to claim!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Add points to user balance
            users_db = Users()
            users_db.update_balance(self.user_id, self.btc_points, "points", "$inc")
            
            # Reset BTC points in database
            self.cog.referral_collection.update_one(
                {"user_id": self.user_id, "type": "rewards"},
                {"$set": {"btc_points": 0}}
            )
            
            self.btc_claimed = True
            button.disabled = True
            button.label = "BTC Claimed ✓"
            
            await interaction.edit_original_response(view=self)
            
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | BTC Reward Claimed",
                description=f"Successfully claimed **{self.btc_points} points** as BTC community bonus!",
                color=0x00FFAE
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to claim BTC reward: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class ReferralsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.main_server_id = int(os.environ.get('MAINSERVER_ID', 0))
        
        # Initialize referral tracking database
        self.mongodb = MongoClient(os.environ["MONGO"])
        self.db = self.mongodb["BetSync"]
        self.referral_collection = self.db["referrals"]
        
    @commands.command(aliases=["ref", "referrals"])
    async def referral(self, ctx, user: discord.Member = None):
        """View referral statistics (Main server only)
        
        Usage: !referral [user]
        """
        # Check if command is being used in the main server
        if ctx.guild.id != self.main_server_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Wrong Server",
                description="This command can only be used in the main server.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Default to command author if no user specified
        target_user = user or ctx.author
        
        # Send loading embed
        loading_embed = discord.Embed(
            title="<a:loading:1344611780638412811> | Loading Referral Data",
            description="Please wait while we fetch the referral statistics.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        try:
            # Get referral data from database
            referral_data = self.referral_collection.find_one({"user_id": target_user.id})
            
            if not referral_data:
                # Initialize referral data if not exists
                referral_data = {
                    "user_id": target_user.id,
                    "total_joins": 0,
                    "current_invites": 0,
                    "rejoins": 0,
                    "left_users": 0,
                    "invited_users": [],
                    "left_user_ids": [],
                    "rejoined_user_ids": []
                }
                self.referral_collection.insert_one(referral_data)
            
            # Extract statistics
            total_joins = referral_data.get("total_joins", 0)
            current_invites = referral_data.get("current_invites", 0)
            rejoins = referral_data.get("rejoins", 0)
            left_users = referral_data.get("left_users", 0)
            
            # Create main embed
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Referral Statistics",
                description=f"Showing referral data for {target_user.mention}",
                color=0x00FFAE
            )
            
            # Add user avatar
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # Main statistics
            embed.add_field(
                name="📊 Current Invites",
                value=f"```{current_invites:,}```",
                inline=True
            )
            
            embed.add_field(
                name="👥 Total Joins",
                value=f"```{total_joins:,}```",
                inline=True
            )
            
            embed.add_field(
                name="🔄 Rejoins",
                value=f"```{rejoins:,}```",
                inline=True
            )
            
            embed.add_field(
                name="👋 Left Users",
                value=f"```{left_users:,}```",
                inline=True
            )
            
            # Show recent activity if available
            invited_users = referral_data.get("invited_users", [])
            if invited_users:
                recent_invites = invited_users[-5:]  # Show last 5 invites
                invite_list = []
                for user_data in recent_invites:
                    join_date = user_data.get("join_date", "Unknown")
                    if isinstance(join_date, str):
                        try:
                            join_date = datetime.datetime.fromisoformat(join_date).strftime("%m/%d/%Y")
                        except:
                            join_date = "Unknown"
                    invite_list.append(f"<@{user_data['user_id']}> - {join_date}")
                
                embed.add_field(
                    name="🎯 Recent Invites",
                    value="\n".join(invite_list) if invite_list else "No recent invites",
                    inline=False
                )
            
            # Leaderboard position
            try:
                # Get all users sorted by current invites
                leaderboard = list(self.referral_collection.find().sort("current_invites", -1))
                user_rank = next((i + 1 for i, data in enumerate(leaderboard) if data["user_id"] == target_user.id), "N/A")
                
                embed.add_field(
                    name="🏆 Server Rank",
                    value=f"```#{user_rank}```" if user_rank != "N/A" else "```Unranked```",
                    inline=True
                )
            except:
                pass
            
            # Calculate casino profit from invited users (Admin only)
            from Cogs.admin import AdminCommands
            admin_cog = self.bot.get_cog('AdminCommands')
            if admin_cog and admin_cog.is_admin(ctx.author.id):
                try:
                    # Get all invited user IDs
                    invited_user_ids = [user_data['user_id'] for user_data in invited_users]
                    
                    if invited_user_ids:
                        # Calculate total casino profit from these users
                        users_db = Users()
                        total_wagered = 0
                        total_won = 0
                        
                        for user_id in invited_user_ids:
                            user_data = users_db.fetch_user(user_id)
                            if user_data:
                                total_wagered += user_data.get("total_spent", 0)
                                total_won += user_data.get("total_earned", 0)
                        
                        casino_profit = total_wagered - total_won
                        casino_profit_usd = casino_profit * 0.0212  # Convert to USD
                        
                        # Add casino profit field for admins
                        embed.add_field(
                            name="💰 Casino Profit (Admin)",
                            value=f"**{casino_profit:,.2f}** points (`${casino_profit_usd:,.2f}`)\nFrom {len(invited_user_ids)} invited users",
                            inline=False
                        )
                except Exception as e:
                    print(f"Error calculating casino profit: {e}")
            
            # Footer
            embed.set_footer(
                text=f"BetSync Casino • Requested by {ctx.author.name}",
                icon_url=self.bot.user.avatar.url
            )
            
            # Add timestamp
            embed.timestamp = discord.utils.utcnow()
            
            # Create view with referral rewards and leaderboard buttons
            view = ReferralView(self, target_user.id)
            
            await loading_message.edit(embed=embed, view=view)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while fetching referral data: {str(e)}",
                color=0xFF0000
            )
            await loading_message.edit(embed=embed)

    @commands.command(aliases=["manageinvites", "mi"])
    async def manage_invites(self, ctx, action: str = None, user: discord.Member = None, amount: int = None):
        """Manage user invite counts (Admin only)
        
        Usage: 
        !manageinvites add @user 5 - Add 5 current invites
        !manageinvites remove @user 3 - Remove 3 current invites
        !manageinvites addrejoins @user 2 - Add 2 rejoin invites
        !manageinvites removerejoins @user 1 - Remove 1 rejoin invite
        !manageinvites reset @user - Reset all invite data for user
        """
        # Check if command is being used in the main server
        if ctx.guild.id != self.main_server_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Wrong Server",
                description="This command can only be used in the main server.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Check if user is admin (you may want to adjust this check based on your admin system)
        from Cogs.admin import AdminCommands
        admin_cog = self.bot.get_cog('AdminCommands')
        if not admin_cog or not admin_cog.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        if not action or not user:
            embed = discord.Embed(
                title=":information_source: | Manage Invites Usage",
                description="Commands to manage user invite statistics",
                color=0x00FFAE
            )
            embed.add_field(
                name="Available Commands",
                value="""
`!manageinvites add @user amount` - Add current invites
`!manageinvites remove @user amount` - Remove current invites
`!manageinvites addrejoins @user amount` - Add rejoin count
`!manageinvites removerejoins @user amount` - Remove rejoin count
`!manageinvites reset @user` - Reset all invite data
                """,
                inline=False
            )
            return await ctx.reply(embed=embed)
        
        # Get or create user referral data
        referral_data = self.referral_collection.find_one({"user_id": user.id})
        if not referral_data:
            referral_data = {
                "user_id": user.id,
                "total_joins": 0,
                "current_invites": 0,
                "rejoins": 0,
                "left_users": 0,
                "invited_users": [],
                "left_user_ids": [],
                "rejoined_user_ids": []
            }
            self.referral_collection.insert_one(referral_data)
        
        action = action.lower()
        
        try:
            if action == "add":
                if amount is None or amount < 1:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Amount",
                        description="Please specify a positive amount to add.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
                
                self.referral_collection.update_one(
                    {"user_id": user.id},
                    {"$inc": {"current_invites": amount, "total_joins": amount}}
                )
                
                embed = discord.Embed(
                    title="<:yes:1355501647538815106> | Invites Added",
                    description=f"Successfully added **{amount}** current invites to {user.mention}",
                    color=0x00FFAE
                )
                
            elif action == "remove":
                if amount is None or amount < 1:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Amount",
                        description="Please specify a positive amount to remove.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
                
                # Don't let current invites go below 0
                current_invites = referral_data.get("current_invites", 0)
                remove_amount = min(amount, current_invites)
                
                self.referral_collection.update_one(
                    {"user_id": user.id},
                    {"$inc": {"current_invites": -remove_amount}}
                )
                
                embed = discord.Embed(
                    title="<:yes:1355501647538815106> | Invites Removed",
                    description=f"Successfully removed **{remove_amount}** current invites from {user.mention}",
                    color=0x00FFAE
                )
                
            elif action == "addrejoins":
                if amount is None or amount < 1:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Amount",
                        description="Please specify a positive amount to add.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
                
                self.referral_collection.update_one(
                    {"user_id": user.id},
                    {"$inc": {"rejoins": amount}}
                )
                
                embed = discord.Embed(
                    title="<:yes:1355501647538815106> | Rejoins Added",
                    description=f"Successfully added **{amount}** rejoins to {user.mention}",
                    color=0x00FFAE
                )
                
            elif action == "removerejoins":
                if amount is None or amount < 1:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Amount",
                        description="Please specify a positive amount to remove.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
                
                # Don't let rejoins go below 0
                current_rejoins = referral_data.get("rejoins", 0)
                remove_amount = min(amount, current_rejoins)
                
                self.referral_collection.update_one(
                    {"user_id": user.id},
                    {"$inc": {"rejoins": -remove_amount}}
                )
                
                embed = discord.Embed(
                    title="<:yes:1355501647538815106> | Rejoins Removed",
                    description=f"Successfully removed **{remove_amount}** rejoins from {user.mention}",
                    color=0x00FFAE
                )
                
            elif action == "reset":
                self.referral_collection.update_one(
                    {"user_id": user.id},
                    {"$set": {
                        "total_joins": 0,
                        "current_invites": 0,
                        "rejoins": 0,
                        "left_users": 0,
                        "invited_users": [],
                        "left_user_ids": [],
                        "rejoined_user_ids": []
                    }}
                )
                
                embed = discord.Embed(
                    title="<:yes:1355501647538815106> | Invite Data Reset",
                    description=f"Successfully reset all invite data for {user.mention}",
                    color=0x00FFAE
                )
                
            else:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Action",
                    description="Valid actions: `add`, `remove`, `addrejoins`, `removerejoins`, `reset`",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
            
            embed.set_footer(text=f"Action performed by {ctx.author.name}", icon_url=ctx.author.avatar.url)
            await ctx.reply(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while managing invites: {str(e)}",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Track when a member joins via invite"""
        if member.guild.id != self.main_server_id:
            return
            
        try:
            # Get current invites
            current_invites = await member.guild.invites()
            
            # Compare with stored invites to find which one was used
            stored_invites = await self.get_stored_invites(member.guild.id)
            
            inviter_id = None
            for current_invite in current_invites:
                if current_invite.inviter:
                    stored_invite = stored_invites.get(current_invite.code)
                    if stored_invite and current_invite.uses > stored_invite["uses"]:
                        inviter_id = current_invite.inviter.id
                        break
            
            # Update stored invites
            await self.update_stored_invites(member.guild.id, current_invites)
            
            if inviter_id:
                # Check if this person was previously invited by anyone (including this inviter)
                previous_inviter_data = self.referral_collection.find_one(
                    {"left_user_ids": member.id}
                )
                
                is_rejoin = False
                is_invite_switch = False
                
                if previous_inviter_data:
                    previous_inviter_id = previous_inviter_data["user_id"]
                    
                    if previous_inviter_id == inviter_id:
                        # Same inviter - this is a rejoin
                        is_rejoin = True
                        # Ensure inviter data exists first
                        self.referral_collection.update_one(
                            {"user_id": inviter_id},
                            {
                                "$setOnInsert": {
                                    "user_id": inviter_id,
                                    "total_joins": 0,
                                    "current_invites": 0,
                                    "rejoins": 0,
                                    "left_users": 0,
                                    "invited_users": [],
                                    "left_user_ids": [],
                                    "rejoined_user_ids": []
                                }
                            },
                            upsert=True
                        )
                        # Remove from left users and add to rejoined (but don't increment current_invites for rejoins)
                        self.referral_collection.update_one(
                            {"user_id": inviter_id},
                            {
                                "$pull": {"left_user_ids": member.id},
                                "$addToSet": {"rejoined_user_ids": member.id},
                                "$inc": {"rejoins": 1}
                            }
                        )
                    else:
                        # Different inviter - this is an invite switch
                        is_invite_switch = True
                        # Remove from previous inviter's left_user_ids (no changes to their stats)
                        self.referral_collection.update_one(
                            {"user_id": previous_inviter_id},
                            {"$pull": {"left_user_ids": member.id}}
                        )
                        
                        # For invite switches, this should count as a rejoin for the new inviter, NOT a new invite
                        # Ensure new inviter data exists first
                        self.referral_collection.update_one(
                            {"user_id": inviter_id},
                            {
                                "$setOnInsert": {
                                    "user_id": inviter_id,
                                    "total_joins": 0,
                                    "current_invites": 0,
                                    "rejoins": 0,
                                    "left_users": 0,
                                    "invited_users": [],
                                    "left_user_ids": [],
                                    "rejoined_user_ids": []
                                }
                            },
                            upsert=True
                        )
                        
                        # Add as rejoin for new inviter (not a new invite)
                        self.referral_collection.update_one(
                            {"user_id": inviter_id},
                            {
                                "$inc": {"rejoins": 1},
                                "$addToSet": {"rejoined_user_ids": member.id}
                            }
                        )
                
                if not is_rejoin and not is_invite_switch:
                    # Completely new invite
                    invite_data = {
                        "user_id": member.id,
                        "username": member.name,
                        "join_date": datetime.datetime.utcnow().isoformat()
                    }
                    
                    # Ensure inviter data exists and update (use upsert to create if doesn't exist)
                    self.referral_collection.update_one(
                        {"user_id": inviter_id},
                        {
                            "$inc": {"total_joins": 1, "current_invites": 1},
                            "$addToSet": {"invited_users": invite_data},
                            "$setOnInsert": {
                                "user_id": inviter_id,
                                "rejoins": 0,
                                "left_users": 0,
                                "left_user_ids": [],
                                "rejoined_user_ids": []
                            }
                        },
                        upsert=True
                    )
                
                if is_rejoin:
                    print(f"[REFERRAL] {member.name} (rejoined) via invite from {inviter_id}")
                elif is_invite_switch:
                    print(f"[REFERRAL] {member.name} (switched invites) from {previous_inviter_data['user_id']} to {inviter_id}")
                else:
                    print(f"[REFERRAL] {member.name} (joined) via invite from {inviter_id}")
                
        except Exception as e:
            print(f"Error tracking member join: {e}")
    
    @commands.Cog.listener() 
    async def on_member_remove(self, member):
        """Track when a member leaves"""
        if member.guild.id != self.main_server_id:
            return
            
        try:
            # Find who invited this user
            referral_data = self.referral_collection.find_one(
                {"invited_users.user_id": member.id}
            )
            
            if referral_data:
                inviter_id = referral_data["user_id"]
                
                # Update referral statistics
                self.referral_collection.update_one(
                    {"user_id": inviter_id},
                    {
                        "$inc": {"left_users": 1, "current_invites": -1},
                        "$addToSet": {"left_user_ids": member.id}
                    }
                )
                
                print(f"[REFERRAL] {member.name} left, deducted from {inviter_id}'s current invites")
                
        except Exception as e:
            print(f"Error tracking member leave: {e}")
    
    async def get_stored_invites(self, guild_id):
        """Get stored invite data for comparison"""
        try:
            stored_data = self.db["invite_cache"].find_one({"guild_id": guild_id})
            return stored_data.get("invites", {}) if stored_data else {}
        except:
            return {}
    
    async def update_stored_invites(self, guild_id, current_invites):
        """Update stored invite data"""
        try:
            invite_data = {}
            for invite in current_invites:
                if invite.inviter:
                    invite_data[invite.code] = {
                        "uses": invite.uses,
                        "inviter_id": invite.inviter.id
                    }
            
            self.db["invite_cache"].update_one(
                {"guild_id": guild_id},
                {"$set": {"invites": invite_data}},
                upsert=True
            )
        except Exception as e:
            print(f"Error updating stored invites: {e}")

def setup(bot):
    bot.add_cog(ReferralsCog(bot))
