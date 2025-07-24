
import discord
from discord.ext import commands, tasks
import asyncio
import os
from datetime import datetime, timedelta
from Cogs.utils.mongo import Users

class PrivateChannels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_channels = {}  # Store user_id: {'channel_id': int, 'last_activity': datetime}
        self.cleanup_inactive_channels.start()
        
    def cog_unload(self):
        self.cleanup_inactive_channels.cancel()

    @tasks.loop(hours=1)  # Check every hour for inactive channels
    async def cleanup_inactive_channels(self):
        """Clean up channels that have been inactive for 24+ hours"""
        current_time = datetime.utcnow()
        channels_to_remove = []
        
        for user_id, channel_data in self.user_channels.items():
            channel_id = channel_data['channel_id']
            last_activity = channel_data['last_activity']
            
            # Check if 24 hours have passed since last activity
            if current_time - last_activity > timedelta(hours=24):
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await channel.delete(reason="Automatic cleanup - 24 hours of inactivity")
                    channels_to_remove.append(user_id)
                except Exception as e:
                    print(f"Error deleting inactive channel {channel_id}: {e}")
                    channels_to_remove.append(user_id)
        
        # Remove tracked channels that were deleted
        for user_id in channels_to_remove:
            del self.user_channels[user_id]

    @cleanup_inactive_channels.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    def update_channel_activity(self, user_id):
        """Update the last activity timestamp for a user's channel"""
        if user_id in self.user_channels:
            self.user_channels[user_id]['last_activity'] = datetime.utcnow()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Update activity when user sends a message in their private channel"""
        if message.author.bot:
            return
            
        # Check if message is in a tracked private channel
        for user_id, channel_data in self.user_channels.items():
            if message.channel.id == channel_data['channel_id'] and message.author.id == user_id:
                self.update_channel_activity(user_id)
                break

    @commands.command(aliases=["pc", "privatechannel"])
    async def create_private_channel(self, ctx):
        """Create a private channel for using commands privately"""
        # Check if user already has a private channel
        if ctx.author.id in self.user_channels:
            channel_id = self.user_channels[ctx.author.id]['channel_id']
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Channel Already Exists",
                    description=f"You already have an active private channel: {channel.mention}",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
            else:
                # Channel was deleted, remove from tracking
                del self.user_channels[ctx.author.id]

        # Get category ID from environment
        category_id = os.getenv('PT_CATEGORY_ID')
        if not category_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Configuration Error",
                description="Private channel category is not configured.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        try:
            category = ctx.guild.get_channel(int(category_id))
            if not category or not isinstance(category, discord.CategoryChannel):
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Configuration Error",
                    description="Invalid category configured for private channels.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

            # Create overwrites for the private channel
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                ctx.author: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True
                ),
                ctx.guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_channels=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True
                )
            }

            # Create the private channel
            channel = await category.create_text_channel(
                name=f"private-{ctx.author.display_name}",
                overwrites=overwrites,
                reason=f"Private channel created by {ctx.author}"
            )

            # Track the channel
            self.user_channels[ctx.author.id] = {
                'channel_id': channel.id,
                'last_activity': datetime.utcnow()
            }

            # Create control panel embed
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Private Channel Created",
                description=f"Your private channel has been created: {channel.mention}",
                color=0x00FFAE
            )
            embed.add_field(
                name="🎫 Channel Controls",
                value="Use the buttons in your channel to manage it",
                inline=False
            )
            embed.add_field(
                name="⏰ Auto Deletion",
                value="Channel will be deleted after 24 hours of inactivity",
                inline=False
            )
            embed.set_footer(text="BetSync • Private Channel System", icon_url=self.bot.user.avatar.url)

            # Send confirmation in original channel
            await ctx.reply(embed=embed)

            # Send welcome message in channel with controls
            welcome_embed = discord.Embed(
                title=":information_source: | Welcome to Your Private Channel",
                description=f"Hello {ctx.author.mention}! This is your private channel where you can use commands privately.",
                color=0x00FFAE
            )
            welcome_embed.add_field(
                name="📋 Available Actions",
                value="• Delete this channel\n• Add members to channel\n• Remove members from channel\n• View channel info",
                inline=False
            )
            welcome_embed.add_field(
                name="🔒 Privacy",
                value="Only you and added members can see this channel.",
                inline=False
            )
            welcome_embed.add_field(
                name="⏰ Auto Deletion",
                value="This channel will be automatically deleted after 24 hours of inactivity.",
                inline=False
            )

            # Create control view
            control_view = ChannelControlView(self, ctx.author.id)
            
            await channel.send(embed=welcome_embed, view=control_view)

        except discord.Forbidden:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Permission Error",
                description="I don't have permission to create channels in the specified category.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to create private channel: {str(e)}",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)

    @commands.command(aliases=["delc", "deletechannel"])
    async def delete_channel(self, ctx):
        """Delete your private channel"""
        # Check if user owns a private channel
        if ctx.author.id not in self.user_channels:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | No Channel Found",
                description="You don't have an active private channel.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        channel_id = self.user_channels[ctx.author.id]['channel_id']
        
        # Check if command is used in the user's private channel
        if ctx.channel.id != channel_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Wrong Channel",
                description="This command can only be used in your private channel.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Delete the channel
        embed = discord.Embed(
            title="<:yes:1355501647538815106> | Channel Deleting",
            description="This private channel will be deleted in 5 seconds...",
            color=0x00FFAE
        )
        await ctx.reply(embed=embed)

        await asyncio.sleep(5)

        # Remove from tracking
        del self.user_channels[ctx.author.id]

        # Delete the channel
        await ctx.channel.delete(reason=f"Channel deleted by {ctx.author}")

class ChannelControlView(discord.ui.View):
    def __init__(self, cog, owner_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.owner_id = owner_id

    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_channel(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="Only the channel owner can delete this channel.",
                color=0xFF0000
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title="<:yes:1355501647538815106> | Channel Deleting",
            description="This private channel will be deleted in 5 seconds...",
            color=0x00FFAE
        )
        await interaction.response.send_message(embed=embed)

        await asyncio.sleep(5)

        # Remove from tracking
        if self.owner_id in self.cog.user_channels:
            del self.cog.user_channels[self.owner_id]

        # Delete the channel
        await interaction.channel.delete(reason=f"Channel deleted by owner")

    @discord.ui.button(label="Add Member", style=discord.ButtonStyle.success, emoji="➕")
    async def add_member(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="Only the channel owner can add members.",
                color=0xFF0000
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        class AddMemberModal(discord.ui.Modal, title="Add Member to Channel"):
            def __init__(self):
                super().__init__()

            member_input = discord.ui.TextInput(
                label="Member to Add",
                placeholder="Enter username, user ID, or mention (@username)",
                required=True,
                max_length=100
            )

            async def on_submit(self, interaction: discord.Interaction):
                member_text = self.member_input.value.strip()
                
                # Try to find the member
                member = None
                
                # Remove @ if present
                if member_text.startswith('@'):
                    member_text = member_text[1:]
                
                # Try by ID first
                if member_text.isdigit():
                    member = interaction.guild.get_member(int(member_text))
                
                # Try by username or display name
                if not member:
                    for guild_member in interaction.guild.members:
                        if (guild_member.name.lower() == member_text.lower() or 
                            guild_member.display_name.lower() == member_text.lower()):
                            member = guild_member
                            break

                if not member:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Member Not Found",
                        description=f"Could not find member: `{member_text}`",
                        color=0xFF0000
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

                if member.id == interaction.user.id:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Member",
                        description="You cannot add yourself to your own channel.",
                        color=0xFF0000
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

                # Check if member already has access
                overwrites = interaction.channel.overwrites
                if member in overwrites:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Already Added",
                        description=f"{member.mention} already has access to this channel.",
                        color=0xFF0000
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

                # Add member to channel
                await interaction.channel.set_permissions(
                    member,
                    read_messages=True,
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True
                )

                embed = discord.Embed(
                    title="<:yes:1355501647538815106> | Member Added",
                    description=f"{member.mention} has been added to the channel.",
                    color=0x00FFAE
                )
                await interaction.response.send_message(embed=embed)

        await interaction.response.send_modal(AddMemberModal())

    @discord.ui.button(label="Remove Member", style=discord.ButtonStyle.secondary, emoji="➖")
    async def remove_member(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="Only the channel owner can remove members.",
                color=0xFF0000
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Get list of members with access (excluding owner and bot)
        overwrites = interaction.channel.overwrites
        removable_members = []
        
        for target, overwrite in overwrites.items():
            if (isinstance(target, discord.Member) and 
                target.id != self.owner_id and 
                target.id != interaction.guild.me.id and
                overwrite.read_messages is True):
                removable_members.append(target)

        if not removable_members:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | No Members",
                description="There are no members to remove from this channel.",
                color=0xFF0000
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        class RemoveMemberSelect(discord.ui.Select):
            def __init__(self, members):
                options = [
                    discord.SelectOption(
                        label=member.display_name,
                        description=f"@{member.name}",
                        value=str(member.id)
                    )
                    for member in members[:25]  # Discord limit
                ]
                super().__init__(placeholder="Select a member to remove...", options=options)

            async def callback(self, interaction: discord.Interaction):
                member = interaction.guild.get_member(int(self.values[0]))
                if not member:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Member Not Found",
                        description="Could not find the selected member.",
                        color=0xFF0000
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

                # Remove member from channel
                await interaction.channel.set_permissions(member, overwrite=None)

                embed = discord.Embed(
                    title="<:yes:1355501647538815106> | Member Removed",
                    description=f"{member.mention} has been removed from the channel.",
                    color=0x00FFAE
                )
                await interaction.response.send_message(embed=embed)

        class RemoveMemberView(discord.ui.View):
            def __init__(self, members):
                super().__init__(timeout=60)
                self.add_item(RemoveMemberSelect(members))

        view = RemoveMemberView(removable_members)
        embed = discord.Embed(
            title="➖ Remove Member",
            description="Select a member to remove from this channel:",
            color=0x00FFAE
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Channel Info", style=discord.ButtonStyle.primary, emoji="ℹ️")
    async def channel_info(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Get channel creation time and member list
        created_at = interaction.channel.created_at
        
        # Get list of members with access
        overwrites = interaction.channel.overwrites
        members_with_access = []
        
        for target, overwrite in overwrites.items():
            if (isinstance(target, discord.Member) and 
                overwrite.read_messages is True):
                members_with_access.append(target)

        # Get activity info if user is owner
        activity_info = ""
        if interaction.user.id == self.owner_id and self.owner_id in self.cog.user_channels:
            last_activity = self.cog.user_channels[self.owner_id]['last_activity']
            time_until_deletion = last_activity + timedelta(hours=24)
            activity_info = f"\n**Last Activity:** <t:{int(last_activity.timestamp())}:R>\n**Auto-Delete:** <t:{int(time_until_deletion.timestamp())}:R>"

        embed = discord.Embed(
            title="ℹ️ Channel Information",
            description=f"Information about {interaction.channel.mention}",
            color=0x00FFAE
        )
        
        embed.add_field(
            name="📋 Basic Info",
            value=f"**Name:** {interaction.channel.name}\n**ID:** `{interaction.channel.id}`\n**Created:** <t:{int(created_at.timestamp())}:R>{activity_info}",
            inline=False
        )
        
        embed.add_field(
            name="👤 Owner",
            value=f"<@{self.owner_id}>",
            inline=True
        )
        
        embed.add_field(
            name="👥 Members",
            value=f"{len(members_with_access)} total",
            inline=True
        )
        
        if members_with_access:
            member_list = "\n".join([f"• {member.mention}" for member in members_with_access[:10]])
            if len(members_with_access) > 10:
                member_list += f"\n• ... and {len(members_with_access) - 10} more"
            
            embed.add_field(
                name="📝 Member List",
                value=member_list,
                inline=False
            )

        embed.add_field(
            name="⏰ Auto-Deletion",
            value="This channel will be automatically deleted after 24 hours of inactivity.",
            inline=False
        )
        
        embed.set_footer(text="BetSync • Private Channel System", icon_url=interaction.guild.me.avatar.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(PrivateChannels(bot))
