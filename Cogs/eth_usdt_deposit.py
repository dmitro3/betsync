# Cogs/eth_usdt_deposit.py

import discord
from discord.ext import commands, tasks
import os
import requests
import qrcode
import io
import asyncio
import datetime
import time
import aiohttp
import json
import re
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from colorama import Fore, Style

from Cogs.utils.mongo import Users
from Cogs.utils.notifier import Notifier
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import get_crypto_price

# Load environment variables
load_dotenv()

METAMASK_SEED = os.environ.get("METAMASK_SEED")
DEPOSIT_WEBHOOK_URL = os.environ.get("DEPOSIT_WEBHOOK")
MONGO_URI = os.environ.get("MONGO")

# Constants
ETH_CONVERSION_RATE = 0.000010  # 1 point = 0.000010 ETH
USDT_CONVERSION_RATE = 0.0212  # 1 point = 0.0212 USDT
REQUIRED_CONFIRMATIONS = 12  # Ethereum typically needs more confirmations
CHECK_DEPOSIT_COOLDOWN = 15  # seconds
EMBED_TIMEOUT = 600  # 10 minutes in seconds
INFURA_URL = "https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID"  # Replace with actual Infura ID
USDT_CONTRACT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"  # Mainnet USDT

from PIL import Image, ImageDraw, ImageFont

def generate_qr_code(address: str, username: str, currency: str):
    """Generates a styled QR code image with text for ETH/USDT."""
    qr_data = f"ethereum:{address}" if currency == "eth" else f"ethereum:{address}?contractAddress={USDT_CONTRACT_ADDRESS}&decimal=6"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_width, qr_height = qr_img.size

    try:
        title_font = ImageFont.truetype("Helvetica-Bold.ttf", 30)
        subtitle_font = ImageFont.truetype("Helvetica.ttf", 18)
        brand_font = ImageFont.truetype("Helvetica-Bold.ttf", 36)
    except IOError:
        print(f"{Fore.YELLOW}[!] Warning: Font files not found. Using default font.{Style.RESET_ALL}")
        try:
            title_font = ImageFont.truetype("arial.ttf", 30)
            subtitle_font = ImageFont.truetype("arial.ttf", 18)
            brand_font = ImageFont.truetype("arial.ttf", 36)
        except IOError:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            brand_font = ImageFont.load_default()

    title_text = f"{username}'s Deposit Address"
    instruction_text = f"Only send {currency.upper()}" 
    brand_text = "BETSYNC"

    padding = 20
    title_bbox = title_font.getbbox(title_text)
    instruction_bbox = subtitle_font.getbbox(instruction_text)
    brand_bbox = brand_font.getbbox(brand_text)

    title_width = title_bbox[2] - title_bbox[0]
    title_height = title_bbox[3] - title_bbox[1]
    instruction_width = instruction_bbox[2] - instruction_bbox[0]
    instruction_height = instruction_bbox[3] - instruction_bbox[1]
    brand_width = brand_bbox[2] - brand_bbox[0]
    brand_height = brand_bbox[3] - brand_bbox[1]

    total_height = padding + title_height + padding // 2 + qr_height + padding // 2 + instruction_height + padding // 2 + brand_height + padding
    max_width = max(qr_width, title_width, instruction_width, brand_width)
    image_width = max_width + 2 * padding

    final_img = Image.new('RGB', (image_width, total_height), color='white')
    draw = ImageDraw.Draw(final_img)

    title_x = (image_width - title_width) // 2
    title_y = padding
    draw.text((title_x, title_y), title_text, font=title_font, fill="black")

    qr_x = (image_width - qr_width) // 2
    qr_y = title_y + title_height + padding // 2
    final_img.paste(qr_img, (qr_x, qr_y))

    instruction_x = (image_width - instruction_width) // 2
    instruction_y = qr_y + qr_height + padding // 2
    draw.text((instruction_x, instruction_y), instruction_text, font=subtitle_font, fill="black")

    brand_x = (image_width - brand_width) // 2
    brand_y = instruction_y + instruction_height + padding // 2
    draw.text((brand_x, brand_y), brand_text, font=brand_font, fill="black")

    buffer = io.BytesIO()
    final_img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

