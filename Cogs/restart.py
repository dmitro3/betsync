
import discord
import os
import sys
import asyncio
from discord.ext import commands

class RestartCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_ids = self.load_admin_ids()
    
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
    
    @commands.command(name="restartbot", aliases=["restart"])
    async def restart_bot(self, ctx):
        """Restart the bot (Bot Admin only)
        
        Usage: !restartbot
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to bot administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Create confirmation embed
        confirm_embed = discord.Embed(
            title="🔄 | Confirm Bot Restart",
            description="Are you sure you want to restart the bot?",
            color=0xFFA500
        )
        confirm_embed.add_field(
            name="Warning",
            value="This will disconnect the bot from all servers temporarily.",
            inline=False
        )
        confirm_embed.add_field(
            name="Confirmation",
            value="Reply with `yes` within 30 seconds to confirm.",
            inline=False
        )
        confirm_embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        confirm_message = await ctx.reply(embed=confirm_embed)
        
        # Wait for confirmation
        try:
            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel and message.content.lower() == 'yes'
            
            await self.bot.wait_for('message', check=check, timeout=30.0)
            
            # Send restart confirmation
            restart_embed = discord.Embed(
                title="🔄 | Restarting Bot",
                description="Bot is restarting... Please wait a moment.",
                color=0x00FFAE
            )
            restart_embed.set_footer(text=f"Initiated by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            
            await ctx.reply(embed=restart_embed)
            
            # Log the restart
            print(f"[RESTART] Bot restart initiated by {ctx.author.name} ({ctx.author.id})")
            
            # Wait a moment before restarting
            await asyncio.sleep(2)
            
            # Restart the bot
            await self.bot.close()
            os.execv(sys.executable, [sys.executable] + sys.argv)
            
        except asyncio.TimeoutError:
            # User didn't confirm in time
            timeout_embed = discord.Embed(
                title="❌ | Operation Cancelled",
                description="Bot restart operation cancelled due to timeout.",
                color=0xFF0000
            )
            await confirm_message.edit(embed=timeout_embed)
    
    @commands.command(name="shutdown")
    async def shutdown_bot(self, ctx):
        """Shutdown the bot (Bot Admin only)
        
        Usage: !shutdown
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to bot administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Create confirmation embed
        confirm_embed = discord.Embed(
            title="⚠️ | Confirm Bot Shutdown",
            description="Are you sure you want to shutdown the bot?",
            color=0xFF0000
        )
        confirm_embed.add_field(
            name="Warning",
            value="This will completely stop the bot. You'll need to manually restart it.",
            inline=False
        )
        confirm_embed.add_field(
            name="Confirmation",
            value="Reply with `yes` within 30 seconds to confirm.",
            inline=False
        )
        confirm_embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        confirm_message = await ctx.reply(embed=confirm_embed)
        
        # Wait for confirmation
        try:
            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel and message.content.lower() == 'yes'
            
            await self.bot.wait_for('message', check=check, timeout=30.0)
            
            # Send shutdown confirmation
            shutdown_embed = discord.Embed(
                title="🛑 | Shutting Down Bot",
                description="Bot is shutting down... Goodbye!",
                color=0xFF0000
            )
            shutdown_embed.set_footer(text=f"Initiated by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            
            await ctx.reply(embed=shutdown_embed)
            
            # Log the shutdown
            print(f"[SHUTDOWN] Bot shutdown initiated by {ctx.author.name} ({ctx.author.id})")
            
            # Wait a moment before shutting down
            await asyncio.sleep(2)
            
            # Shutdown the bot
            await self.bot.close()
            
        except asyncio.TimeoutError:
            # User didn't confirm in time
            timeout_embed = discord.Embed(
                title="❌ | Operation Cancelled",
                description="Bot shutdown operation cancelled due to timeout.",
                color=0xFF0000
            )
            await confirm_message.edit(embed=timeout_embed)

def setup(bot):
    bot.add_cog(RestartCog(bot))
