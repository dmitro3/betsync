
import discord
import aiohttp
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users

class Notifier:
    """
    Utility class for sending notifications via Discord webhooks
    """
    
    @staticmethod
    async def bet_event(webhook_url, user_id, bet_amount):
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
            userd = Users()
            resp = userd.fetch_user(user_id=user_id)
            embed = discord.Embed(
                title="🎮 New Bet Placed",
                description=f"A user has placed a new bet in BetSync Casino",
                color=0x00FFAE
            )
            current_balance = resp["points"]
            primary_currency = resp["primary_coin"]
            coin = resp["wallet"][primary_currency]
            
            # User details field
            embed.add_field(
                name="👤 User Details",
                value=(
                    f"**User:** <@{user_id}>\n"
                    f"**ID:** `{user_id}`"
                ),
                inline=False
            )
            
            # Bet and wallet details field
            
            embed.add_field(
                name="💰 Bet Details",
                value=(
                    f"**Bet Amount:** {int(bet_amount):.2f} points\n"
                    f"**Current Balance:** {int(current_balance):.2f} points ({coin} {primary_currency})"
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
                    print(response)
                    return response.status == 204
                    
                    
        except Exception as e:
            print(f"Error sending webhook notification: {e}")
            return False