class DepositView(discord.ui.View):
    def __init__(self, cog_instance, user_id: int, address: str, currency: str):
        super().__init__(timeout=EMBED_TIMEOUT)
        self.cog = cog_instance
        self.user_id = user_id
        self.address = address
        self.currency = currency
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your deposit interface!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True

                timeout_embed = discord.Embed(
                    title="<:no:1344252518305234987> | Embed Timeout",
                    description=f"Your deposit session for address `{self.address}` has timed out.\n\n"
                                f"Please run `!dep {self.currency}` again if you need to check for deposits or start a new one.",
                    color=discord.Color.red()
                )
                timeout_embed.set_footer(text="BetSync Casino")
                await self.message.edit(embed=timeout_embed, view=None, attachments=[])
            except discord.NotFound:
                print(f"{Fore.YELLOW}[!] Warning: Failed to edit timed-out deposit message for user {self.user_id} (message not found).{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[!] Error editing timed-out deposit message for user {self.user_id}: {e}{Style.RESET_ALL}")
        
        if self.user_id in self.cog.active_deposit_views:
            try:
                del self.cog.active_deposit_views[self.user_id]
            except KeyError:
                pass

    @discord.ui.button(label="Check for New Deposits", style=discord.ButtonStyle.green, custom_id="check_deposit_button", emoji="🔄")
    async def check_deposit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        now = time.time()
        cooldown_key = f"{self.user_id}_check_deposit"
        last_check_time = self.cog.button_cooldowns.get(cooldown_key, 0)

        if now - last_check_time < CHECK_DEPOSIT_COOLDOWN:
            remaining = CHECK_DEPOSIT_COOLDOWN - (now - last_check_time)
            await interaction.response.send_message(f"Please wait {remaining:.1f} more seconds before checking again.", ephemeral=True)
            return

        self.cog.button_cooldowns[cooldown_key] = now
        await interaction.response.defer(ephemeral=True)

        try:
            status, details = await self.cog._check_for_deposits(self.user_id, self.address, self.currency)

            if status == "success":
                deposits = details.get('deposits', [details])
                total_amount = sum(d['amount_crypto'] for d in deposits)
                total_points = sum(d.get('points_credited', 0) for d in deposits)
                
                if total_points > 0:
                    update_result = self.cog.users_db.update_balance(self.user_id, total_points, operation="$inc")
                    if not update_result or update_result.matched_count == 0:
                        print(f"{Fore.RED}[!] Failed to update balance for user {self.user_id} after successful deposit check.{Style.RESET_ALL}")
                        await interaction.followup.send("Deposit detected, but failed to update your balance. Please contact support.", ephemeral=True)
                        return

                    for deposit in deposits:
                        crypto_price = await get_crypto_price(self.currency)
                        usd_value = deposit['amount_crypto'] * crypto_price if crypto_price else None
                        
                        history_entry = {
                            "type": f"{self.currency}_deposit",
                            "amount_crypto": deposit['amount_crypto'],
                            "currency": self.currency.upper(),
                            "usd_value": usd_value,
                            "txid": deposit['txid'],
                            "address": self.address,
                            "confirmations": deposit.get('confirmations', REQUIRED_CONFIRMATIONS),
                            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                        }
                        self.cog.users_db.update_history(self.user_id, history_entry)
                        
                        if usd_value:
                            self.cog.users_db.collection.update_one(
                                {"discord_id": self.user_id},
                                {"$inc": {"total_deposit_amount_usd": usd_value}}
                            )

                if not self.message:
                    await interaction.followup.send("Error: Could not find the original deposit message to update.", ephemeral=True)
                    return

                main_embed = self.message.embeds[0]
                main_embed.title = "<:yes:1355501647538815106> | Deposit Success"
                main_embed.description = f"<:{self.currency}:1339343445675868191> **+{total_amount:,.8f} {self.currency.upper()}** from {len(deposits)} transaction(s)"
                main_embed.clear_fields()
                main_embed.set_image(url=None)

                for i, deposit in enumerate(deposits, 1):
                    txid = deposit['txid']
                    txid_short = txid[:10] + '...' if len(txid) > 10 else txid
                    explorer_url = f"https://etherscan.io/tx/{txid}"
                    tx_value = f"[`{txid_short}`]({explorer_url})" if txid != 'N/A' else "N/A"
                    
                    main_embed.add_field(
                        name=f"Transaction #{i}",
                        value=f"Amount: {deposit['amount_crypto']:,.8f} {self.currency.upper()}\nTXID: {tx_value}",
                        inline=False
                    )

                updated_user = self.cog.users_db.fetch_user(self.user_id)
                balance = updated_user.get("wallet", {}).get(self.currency.upper(), "N/A") if updated_user else "N/A"
                main_embed.add_field(name=f"New {self.currency.upper()} Balance", value=f"<:{self.currency}:1339343445675868191> {balance:,.8f} {self.currency.upper()}", inline=True)
                
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.custom_id == "check_deposit_button":
                        item.disabled = True
                        item.style = discord.ButtonStyle.grey
                        item.label = "Checked"

                await self.message.edit(embed=main_embed, view=self, attachments=[])

            elif status == "pending":
                pending_amount = details.get('amount_crypto', 0)
                embed = discord.Embed(
                    title="⏳ Deposit Pending Confirmation",
                    description=(
                        f"**Address:** `{self.address}`\n"
                        f"**Amount:** {pending_amount:.8f} {self.currency.upper()}\n"
                        f"**Confirmations:** {details['confirmations']}/{REQUIRED_CONFIRMATIONS}\n\n"
                        f"Please wait and check again when fully confirmed."
                    ),
                    color=discord.Color.orange()
                )
                embed.set_footer(text="BetSync Casino | Pending Deposit")
                await interaction.followup.send(embed=embed, ephemeral=True)

            elif status == "no_new":
                embed = discord.Embed(
                    title="🔍 No New Deposits",
                    description=(
                        f"**Address:** `{self.address}`\n\n"
                        f"No new confirmed deposits found.\n\n"
                        f"Please ensure you sent {self.currency.upper()} to the correct address."
                    ),
                    color=discord.Color.blue()
                )
                embed.set_footer(text="BetSync Casino")
                await interaction.followup.send(embed=embed, ephemeral=True)

            elif status == "error":
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Deposit Check Error",
                    description=(
                        f"**Address:** `{self.address}`\n\n"
                        f"Error checking deposits:\n"
                        f"`{details['error']}`"
                    ),
                    color=discord.Color.red()
                )
                embed.set_footer(text="BetSync Casino")
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"{Fore.RED}[!] Error in check_deposit_button interaction for user {self.user_id}: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.followup.send("An unexpected error occurred. Please try again later.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @discord.ui.button(label="History", style=discord.ButtonStyle.grey, custom_id="deposit_history_button", emoji="📜")
    async def deposit_history_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        history_embed = await self.cog._show_deposit_history(self.user_id, self.currency)
        await interaction.followup.send(embed=history_embed, ephemeral=True)

