
import discord
import aiohttp
import asyncio
from discord.ext import commands

class Notifier:
    """
    Utility class for sending notifications via Discord webhooks
    """
    
    @staticmethod
    async def bet_event(webhook_url, user_id, user_name, user_mention, bet_amount, current_balance, primary_currency="points"):
        """
        Send a bet event notification to a webhook
        
        Parameters:
        - webhook_url: Discord webhook URL
        - user_id: Discord user ID
        - user_name: Discord username
        - user_mention: Discord user mention
        - bet_amount: Amount bet in the transaction
        - current_balance: User's current balance after bet
        - primary_currency: Currency type used (default: points)
        """
        if not webhook_url:
            return False
            
        try:
            embed = discord.Embed(
                title="🎮 New Bet Placed",
                description=f"A user has placed a new bet in BetSync Casino",
                color=0x00FFAE
            )
            
            # User details field
            embed.add_field(
                name="👤 User Details",
                value=(
                    f"**User:** {user_mention} ({user_name})\n"
                    f"**ID:** `{user_id}`"
                ),
                inline=False
            )
            
            # Bet and wallet details field
            embed.add_field(
                name="💰 Transaction Details",
                value=(
                    f"**Bet Amount:** {bet_amount:.2f} {primary_currency}\n"
                    f"**Current Balance:** {current_balance:.2f} {primary_currency}"
                ),
                inline=False
            )
            
            embed.set_footer(text="BetSync Casino Notification System")
            
            # Prepare webhook payload
            payload = {
                "embeds": [embed.to_dict()]
            }
            
            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    return response.status == 204
                    
        except Exception as e:
            print(f"Error sending webhook notification: {e}")
            return False
