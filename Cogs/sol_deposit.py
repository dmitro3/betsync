
# Cogs/sol_deposit.py

import discord
from discord.ext import commands, tasks
import os
import qrcode
import io
import asyncio
import datetime
import time
import aiohttp
import json
from dotenv import load_dotenv
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Finalized
from solana.exceptions import SolanaRpcException
from bip_utils import Bip39SeedGenerator, Bip39MnemonicValidator, Bip44, Bip44Coins, Bip44Changes
from hashlib import sha256
import base58
from colorama import Fore, Style
from PIL import Image, ImageDraw, ImageFont
import traceback

from Cogs.utils.mongo import Users
from Cogs.utils.notifier import Notifier
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import get_crypto_price

# Load environment variables
load_dotenv()

PHANTOM_SEED = os.environ.get("PHANTOM_SEED")
MAINWALLET_SOL = os.environ.get("MAINWALLET_SOL")
ALCHEMY_API = os.environ.get("ALCHEMY_API")
DEPOSIT_WEBHOOK_URL = os.environ.get("DEPOSIT_WEBHOOK")
MONGO_URI = os.environ.get("MONGO")

# Constants
SOL_CONVERSION_RATE = 0.0001442
SOL_LAMPORTS = 1_000_000_000
REQUIRED_COMMITMENT = Finalized
ALCHEMY_API_URL = f"https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API}" if ALCHEMY_API else "https://api.mainnet-beta.solana.com"
RPC_URL = ALCHEMY_API_URL
CHECK_DEPOSIT_COOLDOWN = 15
EMBED_TIMEOUT = 600
SOL_DERIVATION_PATH_ACCOUNT_TEMPLATE = "m/44'/501'/{}'/0'"

