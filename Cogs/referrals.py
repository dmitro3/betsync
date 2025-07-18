
import discord
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
import os
import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

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
            title="<a:loading:1344611780638412811> | Loading Referral Data...",
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
            
            # Footer
            embed.set_footer(
                text=f"BetSync Casino • Requested by {ctx.author.name}",
                icon_url=self.bot.user.avatar.url
            )
            
            # Add timestamp
            embed.timestamp = discord.utils.utcnow()
            
            # Create view with referral rewards button
            view = ReferralRewardsView(self, target_user.id)
            await loading_message.edit(embed=embed, view=view)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while fetching referral data: {str(e)}",
                color=0xFF0000
            )
            await loading_message.edit(embed=embed)

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

@commands.command(aliases=["refrew", "rrewards"])
    async def referralrewards(self, ctx, user: discord.Member = None):
        """View referral rewards (Main server only)"""
        # Check if command is being used in the main server
        if ctx.guild.id != self.main_server_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Wrong Server",
                description="This command can only be used in the main server.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        target_user = user or ctx.author
        await self.show_referral_rewards(ctx, target_user)
    
    async def show_referral_rewards(self, ctx, user):
        """Show referral rewards for a user"""
        loading_embed = discord.Embed(
            title="<a:loading:1344611780638412811> | Loading Referral Rewards...",
            description="Please wait while we calculate your referral rewards.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        try:
            # Get or create referral rewards data
            rewards_data = self.db["referral_rewards"].find_one({"user_id": user.id})
            if not rewards_data:
                rewards_data = {
                    "user_id": user.id,
                    "total_profit_tracked": 0,
                    "btc_rewards": 0,
                    "ltc_rewards": 0,
                    "level": 1,
                    "total_claimed": 0,
                    "level_progress": 0
                }
                self.db["referral_rewards"].insert_one(rewards_data)
            
            # Calculate current profit from invited users
            current_profit = await self.calculate_referral_profit(user.id)
            
            # Get user's referral level and percentage
            level_data = self.get_referral_level_data(rewards_data.get("level", 1))
            
            # Calculate available rewards
            total_rewards = current_profit * (level_data["percentage"] / 100)
            btc_rewards = total_rewards * 0.6  # 60% in BTC
            ltc_rewards = total_rewards * 0.4  # 40% in LTC
            
            # Round down to whole numbers
            btc_claimable = int(btc_rewards)
            ltc_claimable = int(ltc_rewards)
            
            # Create embed
            embed = discord.Embed(
                title=":information_source: | Referral Partner Rewards",
                description=f"**Exclusive rewards for our top community builders**\n\n*View your partnership earnings and claim your commission*",
                color=0x00FFAE
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            
            # Level info
            embed.add_field(
                name="🏆 Partnership Level",
                value=f"{level_data['emoji']} **{level_data['name']}**\nCommission Rate: **{level_data['percentage']}%**",
                inline=True
            )
            
            # Available rewards
            embed.add_field(
                name="💰 Available Commission",
                value=f"🟡 **{btc_claimable:,}** BTC Points\n🔵 **{ltc_claimable:,}** LTC Points",
                inline=True
            )
            
            # Progress bar for next level
            if level_data["level"] < 4:
                next_level = self.get_referral_level_data(level_data["level"] + 1)
                progress = min(rewards_data.get("level_progress", 0) / level_data["progress_needed"], 1.0)
                bar_length = 10
                filled_bars = int(progress * bar_length)
                empty_bars = bar_length - filled_bars
                
                embed.add_field(
                    name=f"📈 Progress to {next_level['name']}",
                    value=f"```\n[{'■' * filled_bars}{'□' * empty_bars}] {int(progress * 100)}%\n```\n{rewards_data.get('level_progress', 0):,}/{level_data['progress_needed']:,} community activity",
                    inline=False
                )
            
            # Stats
            total_claimed = rewards_data.get("total_claimed", 0)
            embed.add_field(
                name="📊 Partnership Statistics",
                value=f"• **Total Earned:** {total_claimed:,} points\n• **Community Value:** ${current_profit * 0.0212:.2f}\n• **Active Referrals:** {await self.get_active_referral_count(user.id)}",
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ About Partnership Rewards",
                value="```\nEarn commission based on your community's activity and engagement.\nHigher levels unlock better commission rates and exclusive perks.\n```",
                inline=False
            )
            
            embed.set_footer(
                text=f"BetSync Casino • Requested by {ctx.author.name}",
                icon_url=self.bot.user.avatar.url
            )
            
            # Create view with claim buttons
            view = ReferralRewardsClaimView(self, user.id, btc_claimable, ltc_claimable)
            await loading_message.edit(embed=embed, view=view)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while fetching referral rewards: {str(e)}",
                color=0xFF0000
            )
            await loading_message.edit(embed=embed)
    
    def get_referral_level_data(self, level):
        """Get referral level data"""
        levels = {
            1: {"name": "Community Builder", "emoji": "🌱", "percentage": 5.0, "progress_needed": 10000, "level": 1},
            2: {"name": "Partnership Elite", "emoji": "⭐", "percentage": 6.0, "progress_needed": 25000, "level": 2},
            3: {"name": "Brand Ambassador", "emoji": "💎", "percentage": 7.0, "progress_needed": 50000, "level": 3},
            4: {"name": "Executive Partner", "emoji": "👑", "percentage": 8.0, "progress_needed": 0, "level": 4}
        }
        return levels.get(level, levels[1])
    
    async def calculate_referral_profit(self, user_id):
        """Calculate total profit from user's referrals"""
        try:
            # Get user's current invites
            referral_data = self.referral_collection.find_one({"user_id": user_id})
            if not referral_data:
                return 0
            
            invited_users = referral_data.get("invited_users", [])
            if not invited_users:
                return 0
            
            # Get invited user IDs
            invited_user_ids = [user_data["user_id"] for user_data in invited_users]
            
            # Calculate profit from these users
            users_db = Users()
            total_profit = 0
            
            for invited_user_id in invited_user_ids:
                user_data = users_db.fetch_user(invited_user_id)
                if user_data:
                    total_lost = user_data.get("total_lost", 0)
                    total_won = user_data.get("total_won", 0)
                    user_profit = total_lost - total_won
                    if user_profit > 0:
                        total_profit += user_profit
            
            return total_profit
            
        except Exception as e:
            print(f"Error calculating referral profit: {e}")
            return 0
    
    async def get_active_referral_count(self, user_id):
        """Get count of active referrals"""
        referral_data = self.referral_collection.find_one({"user_id": user_id})
        if referral_data:
            return referral_data.get("current_invites", 0)
        return 0
    
    def track_referral_profit(self, user_id, bet_amount, game_result, won_amount=0):
        """Track profit for referral rewards when a referred user bets"""
        try:
            # Find who invited this user
            referral_data = self.referral_collection.find_one(
                {"invited_users.user_id": user_id}
            )
            
            if referral_data:
                inviter_id = referral_data["user_id"]
                
                # Calculate profit (positive when user loses, negative when user wins)
                if game_result == "loss":
                    profit = bet_amount
                else:  # win
                    profit = -(won_amount - bet_amount)  # Net loss for house
                
                # Update referrer's profit tracking
                self.db["referral_rewards"].update_one(
                    {"user_id": inviter_id},
                    {
                        "$inc": {"total_profit_tracked": profit},
                        "$setOnInsert": {
                            "user_id": inviter_id,
                            "btc_rewards": 0,
                            "ltc_rewards": 0,
                            "level": 1,
                            "total_claimed": 0,
                            "level_progress": 0
                        }
                    },
                    upsert=True
                )
                
                return True
            return False
            
        except Exception as e:
            print(f"Error tracking referral profit: {e}")
            return False

class ReferralRewardsView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
    
    @discord.ui.button(label="Referral Rewards", style=discord.ButtonStyle.blurple, emoji="💎")
    async def show_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("You can only view your own referral rewards!", ephemeral=True)
        
        await interaction.response.defer()
        await self.cog.show_referral_rewards(interaction, interaction.user)

class ReferralRewardsClaimView(discord.ui.View):
    def __init__(self, cog, user_id, btc_amount, ltc_amount):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.btc_amount = btc_amount
        self.ltc_amount = ltc_amount
        
        # Disable buttons if amounts are less than 50
        if btc_amount < 50:
            self.claim_btc.disabled = True
        if ltc_amount < 50:
            self.claim_ltc.disabled = True
    
    @discord.ui.button(label="Claim BTC Points", style=discord.ButtonStyle.green, emoji="🟡")
    async def claim_btc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("You cannot claim someone else's rewards!", ephemeral=True)
        
        if self.btc_amount < 50:
            return await interaction.response.send_message("Minimum claim amount is 50 points!", ephemeral=True)
        
        await self.process_claim(interaction, "BTC", self.btc_amount)
    
    @discord.ui.button(label="Claim LTC Points", style=discord.ButtonStyle.green, emoji="🔵")
    async def claim_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("You cannot claim someone else's rewards!", ephemeral=True)
        
        if self.ltc_amount < 50:
            return await interaction.response.send_message("Minimum claim amount is 50 points!", ephemeral=True)
        
        await self.process_claim(interaction, "LTC", self.ltc_amount)
    
    async def process_claim(self, interaction, currency, amount):
        """Process the reward claim"""
        await interaction.response.defer()
        
        try:
            # Add points to user's balance
            users_db = Users()
            users_db.update_balance(self.user_id, amount, "points", "$inc")
            
            # Update rewards data
            rewards_collection = self.cog.db["referral_rewards"]
            rewards_collection.update_one(
                {"user_id": self.user_id},
                {
                    "$inc": {
                        f"{currency.lower()}_rewards": -amount,
                        "total_claimed": amount,
                        "level_progress": amount // 10  # Progress based on claimed amount
                    }
                },
                upsert=True
            )
            
            # Check for level up
            rewards_data = rewards_collection.find_one({"user_id": self.user_id})
            if rewards_data:
                current_level = rewards_data.get("level", 1)
                level_data = self.cog.get_referral_level_data(current_level)
                progress = rewards_data.get("level_progress", 0)
                
                if progress >= level_data["progress_needed"] and current_level < 4:
                    # Level up!
                    new_level = current_level + 1
                    rewards_collection.update_one(
                        {"user_id": self.user_id},
                        {
                            "$set": {"level": new_level},
                            "$inc": {"level_progress": -level_data["progress_needed"]}
                        }
                    )
                    
                    new_level_data = self.cog.get_referral_level_data(new_level)
                    level_up_embed = discord.Embed(
                        title="<:yes:1355501647538815106> | Partnership Level Up!",
                        description=f"🎉 **Congratulations!** You've been promoted to **{new_level_data['name']}** {new_level_data['emoji']}\n\n**New Commission Rate:** {new_level_data['percentage']}%",
                        color=0x00FFAE
                    )
                    await interaction.followup.send(embed=level_up_embed)
            
            # Send success message
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Commission Claimed!",
                description=f"Successfully claimed **{amount:,}** {currency} points!",
                color=0x00FFAE
            )
            
            # Get new balance
            user_data = users_db.fetch_user(self.user_id)
            new_balance = user_data.get("points", 0) if user_data else 0
            
            embed.add_field(
                name="💰 New Balance",
                value=f"**{new_balance:,}** points",
                inline=True
            )
            
            embed.set_footer(text="BetSync Casino • Partnership Rewards", icon_url=self.cog.bot.user.avatar.url)
            
            # Disable the claimed button
            if currency == "BTC":
                self.claim_btc.disabled = True
                self.btc_amount = 0
            else:
                self.claim_ltc.disabled = True
                self.ltc_amount = 0
            
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Claim Failed",
                description=f"An error occurred while processing your claim: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)

def setup(bot):
    bot.add_cog(ReferralsCog(bot))
