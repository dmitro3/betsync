import discord
from discord.ext import commands
import asyncio
from Cogs.utils.mongo import Users

class PrivateThreads(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_threads = {}  # Store user_id: thread_id mapping

    @commands.command(aliases=["pt", "privatethread"])
    async def create_private_thread(self, ctx):
        """Create a private thread for using commands privately"""
        # Check if user already has a private thread
        if ctx.author.id in self.user_threads:
            thread_id = self.user_threads[ctx.author.id]
            thread = ctx.guild.get_thread(thread_id)
            if thread and not thread.archived:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Thread Already Exists",
                    description=f"You already have an active private thread: {thread.mention}",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
            else:
                # Thread was archived or deleted, remove from tracking
                del self.user_threads[ctx.author.id]

        # Create the private thread
        try:
            thread = await ctx.channel.create_thread(
                name=f"Private Thread - {ctx.author.display_name}",
                type=discord.ChannelType.private_thread,
                reason=f"Private thread created by {ctx.author}"
            )

            # Track the thread
            self.user_threads[ctx.author.id] = thread.id

            # Create control panel embed
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Private Thread Created",
                description=f"Your private thread has been created: {thread.mention}",
                color=0x00FFAE
            )
            embed.add_field(
                name="🎫 Thread Controls",
                value="Use the buttons below to manage your thread",
                inline=False
            )
            embed.set_footer(text="BetSync • Private Thread System", icon_url=self.bot.user.avatar.url)

            # Send confirmation in original channel
            await ctx.reply(embed=embed)

            # Send welcome message in thread with controls
            welcome_embed = discord.Embed(
                title=":information_source: | Welcome to Your Private Thread",
                description=f"Hello {ctx.author.mention}! This is your private thread where you can use commands privately.",
                color=0x00FFAE
            )
            welcome_embed.add_field(
                name="📋 Available Actions",
                value="• Close this thread\n• Add members to thread\n• Remove members from thread\n• View thread info",
                inline=False
            )
            welcome_embed.add_field(
                name="🔒 Privacy",
                value="Only you and added members can see this thread.",
                inline=False
            )

            view = ThreadControlView(self, ctx.author.id)
            await thread.send(embed=welcome_embed, view=view)

        except discord.Forbidden:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Permission Error",
                description="I don't have permission to create private threads in this channel.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to create private thread: {str(e)}",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)

    @commands.command(aliases=["ct", "closethread"])
    async def close_thread(self, ctx):
        """Close your private thread"""
        if not isinstance(ctx.channel, discord.Thread):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Not a Thread",
                description="This command can only be used in threads.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check if user owns this thread
        if ctx.author.id not in self.user_threads or self.user_threads[ctx.author.id] != ctx.channel.id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="You can only close your own private thread.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Close the thread
        embed = discord.Embed(
            title="<:yes:1355501647538815106> | Thread Closing",
            description="This private thread will be closed in 5 seconds...",
            color=0x00FFAE
        )
        await ctx.reply(embed=embed)

        await asyncio.sleep(5)

        # Remove from tracking
        del self.user_threads[ctx.author.id]

        # Archive the thread
        await ctx.channel.edit(archived=True, reason=f"Thread closed by {ctx.author}")

class ThreadControlView(discord.ui.View):
    def __init__(self, cog, owner_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.owner_id = owner_id

    @discord.ui.button(label="Close Thread", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="Only the thread owner can close this thread.",
                color=0xFF0000
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title="<:yes:1355501647538815106> | Thread Closing",
            description="This private thread will be closed in 5 seconds...",
            color=0x00FFAE
        )
        await interaction.response.send_message(embed=embed)

        await asyncio.sleep(5)

        # Remove from tracking
        if self.owner_id in self.cog.user_threads:
            del self.cog.user_threads[self.owner_id]

        # Archive the thread
        await interaction.followup.channel.edit(archived=True, reason=f"Thread closed by {interaction.user}")

    @discord.ui.button(label="Add Member", style=discord.ButtonStyle.secondary, emoji="➕")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="Only the thread owner can add members.",
                color=0xFF0000
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        member = await self.get_member_input(interaction, "Add")
        if not member:
            return

        if member.bot:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Member",
                description="You cannot add bots to private threads.",
                color=0xFF0000
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            await interaction.channel.add_user(member)
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Member Added",
                description=f"{member.mention} has been added to this thread.",
                color=0x00FFAE
            )
            await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Permission Error",
                description="I don't have permission to add members to this thread.",
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
                description="Only the thread owner can remove members.",
                color=0xFF0000
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        member = await self.get_member_input(interaction, "Remove")
        if not member:
            return

        if member not in interaction.channel.members:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Not in Thread",
                description=f"{member.mention} is not in this thread.",
                color=0xFF0000
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            await interaction.channel.remove_user(member)
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Member Removed",
                description=f"{member.mention} has been removed from this thread.",
                color=0x00FFAE
            )
            await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Permission Error",
                description="I don't have permission to remove members from this thread.",
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

    @discord.ui.button(label="Thread Info", style=discord.ButtonStyle.primary, emoji="ℹ️")
    async def thread_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        thread = interaction.channel
        members = [member for member in thread.members if not member.bot]

        embed = discord.Embed(
            title=":information_source: | Thread Information",
            description=f"Information about {thread.name}",
            color=0x00FFAE
        )
        embed.add_field(
            name="👑 Owner",
            value=f"<@{self.owner_id}>",
            inline=True
        )
        embed.add_field(
            name="👥 Members",
            value=f"{len(members)} members",
            inline=True
        )
        embed.add_field(
            name="📅 Created",
            value=f"<t:{int(thread.created_at.timestamp())}:R>",
            inline=True
        )
        embed.add_field(
            name="🔗 Thread ID",
            value=f"`{thread.id}`",
            inline=False
        )

        if len(members) > 1:
            member_list = "\n".join([f"• {member.display_name}" for member in members[:10]])
            if len(members) > 10:
                member_list += f"\n• ... and {len(members) - 10} more"
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
    bot.add_cog(PrivateThreads(bot))