def generate_qr_code(address: str, username: str):
    """Generates a styled QR code image with text for Solana."""
    qr_data = address
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
        try:
            title_font = ImageFont.truetype("arial.ttf", 30)
            subtitle_font = ImageFont.truetype("arial.ttf", 18)
            brand_font = ImageFont.truetype("arial.ttf", 36)
        except IOError:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            brand_font = ImageFont.load_default()

    title_text = f"{username}'s SOL Deposit Address"
    instruction_text = "Only send SOLANA (SOL)"
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
    def __init__(self, cog_instance, user_id: int, address: str):
        super().__init__(timeout=EMBED_TIMEOUT)
        self.cog = cog_instance
        self.user_id = user_id
        self.address = address
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
                                f"Please run the deposit command again if you need to check for deposits.",
                    color=discord.Color.red()
                )
                timeout_embed.set_footer(text="BetSync Casino")
                await self.message.edit(embed=timeout_embed, view=None, attachments=[])
            except discord.NotFound:
                pass
            except Exception as e:
                print(f"{Fore.RED}[!] Error editing timed-out deposit message: {e}{Style.RESET_ALL}")
        
        if self.user_id in self.cog.active_deposit_views:
            try:
                del self.cog.active_deposit_views[self.user_id]
            except KeyError:
                pass

    @discord.ui.button(label="Check for New Deposits", style=discord.ButtonStyle.green, custom_id="check_deposit_button", emoji="🔄")
    async def check_deposit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        now = time.time()
        cooldown_key = f"{self.user_id}_check_deposit_sol"
        last_check_time = self.cog.button_cooldowns.get(cooldown_key, 0)

        if now - last_check_time < CHECK_DEPOSIT_COOLDOWN:
            remaining = CHECK_DEPOSIT_COOLDOWN - (now - last_check_time)
            await interaction.response.send_message(f"Please wait {remaining:.1f} more seconds before checking again.", ephemeral=True)
            return

        self.cog.button_cooldowns[cooldown_key] = now
        await interaction.response.defer(ephemeral=True)

        try:
            status, details = await self.cog._check_for_deposits(self.user_id, self.address)

            if status == "success":
                deposits = details.get('deposits', [])
                if not deposits:
                    await interaction.followup.send("Deposit check successful, but no deposit details found.", ephemeral=True)
                    return

                total_sol = sum(d['amount_crypto'] for d in deposits)
                
                updated_user = self.cog.users_db.fetch_user(self.user_id)
                if not updated_user:
                    await interaction.followup.send("Deposit processed, but failed to fetch updated balance.", ephemeral=True)
                    return

                sol_balance = updated_user.get("wallet", {}).get("SOL", 0)

                for deposit in deposits:
                    sol_price = await get_crypto_price('solana')
                    usd_value = deposit['amount_crypto'] * sol_price if sol_price else None

                    await self.cog.notifier.deposit_notification(
                        user_id=self.user_id,
                        username=interaction.user.name,
                        amount_crypto=deposit['amount_crypto'],
                        currency="SOL",
                        usd_value=usd_value,
                        txid=deposit['txid'],
                        address=self.address
                    )

                    history_entry = {
                        "type": "sol_deposit",
                        "amount_crypto": deposit['amount_crypto'],
                        "currency": "SOL",
                        "usd_value": usd_value,
                        "txid": deposit['txid'],
                        "address": self.address,
                        "status": "confirmed",
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
                main_embed.description = f"<:sol:1340981839497793556> **+{total_sol:,.6f} SOL** from {len(deposits)} transaction(s)"
                main_embed.clear_fields()
                main_embed.set_image(url=None)

                for i, deposit in enumerate(deposits, 1):
                    txid = deposit['txid']
                    txid_short = txid[:10] + '...' + txid[-10:] if len(txid) > 20 else txid
                    explorer_url = f"https://solscan.io/tx/{txid}"
                    tx_value = f"[`{txid_short}`]({explorer_url})"

                    main_embed.add_field(
                        name=f"Transaction #{i}",
                        value=f"Amount: {deposit['amount_crypto']:,.6f} SOL\nTXID: {tx_value}",
                        inline=False
                    )

                main_embed.add_field(name="New SOL Balance", value=f"<:sol:1340981839497793556> {sol_balance:,.6f} SOL", inline=True)

                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.custom_id == "check_deposit_button":
                        item.disabled = True
                        item.style = discord.ButtonStyle.grey
                        item.label = "Checked"

                await self.message.edit(embed=main_embed, view=self, attachments=[])

            elif status == "pending":
                pending_amount = details.get('amount_crypto', 0)
                txid = details.get('txid', 'N/A')
                embed = discord.Embed(
                    title="⏳ Deposit Processing",
                    description=(
                        f"**Address:** `{self.address}`\n"
                        f"**Amount:** {pending_amount:,.6f} SOL\n"
                        f"**TXID:** `{txid}`\n\n"
                        f"Transaction found, waiting for confirmation.\n"
                        f"Please wait a moment and check again."
                    ),
                    color=discord.Color.orange()
                )
                embed.set_footer(text="BetSync Casino | Processing Deposit")
                await interaction.followup.send(embed=embed, ephemeral=True)

            elif status == "no_new":
                embed = discord.Embed(
                    title="🔍 No New Deposits",
                    description=(
                        f"**Address:** `{self.address}`\n\n"
                        f"No new SOL deposits found.\n\n"
                        f"Please ensure you sent SOL to the correct address."
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
            print(f"{Fore.RED}[!] Error in check_deposit_button: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            try:
                await interaction.followup.send("An unexpected error occurred while checking for SOL deposits.", ephemeral=True)
            except:
                pass

    @discord.ui.button(label="History", style=discord.ButtonStyle.grey, custom_id="deposit_history_button", emoji="📜")
    async def deposit_history_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        history_embed = await self.cog._show_deposit_history(self.user_id)
        await interaction.followup.send(embed=history_embed, ephemeral=True)

class SolDeposit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users_db = Users()
        self.notifier = Notifier()
        self.active_deposit_views = {}
        self.button_cooldowns = {}
        self.solana_client = AsyncClient(RPC_URL)

        if not PHANTOM_SEED:
            print(f"{Fore.RED}[!] ERROR: PHANTOM_SEED not found in environment variables!{Style.RESET_ALL}")
        if not ALCHEMY_API:
            print(f"{Fore.YELLOW}[!] WARNING: ALCHEMY_API not found. Using default RPC.{Style.RESET_ALL}")
        if not DEPOSIT_WEBHOOK_URL:
            print(f"{Fore.YELLOW}[!] WARNING: DEPOSIT_WEBHOOK_URL not found.{Style.RESET_ALL}")

    async def cog_unload(self):
        await self.solana_client.close()

    async def _generate_sol_address(self, user_id: int) -> tuple[str | None, str | None]:
        """Generate a unique SOL deposit address for the user."""
        try:
            if not PHANTOM_SEED:
                return None, "PHANTOM_SEED environment variable is not configured."

            # Check if user already has an address
            user_data = self.users_db.fetch_user(user_id)
            if user_data and user_data.get('sol_address'):
                existing_address = user_data.get('sol_address')
                print(f"{Fore.GREEN}[+] Using existing SOL address for user {user_id}: {existing_address}{Style.RESET_ALL}")
                return existing_address, None

            # Always use account 0 (first account) to consolidate funds to main phantom wallet
            seed_bytes = Bip39SeedGenerator(PHANTOM_SEED).Generate()
            bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
            
            # Use unique derivation path for each user but all under account 0
            # This creates unique addresses while keeping funds in the same wallet
            highest_index_user = self.users_db.collection.find_one(
                {"sol_address_index": {"$exists": True}},
                sort=[("sol_address_index", -1)]
            )
            next_index = highest_index_user['sol_address_index'] + 1 if highest_index_user else 0

            # Generate address using account 0 but unique address index
            deposit_address = bip44_mst_ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(next_index).PublicKey().ToAddress()

            # Store in database
            update_data = {
                "$set": {
                    "sol_address": deposit_address,
                    "sol_address_index": next_index,
                    "processed_sol_txids": user_data.get('processed_sol_txids', []) if user_data else []
                }
            }

            result = self.users_db.collection.update_one(
                {"discord_id": user_id},
                update_data,
                upsert=True
            )

            if result.matched_count == 0 and not result.upserted_id:
                return None, "Failed to store address info"
            
            print(f"{Fore.GREEN}[+] Generated new SOL address for user {user_id}: {deposit_address} (index: {next_index}){Style.RESET_ALL}")
            return deposit_address, None

        except Exception as e:
            print(f"{Fore.RED}[!] Error generating SOL address: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            return None, f"Failed to generate deposit address: {e}"

    async def _check_alchemy_transactions(self, address: str) -> list:
        """Check for transactions using Alchemy RPC."""
        try:
            pubkey_address = Pubkey.from_string(address)
            signatures_response = await self.solana_client.get_signatures_for_address(
                pubkey_address,
                limit=20,
                commitment=Finalized
            )
            
            if signatures_response and signatures_response.value:
                # Convert RPC format to transaction list
                transactions = []
                for sig_info in signatures_response.value:
                    if not sig_info.err:  # Only successful transactions
                        transactions.append({
                            'txHash': str(sig_info.signature),
                            'blockTime': sig_info.block_time
                        })
                return transactions
            return []
        except Exception as e:
            print(f"{Fore.RED}[!] Error checking Alchemy transactions: {e}{Style.RESET_ALL}")
            return []

    async def _check_for_deposits(self, user_id: int, address: str) -> tuple[str, dict]:
        """Check for deposits to the address and credit user's wallet."""
        try:
            user_data = self.users_db.fetch_user(user_id)
            if not user_data:
                return "error", {"error": "User data not found."}

            processed_txids = set(user_data.get('processed_sol_txids', []))
            processed_deposits = []

            # Use Alchemy API through RPC
            transactions = await self._check_alchemy_transactions(address)

            if not transactions:
                return "no_new", {}

            # Process transactions
            for tx in transactions:
                tx_hash = tx.get('txHash')
                if not tx_hash or tx_hash in processed_txids:
                    continue

                try:
                    # Get transaction details - convert string to Signature properly
                    from solders.signature import Signature
                    signature = Signature.from_string(tx_hash)
                    tx_detail_response = await self.solana_client.get_transaction(
                        signature,
                        encoding="jsonParsed",
                        max_supported_transaction_version=0,
                        commitment=Finalized
                    )

                    if not tx_detail_response or not tx_detail_response.value:
                        continue

                    tx_data = tx_detail_response.value.transaction
                    if not tx_data or not tx_data.meta:
                        continue

                    # Check for errors
                    if tx_data.meta.err:
                        # Mark as processed to skip in future
                        self.users_db.collection.update_one(
                            {"discord_id": user_id},
                            {"$addToSet": {"processed_sol_txids": tx_hash}}
                        )
                        continue

                    # Calculate SOL received
                    lamports_received = 0
                    account_keys = tx_data.message.account_keys
                    target_pubkey_str = address

                    if tx_data.meta:
                        pre_balances = tx_data.meta.pre_balances
                        post_balances = tx_data.meta.post_balances
                        
                        for i, key in enumerate(account_keys):
                            if i < len(pre_balances) and i < len(post_balances):
                                if str(key.pubkey) == target_pubkey_str:
                                    balance_change = post_balances[i] - pre_balances[i]
                                    if balance_change > 0:
                                        lamports_received = balance_change
                                        break

                    if lamports_received <= 0:
                        # Mark as processed to skip in future
                        self.users_db.collection.update_one(
                            {"discord_id": user_id},
                            {"$addToSet": {"processed_sol_txids": tx_hash}}
                        )
                        continue

                    # Convert lamports to SOL
                    amount_sol = lamports_received / SOL_LAMPORTS

                    # Update user's SOL wallet balance
                    update_result = self.users_db.collection.update_one(
                        {"discord_id": user_id},
                        {"$inc": {"wallet.SOL": amount_sol}}
                    )

                    if update_result.matched_count == 0:
                        print(f"{Fore.RED}[!] Failed to update wallet for user {user_id}{Style.RESET_ALL}")
                        continue

                    # Mark transaction as processed
                    self.users_db.collection.update_one(
                        {"discord_id": user_id},
                        {"$addToSet": {"processed_sol_txids": tx_hash}}
                    )

                    processed_deposits.append({
                        "amount_crypto": amount_sol,
                        "txid": tx_hash
                    })

                    print(f"{Fore.GREEN}[+] Processed SOL deposit: {amount_sol:.6f} SOL for user {user_id}{Style.RESET_ALL}")

                except Exception as e:
                    print(f"{Fore.RED}[!] Error processing transaction {tx_hash}: {e}{Style.RESET_ALL}")
                    continue

            if processed_deposits:
                return "success", {"deposits": processed_deposits}
            else:
                return "no_new", {}

        except Exception as e:
            print(f"{Fore.RED}[!] Error in _check_for_deposits: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            return "error", {"error": f"An unexpected error occurred: {e}"}

    async def _show_deposit_history(self, user_id: int) -> discord.Embed:
        """Show user's SOL deposit history."""
        user_data = self.users_db.fetch_user(user_id)
        if not user_data:
            return discord.Embed(title="Error", description="Could not fetch user data.", color=discord.Color.red())

        history = user_data.get('history', [])
        sol_deposits = [entry for entry in history if entry.get('type') == 'sol_deposit']

        embed = discord.Embed(title="📜 SOL Deposit History", color=discord.Color.purple())

        if not sol_deposits:
            embed.description = "No SOL deposit history found."
            return embed

        description = ""
        for entry in reversed(sol_deposits[-10:]):
            ts = entry.get('timestamp', 'N/A')
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                formatted_ts = dt_obj.strftime("%b %d, %Y %H:%M UTC")
            except:
                formatted_ts = ts

            amount = entry.get('amount_crypto', 0)
            txid = entry.get('txid', 'N/A')
            txid_short = txid[:6] + '...' + txid[-6:] if len(txid) > 12 else txid
            explorer_url = f"https://solscan.io/tx/{txid}"
            tx_link = f"[`{txid_short}`]({explorer_url})" if txid != 'N/A' else "N/A"

            description += f"**{formatted_ts}**: +{amount:,.6f} SOL ({tx_link})\n"

        embed.description = description
        embed.set_footer(text="Showing last 10 SOL deposits.")
        return embed

    @commands.command(name="deposit_sol", aliases=["soldep", "soldeposit"])
    async def deposit_sol(self, ctx, currency: str = None):
        """Generate a SOL deposit address for the user."""
        user_id = ctx.author.id
        username = ctx.author.name

        # Check for existing active view
        if user_id in self.active_deposit_views:
            try:
                existing_message = self.active_deposit_views[user_id]
                await ctx.reply(f"You already have an active SOL deposit session. {existing_message.jump_url}", delete_after=10)
                return
            except (discord.NotFound, AttributeError):
                del self.active_deposit_views[user_id]

        # Generate address
        address, error = await self._generate_sol_address(user_id)

        if error:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error Generating Address",
                description=f"Could not generate SOL deposit address:\n`{error}`",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        if not address:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error Generating Address",
                description="An unknown error occurred while generating the SOL address.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        # Generate QR Code
        qr_buffer = await asyncio.to_thread(generate_qr_code, address, username)
        qr_file = discord.File(qr_buffer, filename=f"sol_deposit_{user_id}.png")

        # Create Embed
        embed = discord.Embed(
            title=f"<:sol:1340981839497793556> Your SOL Deposit Address",
            description=(
                f"Send only **SOL** to the address below. Deposits will be credited to your SOL wallet balance after confirmation.\n\n"
                f"**Address:**\n`{address}`\n\n"
                f"**Network:** Solana (Mainnet)\n"
                f"**Minimum Deposit:** None\n"
                f"**Confirmation:** Finalized status required"
            ),
            color=discord.Color.purple()
        )
        embed.set_image(url=f"attachment://sol_deposit_{user_id}.png")
        embed.set_footer(text="BetSync Casino | Send only SOL to this address")

        # Create View
        view = DepositView(self, user_id, address)

        # Send message
        message = await ctx.reply(embed=embed, file=qr_file, view=view)
        view.message = message
        self.active_deposit_views[user_id] = message

def setup(bot):
    if not PHANTOM_SEED:
        print(f"{Fore.RED}[!] Cannot load SolDeposit Cog: PHANTOM_SEED not set.{Style.RESET_ALL}")
        return
    bot.add_cog(SolDeposit(bot))
    print(f"{Fore.GREEN}[+] {Fore.WHITE}Loaded Cog: {Fore.GREEN}Cogs.sol_deposit{Fore.WHITE}")
