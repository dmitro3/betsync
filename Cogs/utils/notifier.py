
import discord
from discord_webhook import DiscordWebhook, DiscordEmbed
from Cogs.utils.mongo import Users
import aiohttp
import asyncio

class Notifier:
    """
    Utility class for sending notifications via Discord webhooks
    """
    
    #@staticmethod
    async def bet_event(self, webhook_url, user_id, bet_amount):
        """
        Send a bet event notification to a webhook
        
        Parameters:
        - webhook_url: Discord webhook URL
        - user_id: Discord user ID
        - bet_amount: Amount bet in the transaction
        """
        if not webhook_url:
            return False
            
        try:
            userd = Users()
            resp = userd.fetch_user(user_id=user_id)
            current_balance = resp["points"]
            primary_currency = resp["primary_coin"]
            coin = resp["wallet"][primary_currency]
            
            # Create webhook
            webhook = DiscordWebhook(url=webhook_url, rate_limit_retry=True)
            
            # Create embed
            embed = DiscordEmbed(
                title="🎮 New Bet Placed",
                description="A user has placed a new bet in BetSync Casino",
                color=0x00FFAE
            )
            
            # User details field
            embed.add_embed_field(
                name="👤 User Details",
                value=(
                    f"**User:** <@{user_id}>\n"
                    f"**ID:** `{user_id}`"
                ),
                inline=False
            )
            
            # Bet and wallet details field
            embed.add_embed_field(
                name="💰 Bet Details",
                value=(
                    f"**Bet Amount:** {int(bet_amount):.2f} points\n"
                    f"**Current Balance:** {int(current_balance):.2f} points ({coin} {primary_currency})"
                ),
                inline=False
            )
            
            embed.set_footer(text="BetSync Casino Notification System")
            
            # Add embed to webhook
            webhook.add_embed(embed)
            
            # Send webhook (async)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, webhook.execute)
            return True
                    
        except Exception as e:
            print(f"Error sending webhook notification: {e}")
            return False
