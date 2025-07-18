
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
            
            await loading_message.edit(embed=embed)
            
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

def setup(bot):
    bot.add_cog(ReferralsCog(bot))
