
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

            view = ChannelControlView(self, ctx.author.id)
            await channel.send(embed=welcome_embed, view=view)

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

    @commands.command(aliases=["dc", "deletechannel"])
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
    async def delete_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        await interaction.channel.delete(reason=f"Channel deleted by {interaction.user}")

    @discord.ui.button(label="Add Member", style=discord.ButtonStyle.secondary, emoji="➕")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="Only the channel owner can add members.",
                color=0xFF0000
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        member = await self.get_member_input(interaction, "Add")
        if not member:
            return

        if member.bot:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Member",
                description="You cannot add bots to private channels.",
                color=0xFF0000
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            # Add read and send permissions for the member
            await interaction.channel.set_permissions(
                member,
                read_messages=True,
                send_messages=True,
                read_message_history=True,
                embed_links=True,
                attach_files=True
            )
            
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Member Added",
                description=f"{member.mention} has been added to this channel.",
                color=0x00FFAE
            )
            await interaction.followup.send(embed=embed)
            
            # Update activity
            self.cog.update_channel_activity(self.owner_id)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Permission Error",
                description="I don't have permission to add members to this channel.",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to add member: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Remove Member", style=discord.ButtonStyle.secondary, emoji="➖")
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="Only the channel owner can remove members.",
                color=0xFF0000
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        member = await self.get_member_input(interaction, "Remove")
        if not member:
            return

        # Check if member has access to the channel
        permissions = interaction.channel.permissions_for(member)
        if not permissions.read_messages:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Not in Channel",
                description=f"{member.mention} doesn't have access to this channel.",
                color=0xFF0000
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            # Remove permissions for the member
            await interaction.channel.set_permissions(member, overwrite=None)
            
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Member Removed",
                description=f"{member.mention} has been removed from this channel.",
                color=0x00FFAE
            )
            await interaction.followup.send(embed=embed)
            
            # Update activity
            self.cog.update_channel_activity(self.owner_id)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Permission Error",
                description="I don't have permission to modify channel permissions.",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to remove member: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Channel Info", style=discord.ButtonStyle.primary, emoji="ℹ️")
    async def channel_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        
        # Get members with read access (excluding @everyone and bots)
        members_with_access = []
        for member in channel.guild.members:
            if not member.bot and channel.permissions_for(member).read_messages:
                # Don't count members who only have access through @everyone
                overwrite = channel.overwrites_for(member)
                if overwrite.read_messages is True or member.id == self.owner_id:
                    members_with_access.append(member)

        embed = discord.Embed(
            title=":information_source: | Channel Information",
            description=f"Information about {channel.name}",
            color=0x00FFAE
        )
        embed.add_field(
            name="👑 Owner",
            value=f"<@{self.owner_id}>",
            inline=True
        )
        embed.add_field(
            name="👥 Members",
            value=f"{len(members_with_access)} members",
            inline=True
        )
        embed.add_field(
            name="📅 Created",
            value=f"<t:{int(channel.created_at.timestamp())}:R>",
            inline=True
        )
        embed.add_field(
            name="🔗 Channel ID",
            value=f"`{channel.id}`",
            inline=False
        )
        
        # Show last activity if available
        if self.owner_id in self.cog.user_channels:
            last_activity = self.cog.user_channels[self.owner_id]['last_activity']
            embed.add_field(
                name="⏰ Last Activity",
                value=f"<t:{int(last_activity.timestamp())}:R>",
                inline=True
            )

        if len(members_with_access) > 1:
            member_list = "\n".join([f"• {member.display_name}" for member in members_with_access[:10]])
            if len(members_with_access) > 10:
                member_list += f"\n• ... and {len(members_with_access) - 10} more"
            embed.add_field(
                name="👥 Member List",
                value=member_list,
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def get_member_input(self, interaction: discord.Interaction, action: str):
        """Get member input via message instead of modal"""
        embed = discord.Embed(
            title=f"ℹ️ | {action} Member",
            description=f"Please type the username, display name, or user ID of the member to {action.lower()}:",
            color=0x3498db
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.cog.bot.wait_for('message', check=check, timeout=60)
            member_input = msg.content.strip()

            # Try to find the member
            member = None
            guild = interaction.guild

            # Try by mention (if it starts with <@)
            if member_input.startswith('<@') and member_input.endswith('>'):
                user_id = member_input[2:-1]
                if user_id.startswith('!'):
                    user_id = user_id[1:]
                try:
                    member = guild.get_member(int(user_id))
                except ValueError:
                    pass

            # Try by user ID
            if not member and member_input.isdigit():
                member = guild.get_member(int(member_input))

            # Try by username or display name
            if not member:
                member = discord.utils.find(
                    lambda m: m.name.lower() == member_input.lower() or 
                             m.display_name.lower() == member_input.lower(),
                    guild.members
                )

            if not member:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Member Not Found",
                    description=f"Could not find member: `{member_input}`",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return None

            return member

        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Timed Out",
                description="Timed out waiting for member input",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return None

def setup(bot):
    bot.add_cog(PrivateChannels(bot))