class EthUsdtDeposit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users_db = Users()
        self.notifier = Notifier()
        self.active_deposit_views = {}
        self.button_cooldowns = {}

        if not METAMASK_SEED:
            print(f"{Fore.RED}[!] ERROR: METAMASK_SEED not found in environment variables! ETH/USDT deposits will not work.{Style.RESET_ALL}")
        if not DEPOSIT_WEBHOOK_URL:
            print(f"{Fore.YELLOW}[!] WARNING: DEPOSIT_WEBHOOK_URL not found. Deposit notifications will not be sent.{Style.RESET_ALL}")

        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(INFURA_URL))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        Account.enable_unaudited_hdwallet_features()

    async def _generate_eth_address(self, user_id: int, currency: str) -> tuple[str | None, str | None]:
        """Generates or retrieves a unique ETH/USDT deposit address for the user."""
        user_data = self.users_db.fetch_user(user_id)

        # Check if address already exists
        address_key = f"{currency}_address"
        if user_data and user_data.get(address_key):
            return user_data[address_key], None

        if not METAMASK_SEED:
            return None, "METAMASK_SEED environment variable is not configured."

        try:
            # Find the highest index used for this currency
            highest_index_user = self.users_db.collection.find_one(
                {f"{currency}_address_index": {"$exists": True}},
                sort=[(f"{currency}_address_index", -1)]
            )

            last_global_index = -1
            if highest_index_user and f"{currency}_address_index" in highest_index_user:
                last_global_index = highest_index_user[f"{currency}_address_index"]

            next_index = last_global_index + 1

            # Derive address from seed phrase
            account = Account.from_mnemonic(
                METAMASK_SEED,
                account_path=f"m/44'/60'/0'/0/{next_index}"
            )
            address = account.address

            # Store the new address and index
            update_data = {
                "$set": {
                    address_key: address,
                    f"{currency}_address_index": next_index
                }
            }

            if not user_data:
                result = self.users_db.collection.update_one({"discord_id": user_id}, update_data)
                if result.matched_count == 0:
                    print(f"{Fore.RED}[!] Failed to store address for user {user_id} - user document not found.{Style.RESET_ALL}")
                    return None, "User document not found to store address."
            else:
                self.users_db.collection.update_one({"discord_id": user_id}, update_data)

            print(f"{Fore.GREEN}[+] Generated {currency.upper()} address {address} (Index: {next_index}) for user {user_id}{Style.RESET_ALL}")
            return address, None

        except Exception as e:
            print(f"{Fore.RED}[!] Error generating {currency.upper()} address for user {user_id}: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            return None, f"Failed to generate address: {e}"

    async def _check_for_deposits(self, user_id: int, address: str, currency: str) -> tuple[str, dict]:
        """Checks Etherscan API for confirmed deposits to the address."""
        try:
            user_data = self.users_db.fetch_user(user_id)
            if not user_data:
                print(f"{Fore.RED}[!] User data not found for user {user_id} at start of deposit check.{Style.RESET_ALL}")
                return "error", {"error": "User data not found."}

            # For ETH, check normal transactions
            # For USDT, check token transfers
            ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY")
            if currency == "eth":
                api_url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={ETHERSCAN_API_KEY}"
            else:
                api_url = f"https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={USDT_CONTRACT_ADDRESS}&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={ETHERSCAN_API_KEY}"

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url) as response:
                        if response.status != 200:
                            print(f"{Fore.RED}[!] Etherscan API Error ({response.status}) fetching transactions for {address}.{Style.RESET_ALL}")
                            return "error", {"error": "Failed to check deposits. Please try again later."}

                        data = await response.json()
                        if data.get('status') != '1':
                            error_msg = data.get('message', 'Etherscan API error')
                            if "No transactions found" in error_msg:
                                return "no_new", {}
                            print(f"{Fore.RED}[!] Etherscan API returned error: {error_msg}{Style.RESET_ALL}")
                            return "error", {"error": "Failed to check deposits. Please try again later."}

                        transactions = data.get('result', [])
            except Exception as e:
                print(f"{Fore.RED}[!] Error during API check for {address}: {e}{Style.RESET_ALL}")
                return "error", {"error": f"API request failed: {e}"}

            if not transactions:
                return "no_new", {}

            history = user_data.get('history', [])
            processed_txids = {entry.get('txid') for entry in history if entry and entry.get('type') == f'{currency}_deposit'}

            new_deposits = []
            first_pending_tx = None
            current_block = self.w3.eth.block_number

            for tx in transactions:
                txid = tx.get('hash')
                if not txid or txid in processed_txids:
                    continue

                # For ETH: value is in wei
                # For USDT: value is in the token decimals (6 for USDT)
                if currency == "eth":
                    amount = int(tx.get('value', 0)) / 1e18  # Convert from wei to ETH
                else:
                    amount = int(tx.get('value', 0)) / 1e6  # Convert to USDT (6 decimals)

                if amount <= 0:
                    continue

                confirmations = 0
                if tx.get('blockNumber'):
                    confirmations = current_block - int(tx['blockNumber']) + 1

                if confirmations < REQUIRED_CONFIRMATIONS:
                    if not first_pending_tx or confirmations > first_pending_tx['confirmations']:
                        first_pending_tx = {
                            "confirmations": confirmations,
                            "txid": txid,
                            "amount_crypto": amount
                        }
                    continue

                # If we get here, we have a confirmed deposit
                new_deposits.append({
                    "amount_crypto": amount,
                    "txid": txid,
                    "confirmations": confirmations
                })

            if new_deposits:
                return "success", {
                    "deposits": new_deposits,
                    "points_credited": sum(deposit['amount_crypto'] / (ETH_CONVERSION_RATE if currency == 'eth' else USDT_CONVERSION_RATE) for deposit in new_deposits)
                }
            elif first_pending_tx:
                return "pending", first_pending_tx
            else:
                return "no_new", {}

        except Exception as e:
            print(f"{Fore.RED}[!] Error in _check_for_deposits for user {user_id}: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            return "error", {"error": str(e)}

    async def _show_deposit_history(self, user_id: int, currency: str) -> discord.Embed:
        """Shows deposit history for the user."""
        user_data = self.users_db.fetch_user(user_id)
        if not user_data:
            return discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description="User data not found.",
                color=discord.Color.red()
            )

        history = user_data.get('history', [])
        if not isinstance(history, list):
            history = []

        deposit_history = [entry for entry in history if entry and entry.get('type') == f'{currency}_deposit']
        deposit_history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        embed = discord.Embed(
            title=f"<:{currency}:1339343445675868191> {currency.upper()} Deposit History",
            color=0x00FFAE
        )

        if not deposit_history:
            embed.description = "No deposit history found."
            return embed

        for deposit in deposit_history[:10]:  # Show last 10 deposits
            txid = deposit.get('txid', 'N/A')
            txid_short = txid[:10] + '...' if len(txid) > 10 else txid
            explorer_url = f"https://etherscan.io/tx/{txid}"
            tx_value = f"[`{txid_short}`]({explorer_url})" if txid != 'N/A' else "N/A"
            
            embed.add_field(
                name=f"{deposit.get('timestamp', 'Unknown date')}",
                value=(
                    f"Amount: {deposit.get('amount_crypto', 0):,.8f} {currency.upper()}\n"
                    f"TXID: {tx_value}\n"
                    f"Status: Confirmed ({deposit.get('confirmations', 0)} confirmations)"
                ),
                inline=False
            )

        embed.set_footer(text="BetSync Casino")
        return embed

    @commands.command(name="deposit_eth", aliases=["ethdep", "ethdeposit"])
    async def deposit_eth(self, ctx, currency: str = None):
        """Handle ETH deposit command"""
        await self._handle_deposit(ctx, "eth")

    @commands.command(name="deposit_usdt", aliases=["usdtdep", "usdtdeposit"])
    async def deposit_usdt(self, ctx, currency: str = None):
        """Handle USDT deposit command"""
        await self._handle_deposit(ctx, "usdt")

    async def _handle_deposit(self, ctx, currency: str):
        """Common handler for ETH and USDT deposits"""
        user_id = ctx.author.id

        # Generate or get address
        address, error = await self._generate_eth_address(user_id, currency)
        if error:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Deposit Error",
                description=f"Failed to generate deposit address:\n`{error}`",
                color=discord.Color.red()
            )
            embed.set_footer(text="BetSync Casino")
            return await ctx.reply(embed=embed)

        # Generate QR code
        try:
            qr_buffer = await asyncio.to_thread(generate_qr_code, address, ctx.author.name, currency)
        except Exception as e:
            print(f"{Fore.RED}[!] Error generating QR code for user {user_id}: {e}{Style.RESET_ALL}")
            qr_buffer = None

        # Create deposit embed
        # Format conversion rate to avoid scientific notation for ETH
        conversion_rate = ETH_CONVERSION_RATE if currency == 'eth' else USDT_CONVERSION_RATE
        if currency == 'eth':
            conversion_rate = "{0:.8f}".format(conversion_rate).rstrip('0').rstrip('.') if '.' in "{0:.8f}".format(conversion_rate) else "{0:.8f}".format(conversion_rate)
        
        # Create message content with plain address
        message_content = f"Your {currency.upper()} deposit address: {address}\n\n"
        
        embed = discord.Embed(
            title=f"<:{currency}:1339343445675868191> | {currency.upper()} Deposit",
            description=(
                f"**Address:** ```{address}```\n\n"
                f"Send **{currency.upper()}** to this address to receive points.\n\n"
                f"**Conversion Rate:**\n"
                f"1 point = {conversion_rate} {currency.upper()}"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino")

        if qr_buffer:
            embed.set_image(url="attachment://qr.png")

        # Create view and send message
        view = DepositView(self, user_id, address, currency)
        if qr_buffer:
            message = await ctx.reply(content=message_content, embed=embed, file=discord.File(qr_buffer, filename="qr.png"), view=view)
        else:
            message = await ctx.reply(content=message_content, embed=embed, view=view)

        view.message = message
        self.active_deposit_views[user_id] = view

def setup(bot):
    bot.add_cog(EthUsdtDeposit(bot))