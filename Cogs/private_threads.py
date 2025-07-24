
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

            await channel.send(embed=welcome_embed)

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

def setup(bot):
    bot.add_cog(PrivateChannels(bot))
