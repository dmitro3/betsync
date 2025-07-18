
import discord
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
import os
from dotenv import load_dotenv

load_dotenv()

class ReferralsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.main_server_id = int(os.environ.get('MAINSERVER_ID', 0))
        
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
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Loading Referral Data...",
            description="Please wait while we fetch the referral statistics.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        try:
            # Get all invites for the server
            guild = self.bot.get_guild(self.main_server_id)
            if not guild:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Server Error",
                    description="Could not access the main server.",
                    color=0xFF0000
                )
                await loading_message.edit(embed=embed)
                return
            
            # Get user's invites
            user_invites = []
            try:
                invites = await guild.invites()
                user_invites = [invite for invite in invites if invite.inviter and invite.inviter.id == target_user.id]
            except discord.Forbidden:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Permission Error", 
                    description="Bot doesn't have permission to view invites.",
                    color=0xFF0000
                )
                await loading_message.edit(embed=embed)
                return
            
            # Calculate statistics
            total_uses = sum(invite.uses for invite in user_invites)
            current_invites = total_uses  # This would need tracking for leaves/kicks
            total_joins = total_uses
            
            # Note: Discord API doesn't provide leave/kick data directly
            # These would need to be tracked via bot events
            rejoins = 0  # Would need custom tracking
            left_users = 0  # Would need custom tracking
            
            # Adjust current invites (this is simplified - real implementation would need event tracking)
            current_invites = max(0, total_joins - rejoins - left_users)
            
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
            
            embed.add_field(
                name="🔗 Active Invite Links",
                value=f"```{len(user_invites):,}```",
                inline=True
            )
            
            # Calculate success rate
            if total_joins > 0:
                retention_rate = ((current_invites / total_joins) * 100)
                embed.add_field(
                    name="📈 Retention Rate",
                    value=f"```{retention_rate:.1f}%```",
                    inline=True
                )
            
            # Show invite codes if user has any
            if user_invites:
                invite_info = []
                for invite in user_invites[:5]:  # Show max 5 invites
                    uses_text = f"{invite.uses} use{'s' if invite.uses != 1 else ''}"
                    max_uses_text = f"/{invite.max_uses}" if invite.max_uses else ""
                    channel_name = invite.channel.name if invite.channel else "Unknown"
                    
                    invite_info.append(f"`{invite.code}` • {uses_text}{max_uses_text} • #{channel_name}")
                
                embed.add_field(
                    name="🎫 Recent Invite Codes",
                    value="\n".join(invite_info) if invite_info else "No active invites",
                    inline=False
                )
                
                if len(user_invites) > 5:
                    embed.add_field(
                        name="ℹ️ Additional Info",
                        value=f"Showing 5 of {len(user_invites)} total invite codes",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="🎫 Invite Codes",
                    value="No active invite codes found",
                    inline=False
                )
            
            # Leaderboard position (simplified)
            try:
                all_invites = await guild.invites()
                invite_counts = {}
                for invite in all_invites:
                    if invite.inviter:
                        invite_counts[invite.inviter.id] = invite_counts.get(invite.inviter.id, 0) + invite.uses
                
                sorted_users = sorted(invite_counts.items(), key=lambda x: x[1], reverse=True)
                user_rank = next((i + 1 for i, (user_id, _) in enumerate(sorted_users) if user_id == target_user.id), "N/A")
                
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
        """Track when a member joins via invite (for future implementation)"""
        # This would store join data for tracking purposes
        # Implementation would require comparing invite uses before/after join
        pass
    
    @commands.Cog.listener() 
    async def on_member_remove(self, member):
        """Track when a member leaves (for future implementation)"""
        # This would update referral statistics when users leave
        pass

def setup(bot):
    bot.add_cog(ReferralsCog(bot))
