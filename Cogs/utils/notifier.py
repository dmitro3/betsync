
import discord
from discord_webhook import DiscordWebhook, DiscordEmbed
#from Cogs.utils.mongo import Users
import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables

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
        from Cogs.utils.mongo import Users
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

    async def server_profit_update(self, server_id, server_name, profit_loss_amount, new_wallet_balance, currency):
        """
        Send a server profit update notification to a webhook

        Parameters:
        - server_id: Discord server ID
        - server_name: Name of the server
        - profit_loss_amount: The amount of profit or loss (+/-)
        - new_wallet_balance: The new wallet balance for the specific currency
        - currency: The currency type (e.g., 'BTC', 'ETH')
        """
        webhook_url = os.environ.get("PROFIT_WEBHOOK_URL")
        if not webhook_url:
            print("Error: PROFIT_WEBHOOK_URL environment variable not set.")
            return False

        try:
            # Create webhook
            webhook = DiscordWebhook(url=webhook_url, rate_limit_retry=True)

            # Determine color and title based on profit/loss
            if profit_loss_amount >= 0:
                color = 0x00FF00  # Green for profit
                title = "📈 Server Profit Update"
                change_indicator = "+"
            else:
                color = 0xFF0000  # Red for loss
                title = "📉 Server Loss Update"
                change_indicator = "" # Amount already includes negative sign

            # Create embed
            embed = DiscordEmbed(
                title=title,
                description=f"Profit/Loss recorded for server: **{server_name}**",
                color=color
            )

            # Server details field
            embed.add_embed_field(
                name="🏢 Server Details",
                value=(
                    f"**Name:** {server_name}\n"
                    f"**ID:** `{server_id}`"
                ),
                inline=False
            )

            # Profit/Loss and Wallet details field
            embed.add_embed_field(
                name="📊 Update Details",
                value=(
                    f"**Change:** {change_indicator}{profit_loss_amount:.8f} {currency}\n"
                    f"**New {currency} Balance:** {new_wallet_balance:.8f} {currency}"
                ),
                inline=False
            )

            embed.set_footer(text="BetSync Casino Server Profit Notification")

            # Add embed to webhook
            webhook.add_embed(embed)

            # Send webhook (async)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, webhook.execute)
            return True

        except Exception as e:
            print(f"Error sending server profit webhook notification: {e}")
            return False
