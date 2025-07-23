import discord
from discord.ext import commands
from Cogs.utils.mongo import Servers

class ChannelManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_ids = self.load_admin_ids()

        # Add command check for disabled channels
        self.bot.add_check(self.check_disabled_channels)

    def load_admin_ids(self):
        """Load admin IDs from admins.txt file"""
        admin_ids = []
        try:
            with open("admins.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and line.isdigit():
                        admin_ids.append(int(line))
        except Exception as e:
            print(f"Error loading admin IDs: {e}")
        return admin_ids

    def is_admin(self, user_id):
        """Check if a user ID is in the admin list"""
        return user_id in self.admin_ids

    async def check_disabled_channels(self, ctx):
        """Check if commands are disabled in the current channel"""
        # Block all DM commands
        if not ctx.guild:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | DMs Disabled",
                description="Commands are disabled in direct messages. Please use the bot in a server.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)
            return False

        # Skip check for admin commands and this cog's commands
        if ctx.command.cog_name in ['AdminCommands', 'ChannelManagementCog']:
            return True

        # Get server data
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)

        if not server_data:
            return True

        # Check if current channel is in disabled channels list
        disabled_channels = server_data.get("disabled_channels", [])
        if ctx.channel.id in disabled_channels:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Commands Disabled",
                description=f"Commands are disabled in {ctx.channel.mention}.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed, delete_after=10)
            return False

        return True

    @commands.command(name="disablechannel", aliases=["dc"])
    async def disable_channel(self, ctx, channel: discord.TextChannel = None):
        """Disable commands in a specific channel (Bot Admin only)

        Usage: !disablechannel #channel
               !disablechannel (disables current channel)
        """
        # Check if command user is a bot admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to bot administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Use current channel if none specified
        if channel is None:
            channel = ctx.channel
        elif isinstance(channel, str) and channel.isdigit():
            # If channel is a string of digits, try to get channel by ID
            channel_id = int(channel)
            channel = ctx.guild.get_channel(channel_id)
            if channel is None:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Channel Not Found",
                    description=f"No channel found with ID `{channel_id}` in this server.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        elif not isinstance(channel, discord.TextChannel):
            # If channel is not a TextChannel object, try to convert it
            try:
                if hasattr(channel, 'id'):
                    channel_obj = ctx.guild.get_channel(channel.id)
                else:
                    channel_obj = ctx.guild.get_channel(int(str(channel)))

                if channel_obj is None:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Channel",
                        description="Please provide a valid channel mention or channel ID.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
                channel = channel_obj
            except (ValueError, AttributeError):
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Channel",
                    description="Please provide a valid channel mention or channel ID.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        # Get server data
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)

        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact the developer.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Get current disabled channels list
        disabled_channels = server_data.get("disabled_channels", [])

        # Check if channel is already disabled
        if channel.id in disabled_channels:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Already Disabled",
                description=f"Commands are already disabled in {channel.mention}.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Add channel to disabled list
        disabled_channels.append(channel.id)

        # Update database
        db.collection.update_one(
            {"server_id": ctx.guild.id},
            {"$set": {"disabled_channels": disabled_channels}}
        )

        # Send confirmation
        embed = discord.Embed(
            title="<:checkmark:1344252974188335206> | Channel Disabled",
            description=f"Commands have been disabled in {channel.mention}.",
            color=0x00FFAE
        )
        embed.add_field(
            name="Note",
            value="Admin commands and channel management commands will still work.",
            inline=False
        )
        embed.set_footer(text=f"Admin: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.reply(embed=embed)

    @commands.command(name="enablechannel", aliases=["ec"])
    async def enable_channel(self, ctx, channel: discord.TextChannel = None):
        """Enable commands in a specific channel (Bot Admin only)

        Usage: !enablechannel #channel
               !enablechannel (enables current channel)
        """
        # Check if command user is a bot admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to bot administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Use current channel if none specified
        if channel is None:
            channel = ctx.channel
        elif isinstance(channel, str) and channel.isdigit():
            # If channel is a string of digits, try to get channel by ID
            channel_id = int(channel)
            channel = ctx.guild.get_channel(channel_id)
            if channel is None:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Channel Not Found",
                    description=f"No channel found with ID `{channel_id}` in this server.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        elif not isinstance(channel, discord.TextChannel):
            # If channel is not a TextChannel object, try to convert it
            try:
                if hasattr(channel, 'id'):
                    channel_obj = ctx.guild.get_channel(channel.id)
                else:
                    channel_obj = ctx.guild.get_channel(int(str(channel)))

                if channel_obj is None:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Channel",
                        description="Please provide a valid channel mention or channel ID.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
                channel = channel_obj
            except (ValueError, AttributeError):
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Channel",
                    description="Please provide a valid channel mention or channel ID.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        # Get server data
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)

        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact the developer.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Get current disabled channels list
        disabled_channels = server_data.get("disabled_channels", [])

        # Check if channel is not disabled
        if channel.id not in disabled_channels:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Already Enabled",
                description=f"Commands are already enabled in {channel.mention}.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Remove channel from disabled list
        disabled_channels.remove(channel.id)

        # Update database
        db.collection.update_one(
            {"server_id": ctx.guild.id},
            {"$set": {"disabled_channels": disabled_channels}}
        )

        # Send confirmation
        embed = discord.Embed(
            title="<:checkmark:1344252974188335206> | Channel Enabled",
            description=f"Commands have been enabled in {channel.mention}.",
            color=0x00FFAE
        )
        embed.set_footer(text=f"Admin: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.reply(embed=embed)

    @commands.command(name="listdisabledchannels", aliases=["ldc"])
    async def list_disabled_channels(self, ctx):
        """List all disabled channels in the server (Bot Admin only)

        Usage: !listdisabledchannels
        """
        # Check if command user is a bot admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to bot administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Get server data
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)

        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact the developer.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Get disabled channels
        disabled_channels = server_data.get("disabled_channels", [])

        # Create embed
        embed = discord.Embed(
            title="🚫 Disabled Channels",
            description=f"Channels where commands are disabled in {ctx.guild.name}",
            color=0x00FFAE
        )

        if not disabled_channels:
            embed.add_field(
                name="No Disabled Channels",
                value="All channels allow commands.",
                inline=False
            )
        else:
            channel_list = []
            for channel_id in disabled_channels:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    channel_list.append(f"{channel.mention} (`{channel.id}`)")
                else:
                    channel_list.append(f"Unknown Channel (`{channel_id}`)")

            embed.add_field(
                name=f"Disabled Channels ({len(disabled_channels)})",
                value="\n".join(channel_list),
                inline=False
            )

        embed.add_field(
            name="Commands",
            value="• `!disablechannel #channel` - Disable commands in a channel\n• `!enablechannel #channel` - Enable commands in a channel",
            inline=False
        )

        embed.set_footer(text=f"Requested by: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.reply(embed=embed)

    @commands.command(name="channelstatus", aliases=["cs"])
    async def channel_status(self, ctx, channel: discord.TextChannel = None):
        """Check if commands are enabled or disabled in a channel (Bot Admin only)

        Usage: !channelstatus #channel
               !channelstatus (checks current channel)
        """
        # Check if command user is a bot admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to bot administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Use current channel if none specified
        if channel is None:
            channel = ctx.channel
        elif isinstance(channel, str) and channel.isdigit():
            # If channel is a string of digits, try to get channel by ID
            channel_id = int(channel)
            channel = ctx.guild.get_channel(channel_id)
            if channel is None:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Channel Not Found",
                    description=f"No channel found with ID `{channel_id}` in this server.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        elif not isinstance(channel, discord.TextChannel):
            # If channel is not a TextChannel object, try to convert it
            try:
                if hasattr(channel, 'id'):
                    channel_obj = ctx.guild.get_channel(channel.id)
                else:
                    channel_obj = ctx.guild.get_channel(int(str(channel)))

                if channel_obj is None:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Channel",
                        description="Please provide a valid channel mention or channel ID.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
                channel = channel_obj
            except (ValueError, AttributeError):
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Channel",
                    description="Please provide a valid channel mention or channel ID.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        # Get server data
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)

        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact the developer.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check channel status
        disabled_channels = server_data.get("disabled_channels", [])
        is_disabled = channel.id in disabled_channels

        # Create status embed
        status_emoji = "🚫" if is_disabled else "✅"
        status_text = "Disabled" if is_disabled else "Enabled"
        status_color = 0xFF0000 if is_disabled else 0x00FFAE

        embed = discord.Embed(
            title=f"{status_emoji} Channel Status",
            description=f"Commands are **{status_text.lower()}** in {channel.mention}.",
            color=status_color
        )

        embed.add_field(
            name="Channel Info",
            value=f"**Name:** {channel.name}\n**ID:** `{channel.id}`\n**Status:** {status_text}",
            inline=False
        )

        if is_disabled:
            embed.add_field(
                name="Enable Commands",
                value=f"Use `!enablechannel {channel.mention}` to enable commands.",
                inline=False
            )
        else:
            embed.add_field(
                name="Disable Commands",
                value=f"Use `!disablechannel {channel.mention}` to disable commands.",
                inline=False
            )

        embed.set_footer(text=f"Requested by: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(ChannelManagementCog(bot))