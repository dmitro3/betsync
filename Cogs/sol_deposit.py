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
from solders.keypair import Keypair # Keep for potential use, though bip_utils handles derivation
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Finalized
from solana.exceptions import SolanaRpcException
# Import necessary BIP44 components
from bip_utils import Bip39SeedGenerator, Bip39MnemonicValidator, Bip44, Bip44Coins, Bip44Changes
from bip_utils.bip.bip44.bip44 import Bip44Changes
from hashlib import sha256
import base58
# import nacl.signing # No longer needed for address generation
from colorama import Fore, Style
from PIL import Image, ImageDraw, ImageFont
import traceback # Added for detailed error logging

from Cogs.utils.mongo import Users
from Cogs.utils.notifier import Notifier
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import get_crypto_price # Although rate is fixed in mongo.py

# Load environment variables
load_dotenv()

PHANTOM_SEED = os.environ.get("PHANTOM_SEED")
MAINWALLET_SOL = os.environ.get("MAINWALLET_SOL")
SOLSCAN_API_KEY = os.environ.get("SOLSCAN_API_KEY") # Kept for potential future use, but not used for checking
DEPOSIT_WEBHOOK_URL = os.environ.get("DEPOSIT_WEBHOOK")
MONGO_URI = os.environ.get("MONGO") # Needed for Users() initialization if not handled globally

# Constants
# Rate from Cogs/utils/mongo.py: 1 point = 0.0001442 SOL
SOL_CONVERSION_RATE = 0.0001442
SOL_LAMPORTS = 1_000_000_000 # 1 SOL = 1,000,000,000 lamports
# Solana uses finalization, not confirmations like BTC/LTC. We check for finalized status.
REQUIRED_COMMITMENT = Finalized
# SOLSCAN_API_URL = "https://api.solscan.io" # No longer primary source
# Using Solana mainnet-beta RPC endpoint
RPC_URL = "https://api.mainnet-beta.solana.com"
CHECK_DEPOSIT_COOLDOWN = 15 # seconds
EMBED_TIMEOUT = 600 # 10 minutes in seconds
# Standard Solana derivation path template (account index is the variable part)
SOL_DERIVATION_PATH_ACCOUNT_TEMPLATE = "m/44'/501'/{}'/0'" # BIP44 standard with change path: m / purpose' / coin_type' / account' / change'
# Phantom and most wallets use the change path 0' for deposit addresses

# --- Helper Functions ---

def generate_qr_code(address: str, username: str):
    """Generates a styled QR code image with text for Solana."""
    # 1. Generate base QR code
    # <<< CHANGE HERE: Remove "solana:" prefix >>>
    qr_data = address # Encode just the address
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

    # 2. Prepare fonts and text
    try:
        # Adjust font paths if necessary relative to the workspace root
        title_font = ImageFont.truetype("Helvetica-Bold.ttf", 30)
        subtitle_font = ImageFont.truetype("Helvetica.ttf", 18)
        brand_font = ImageFont.truetype("Helvetica-Bold.ttf", 36)
    except IOError:
        print(f"{Fore.YELLOW}[!] Warning: Font files not found. Using default font.{Style.RESET_ALL}")
        # Fallback to default font if specific fonts aren't found
        try:
            title_font = ImageFont.truetype("arial.ttf", 30) # Try Arial as fallback
            subtitle_font = ImageFont.truetype("arial.ttf", 18)
            brand_font = ImageFont.truetype("arial.ttf", 36)
        except IOError:
             title_font = ImageFont.load_default()
             subtitle_font = ImageFont.load_default()
             brand_font = ImageFont.load_default()


    title_text = f"{username}'s Deposit Address" # Changed title slightly
    instruction_text = "Only send SOLANA (SOL)" # Updated instruction
    brand_text = "BETSYNC"

    # 3. Calculate image dimensions and text positions using getbbox
    padding = 20
    title_bbox = title_font.getbbox(title_text)
    instruction_bbox = subtitle_font.getbbox(instruction_text) # Use subtitle font for instruction
    brand_bbox = brand_font.getbbox(brand_text)

    title_width = title_bbox[2] - title_bbox[0]
    title_height = title_bbox[3] - title_bbox[1]
    instruction_width = instruction_bbox[2] - instruction_bbox[0]
    instruction_height = instruction_bbox[3] - instruction_bbox[1]
    brand_width = brand_bbox[2] - brand_bbox[0]
    brand_height = brand_bbox[3] - brand_bbox[1]

    # Adjust total height calculation
    total_height = padding + title_height + padding // 2 + qr_height + padding // 2 + instruction_height + padding // 2 + brand_height + padding
    max_width = max(qr_width, title_width, instruction_width, brand_width)
    image_width = max_width + 2 * padding

    # 4. Create final image canvas (white background)
    final_img = Image.new('RGB', (image_width, total_height), color='white')
    draw = ImageDraw.Draw(final_img)

    # 5. Draw elements
    # Title
    title_x = (image_width - title_width) // 2
    title_y = padding
    draw.text((title_x, title_y), title_text, font=title_font, fill="black")

    # QR Code
    qr_x = (image_width - qr_width) // 2
    qr_y = title_y + title_height + padding // 2
    final_img.paste(qr_img, (qr_x, qr_y))

    # Instruction Text
    instruction_x = (image_width - instruction_width) // 2
    instruction_y = qr_y + qr_height + padding // 2
    draw.text((instruction_x, instruction_y), instruction_text, font=subtitle_font, fill="black")

    # Brand Name
    brand_x = (image_width - brand_width) // 2
    brand_y = instruction_y + instruction_height + padding // 2 # Position below instruction
    draw.text((brand_x, brand_y), brand_text, font=brand_font, fill="black")

    # 6. Save to buffer
    buffer = io.BytesIO()
    final_img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# --- Deposit View ---

class DepositView(discord.ui.View):
    def __init__(self, cog_instance, user_id: int, address: str):
        super().__init__(timeout=EMBED_TIMEOUT)
        self.cog = cog_instance
        self.user_id = user_id
        self.address = address
        self.message = None # Will be set after sending the initial message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command initiator can interact."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your deposit interface!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        """Handle view timeout."""
        if self.message:
            try:
                # Disable buttons
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True

                # Create timeout embed
                timeout_embed = discord.Embed(
                    title="<:no:1344252518305234987> | Embed Timeout",
                    description=f"Your deposit session for address `{self.address}` has timed out.\n\n"
                                f"Please run `!dep sol` again if you need to check for deposits or start a new one.",
                    color=discord.Color.red()
                )
                timeout_embed.set_footer(text="BetSync Casino")
                await self.message.edit(embed=timeout_embed, view=None, attachments=[])
            except discord.NotFound:
                print(f"{Fore.YELLOW}[!] Warning: Failed to edit timed-out deposit message for user {self.user_id} (message not found).{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[!] Error editing timed-out deposit message for user {self.user_id}: {e}{Style.RESET_ALL}")
        # Remove from active views
        if self.user_id in self.cog.active_deposit_views:
            try:
                del self.cog.active_deposit_views[self.user_id]
            except KeyError:
                 pass

    @discord.ui.button(label="Check for New Deposits", style=discord.ButtonStyle.green, custom_id="check_deposit_button", emoji="🔄")
    async def check_deposit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Button to check for new deposits."""
        now = time.time()
        cooldown_key = f"{self.user_id}_check_deposit_sol" # Unique cooldown key
        last_check_time = self.cog.button_cooldowns.get(cooldown_key, 0)

        if now - last_check_time < CHECK_DEPOSIT_COOLDOWN:
            remaining = CHECK_DEPOSIT_COOLDOWN - (now - last_check_time)
            await interaction.response.send_message(f"Please wait {remaining:.1f} more seconds before checking again.", ephemeral=True)
            return

        self.cog.button_cooldowns[cooldown_key] = now
        await interaction.response.defer(ephemeral=True)

        try:
            # Check for deposits using the cog's method
            status, details = await self.cog._check_for_deposits(self.user_id, self.address)

            if status == "success":
                # Details should contain a list of processed deposits
                deposits = details.get('deposits', [])
                if not deposits: # Should not happen if status is success, but check anyway
                     await interaction.followup.send("Deposit check successful, but no deposit details found. Please contact support.", ephemeral=True)
                     return

                total_sol = sum(d['amount_crypto'] for d in deposits)
                # Points are calculated based on the direct SOL wallet update, not a separate points field here

                # Fetch updated user data to get the new SOL balance
                updated_user = self.cog.users_db.fetch_user(self.user_id)
                if not updated_user:
                    print(f"{Fore.RED}[!] Failed to fetch updated user data for {self.user_id} after deposit.{Style.RESET_ALL}")
                    await interaction.followup.send("Deposit processed, but failed to fetch updated balance. Please check your balance or contact support.", ephemeral=True)
                    return

                sol_balance = updated_user.get("wallet", {}).get("SOL", 0) # Get the updated SOL balance

                # --- Send Notification and Update History ---
                for deposit in deposits:
                    sol_price = await get_crypto_price('solana') # Use helper for USD value
                    usd_value = deposit['amount_crypto'] * sol_price if sol_price else None

                    # Send notification (assuming notifier handles SOL)
                    await self.cog.notifier.deposit_notification(
                        user_id=self.user_id,
                        username=interaction.user.name,
                        amount_crypto=deposit['amount_crypto'],
                        currency="SOL",
                        usd_value=usd_value,
                        txid=deposit['txid'],
                        address=self.address
                    )

                    # Update history
                    history_entry = {
                        "type": "sol_deposit",
                        "amount_crypto": deposit['amount_crypto'],
                        "currency": "SOL",
                        "usd_value": usd_value,
                        "txid": deposit['txid'], # Solana calls this 'signature'
                        "address": self.address,
                        "status": "finalized", # Solana uses finalization
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                    }
                    self.cog.users_db.update_history(self.user_id, history_entry)

                    # Update total deposit amount in USD if value exists
                    if usd_value:
                        self.cog.users_db.collection.update_one(
                            {"discord_id": self.user_id},
                            {"$inc": {"total_deposit_amount_usd": usd_value}}
                        )
                # --- End Notification and History ---


                # --- Update Embed ---
                if not self.message:
                    await interaction.followup.send("Error: Could not find the original deposit message to update.", ephemeral=True)
                    return

                main_embed = self.message.embeds[0]
                main_embed.title = "<:yes:1355501647538815106> | Deposit Success"
                main_embed.description = f"<:sol:1340981839497793556> **+{total_sol:,.9f} SOL** from {len(deposits)} transaction(s)" # SOL uses 9 decimal places
                main_embed.clear_fields()
                main_embed.set_image(url=None)  # Remove QR code image

                # Show each transaction
                for i, deposit in enumerate(deposits, 1):
                    txid = deposit['txid']
                    txid_short = txid[:10] + '...' + txid[-10:] if len(txid) > 20 else txid
                    explorer_url = f"https://solscan.io/tx/{txid}" # Keep Solscan link for user convenience
                    tx_value = f"[`{txid_short}`]({explorer_url})" if txid != 'N/A' else "N/A"

                    main_embed.add_field(
                        name=f"Transaction #{i}",
                        value=f"Amount: {deposit['amount_crypto']:,.9f} SOL\nTXID: {tx_value}",
                        inline=False
                    )

                # Show new balance (fetched earlier)
                main_embed.add_field(name="New SOL Balance", value=f"<:sol:1340981839497793556> {sol_balance:,.9f} SOL", inline=True)

                # Disable check button
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.custom_id == "check_deposit_button":
                        item.disabled = True
                        item.style = discord.ButtonStyle.grey
                        item.label = "Checked"

                await self.message.edit(embed=main_embed, view=self, attachments=[])
                # No followup needed as we edited the main message

            elif status == "pending":
                # This status might be less common now as we fetch finalized txns directly
                # But keep it in case get_transaction returns a non-finalized status somehow
                pending_amount = details.get('amount_crypto', 0)
                txid = details.get('txid', 'N/A')
                embed = discord.Embed(
                    title="⏳ Deposit Processing",
                    description=(
                        f"**Address:** `{self.address}`\n"
                        f"**Amount:** {pending_amount:,.9f} SOL\n"
                        f"**TXID:** `{txid}`\n\n"
                        f"Transaction found, waiting for finalization on the Solana network.\n"
                        f"Please wait a minute and check again."
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
                        f"No new finalized SOL deposits found.\n\n"
                        f"Please ensure you sent SOL to the correct address and the transaction is finalized."
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
            print(f"{Fore.RED}[!] Error in check_deposit_button (SOL) interaction for user {self.user_id}: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            try:
                await interaction.followup.send("An unexpected error occurred while checking for SOL deposits. Please try again later.", ephemeral=True)
            except discord.InteractionResponded:
                 pass

    @discord.ui.button(label="History", style=discord.ButtonStyle.grey, custom_id="deposit_history_button", emoji="📜")
    async def deposit_history_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Button to show deposit history."""
        await interaction.response.defer(ephemeral=True)
        history_embed = await self.cog._show_deposit_history(self.user_id)
        await interaction.followup.send(embed=history_embed, ephemeral=True)

# --- SOL Deposit Cog ---

class SolDeposit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users_db = Users()
        self.notifier = Notifier()
        self.active_deposit_views = {} # user_id: message_object
        self.button_cooldowns = {} # key: timestamp
        self.solana_client = AsyncClient(RPC_URL) # Async client for Solana RPC

        if not PHANTOM_SEED:
            print(f"{Fore.RED}[!] ERROR: PHANTOM_SEED not found in environment variables! SOL deposits will not work.{Style.RESET_ALL}")
        # Removed SOLSCAN_API_KEY check as it's not essential for RPC method
        # if not SOLSCAN_API_KEY:
        #      print(f"{Fore.YELLOW}[!] WARNING: SOLSCAN_API_KEY not found. Deposit checking might fail or be rate-limited.{Style.RESET_ALL}")
        if not DEPOSIT_WEBHOOK_URL:
            print(f"{Fore.YELLOW}[!] WARNING: DEPOSIT_WEBHOOK_URL not found. Deposit notifications will not be sent.{Style.RESET_ALL}")

    async def cog_unload(self):
        """Close the Solana client when the cog unloads."""
        await self.solana_client.close()

    async def _generate_sol_address(self, user_id: int) -> tuple[str | None, str | None]:
        """Generates a deposit address that automatically forwards to main account."""
        try:
            if not PHANTOM_SEED:
                return None, "PHANTOM_SEED environment variable is not configured."
            if not MAINWALLET_SOL:
                return None, "MAINWALLET_SOL environment variable is not configured."

            # Generate unique deposit address for tracking
            seed_bytes = Bip39SeedGenerator(PHANTOM_SEED).Generate()
            bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
            
            # Get next available index
            user_data = self.users_db.fetch_user(user_id)
            existing_index = user_data.get('sol_address_index', None) if user_data else None
            
            if existing_index is None:
                highest_index_user = self.users_db.collection.find_one(
                    {"sol_address_index": {"$exists": True}},
                    sort=[("sol_address_index", -1)]
                )
                next_index = highest_index_user['sol_address_index'] + 1 if highest_index_user else 0
            else:
                next_index = existing_index

            # Generate unique tracking address with proper derivation path
            tracking_address = bip44_mst_ctx.Purpose().Coin().Account(next_index).Change(Bip44Changes.CHAIN_EXT).PublicKey().ToAddress()

            # Store tracking info
            update_data = {
                "$set": {
                    "sol_address": tracking_address,
                    "sol_address_index": next_index,
                    "sol_main_account": MAINWALLET_SOL,
                    "processed_sol_txids": user_data.get('processed_sol_txids', []) if user_data else []
                }
            }

            result = self.users_db.collection.update_one(
                {"discord_id": user_id},
                update_data,
                upsert=True
            )

            if result.matched_count == 0 and not result.upserted_id:
                return None, "Failed to store address tracking info"
            
            print(f"{Fore.GREEN}[+] Generated tracking address: {tracking_address} (Forwarding to main: {MAINWALLET_SOL}){Style.RESET_ALL}")
            return tracking_address, None

        except Exception as e:
            print(f"{Fore.RED}[!] Error generating deposit address: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            return None, f"Failed to generate deposit address: {e}"

    async def _check_for_deposits(self, user_id: int, address: str) -> tuple[str, dict]:
        """Checks for deposits to the tracking address and internally credits balance."""
        processed_deposits_details = []
        first_pending_tx = None # Keep track if we see any non-finalized (less likely now)

        try:
            user_data = self.users_db.fetch_user(user_id)
            if not user_data:
                 print(f"{Fore.RED}[!] User data not found for user {user_id} at start of SOL deposit check.{Style.RESET_ALL}")
                 return "error", {"error": "User data not found."}

            processed_txids = set(user_data.get('processed_sol_txids', []))

            # Use Solana RPC to find transactions
            try:
                pubkey_address = Pubkey.from_string(address)
                # Fetch recent signatures (adjust limit as needed)
                signatures_response = await self.solana_client.get_signatures_for_address(
                    pubkey_address,
                    limit=20, # Fetch more signatures to increase chance of finding recent ones
                    commitment=Finalized # Only look for finalized transactions
                )

                if not signatures_response or not signatures_response.value:
                    print(f"{Fore.BLUE}[SOL Check - {address}] No finalized signatures found via RPC.{Style.RESET_ALL}")
                    return "no_new", {}

                signatures = signatures_response.value

            except SolanaRpcException as e:
                print(f"{Fore.RED}[!] Solana RPC Error fetching signatures for {address}: {e}{Style.RESET_ALL}")
                return "error", {"error": f"RPC Error fetching signatures: {e}"}
            except Exception as e:
                print(f"{Fore.RED}[!] Unexpected error fetching signatures for {address}: {e}{Style.RESET_ALL}")
                traceback.print_exc()
                return "error", {"error": f"Unexpected error fetching signatures: {e}"}

            # Process Signatures
            for sig_info in reversed(signatures): # Process oldest first within the batch
                tx_signature = str(sig_info.signature)

                if tx_signature in processed_txids:
                    continue # Skip already processed transactions

                # Check if transaction failed early (RPC error in signature list)
                if sig_info.err:
                    print(f"{Fore.YELLOW}[SOL Check] Skipping TX {tx_signature} - RPC indicated error in signature list: {sig_info.err}{Style.RESET_ALL}")
                    # Add to processed to avoid re-checking failed txns
                    self.users_db.collection.update_one({"discord_id": user_id}, {"$addToSet": {"processed_sol_txids": tx_signature}})
                    continue

                # Fetch full transaction details
                try:
                    print(f"{Fore.BLUE}[SOL Check - {address}] Fetching details for TX: {tx_signature}{Style.RESET_ALL}")
                    tx_detail_response = await self.solana_client.get_transaction(
                        sig_info.signature,
                        encoding="jsonParsed", # Easier parsing
                        max_supported_transaction_version=0, # Specify version if needed
                        commitment=Finalized # Ensure we get finalized details
                    )

                    if not tx_detail_response or not tx_detail_response.value:
                        print(f"{Fore.YELLOW}[SOL Check] Could not fetch details for TX {tx_signature}, skipping.{Style.RESET_ALL}")
                        continue

                    # Access the nested transaction object correctly
                    tx_data = tx_detail_response.value.transaction
                    if not tx_data:
                        print(f"{Fore.YELLOW}[SOL Check] No transaction data found within the response for TX {tx_signature}, skipping.{Style.RESET_ALL}")
                        continue

                    tx_meta = tx_data.meta # Access meta from tx_data

                    # Check for transaction error in meta
                    if tx_meta and tx_meta.err:
                        print(f"{Fore.YELLOW}[SOL Check] Skipping TX {tx_signature} - Transaction meta has error: {tx_meta.err}{Style.RESET_ALL}")
                        # Add to processed to avoid re-checking failed txns
                        self.users_db.collection.update_one({"discord_id": user_id}, {"$addToSet": {"processed_sol_txids": tx_signature}})
                        continue

                    # Find the SOL transfer to our deposit address by checking balance changes
                    lamports_received = 0
                    # Access message from tx_data correctly
                    if not tx_data.message:
                         print(f"{Fore.YELLOW}[SOL Check] No message found in transaction data for TX {tx_signature}, skipping.{Style.RESET_ALL}")
                         continue
                    account_keys = tx_data.message.account_keys
                    target_pubkey_str = address # Our deposit address

                    if tx_meta:
                        pre_balances = tx_meta.pre_balances
                        post_balances = tx_meta.post_balances
                        for i, key in enumerate(account_keys):
                            # Ensure index is within bounds for balance arrays
                            if i < len(pre_balances) and i < len(post_balances):
                                if str(key.pubkey) == target_pubkey_str:
                                     balance_change = post_balances[i] - pre_balances[i]
                                     if balance_change > 0:
                                         lamports_received = balance_change
                                         print(f"{Fore.GREEN}[SOL Check - {address}] Found balance change for {target_pubkey_str} in TX {tx_signature}: +{lamports_received} lamports{Style.RESET_ALL}")
                                         break # Found the relevant balance change

                    if lamports_received <= 0:
                        # This transaction didn't result in a direct SOL increase for the target address.
                        # It might be an SPL transfer, NFT mint, or something else. We only care about direct SOL deposits.
                        print(f"{Fore.BLUE}[SOL Check - {address}] TX {tx_signature} did not result in a direct SOL balance increase for {target_pubkey_str}. Skipping.{Style.RESET_ALL}")
                        # Add to processed to avoid re-checking irrelevant txns
                        self.users_db.collection.update_one({"discord_id": user_id}, {"$addToSet": {"processed_sol_txids": tx_signature}})
                        continue

                except SolanaRpcException as e:
                    print(f"{Fore.RED}[!] Solana RPC Error fetching details for {tx_signature}: {e}{Style.RESET_ALL}")
                    # Potentially treat as temporary error and don't add to processed_txids yet
                    continue # Skip processing this tx for now
                except Exception as e:
                    print(f"{Fore.RED}[!] Unexpected error processing details for {tx_signature}: {e}{Style.RESET_ALL}")
                    traceback.print_exc()
                    continue # Skip processing this tx for now

                # Transaction is valid, finalized, and resulted in SOL deposit
                amount_crypto = round(lamports_received / SOL_LAMPORTS, 9) # Convert lamports to SOL

                # --- Process Finalized Deposit (Existing Logic) ---
                # Update wallet.SOL directly
                update_result_wallet = self.users_db.collection.update_one(
                    {"discord_id": user_id},
                    {"$inc": {"wallet.SOL": amount_crypto}}
                )
                if not update_result_wallet or update_result_wallet.matched_count == 0:
                    print(f"{Fore.RED}[!] Failed to update wallet.SOL for user {user_id} for txid {tx_signature}. Aborting processing for this TX.{Style.RESET_ALL}")
                    continue # Skip this transaction if wallet update fails

                print(f"{Fore.GREEN}[+] Updated wallet.SOL for user {user_id} by {amount_crypto:.9f} SOL for txid {tx_signature}{Style.RESET_ALL}")

                # Add to processed list in DB immediately to prevent reprocessing
                self.users_db.collection.update_one(
                    {"discord_id": user_id},
                    {"$addToSet": {"processed_sol_txids": tx_signature}}
                )

                # Add details for the final success message
                processed_deposits_details.append({
                    "amount_crypto": amount_crypto,
                    "txid": tx_signature,
                    # Add other relevant details if needed
                })
                # --- End Processing Finalized Deposit ---

            # --- Determine Final Status ---
            if processed_deposits_details:
                # Call save to potentially update points if SOL is primary (though deposit updates wallet directly)
                # This might be redundant if points aren't directly used for SOL deposits
                # await asyncio.to_thread(self.users_db.save, user_id) # Consider if save() logic needs adjustment for direct wallet updates
                return "success", {"deposits": processed_deposits_details}
            # No need for 'pending' check here as we only fetch finalized signatures
            # elif first_pending_tx:
            #     return "pending", first_pending_tx # Return details of the first pending tx found
            else:
                # If we processed signatures but none resulted in a valid deposit for us
                return "no_new", {}
            # --- End Final Status Determination ---

        except Exception as e:
            print(f"{Fore.RED}[!] Unexpected error in _check_for_deposits (SOL) for user {user_id}: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            return "error", {"error": f"An unexpected error occurred: {e}"}

    async def _show_deposit_history(self, user_id: int) -> discord.Embed:
        """Shows the user's SOL deposit history."""
        user_data = self.users_db.fetch_user(user_id)
        if not user_data:
            return discord.Embed(title="Error", description="Could not fetch user data.", color=discord.Color.red())

        history = user_data.get('history', [])
        sol_deposits = [entry for entry in history if entry.get('type') == 'sol_deposit']

        embed = discord.Embed(title="📜 SOL Deposit History", color=discord.Color.purple()) # Solana color

        if not sol_deposits:
            embed.description = "No SOL deposit history found."
            return embed

        description = ""
        for entry in reversed(sol_deposits[-10:]): # Show last 10
            ts = entry.get('timestamp', 'N/A')
            # Attempt to parse timestamp
            try:
                 dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                 # Format timestamp for display (e.g., "Apr 04, 2025 15:55 UTC")
                 formatted_ts = dt_obj.strftime("%b %d, %Y %H:%M UTC")
            except:
                 formatted_ts = ts # Keep original if parsing fails

            amount = entry.get('amount_crypto', 0)
            txid = entry.get('txid', 'N/A')
            txid_short = txid[:6] + '...' + txid[-6:] if len(txid) > 12 else txid
            explorer_url = f"https://solscan.io/tx/{txid}" # Keep Solscan link
            tx_link = f"[`{txid_short}`]({explorer_url})" if txid != 'N/A' else "N/A"

            description += f"**{formatted_ts}**: +{amount:,.9f} SOL ({tx_link})\n"

        embed.description = description
        embed.set_footer(text="Showing last 10 SOL deposits.")
        return embed

    @commands.command(name="deposit_sol", aliases=["soldep", "soldeposit"])
    async def deposit_sol(self, ctx, currency: str = None):
        """Generates a unique SOL deposit address for the user."""
        user_id = ctx.author.id
        username = ctx.author.name

        # Check if a view is already active for this user
        if user_id in self.active_deposit_views:
            try:
                # Try to jump to the existing message
                existing_message = self.active_deposit_views[user_id]
                await ctx.reply(f"You already have an active SOL deposit session. {existing_message.jump_url}", delete_after=10)
                return
            except (discord.NotFound, AttributeError):
                 # If message fetch fails, remove the stale entry
                 del self.active_deposit_views[user_id]


        # Generate or retrieve address
        address, error = await self._generate_sol_address(user_id)

        # <<< INDENTATION FIX START >>>
        if error:
            embed = discord.Embed(title="<:no:1344252518305234987> | Error Generating Address", description=f"Could not generate SOL deposit address:\n`{error}`", color=discord.Color.red())
            await ctx.reply(embed=embed)
            return

        if not address:
            embed = discord.Embed(title="<:no:1344252518305234987> | Error Generating Address", description="An unknown error occurred while generating the SOL address.", color=discord.Color.red())
            await ctx.reply(embed=embed)
            return
        # <<< INDENTATION FIX END >>>

        # Generate QR Code
        qr_buffer = await asyncio.to_thread(generate_qr_code, address, username)
        qr_file = discord.File(qr_buffer, filename=f"sol_deposit_{user_id}.png")

        # Create Embed
        embed = discord.Embed(
            title=f"<:sol:1340981839497793556> Your SOL Deposit Address",
            description=(
                f"Send only **SOL** to the address below. Deposits will be credited to your `wallet.SOL` balance after finalization.\n\n"
                f"**Address:**\n`{address}`\n\n"
                f"**Network:** Solana (Mainnet-Beta)\n"
                f"**Minimum Deposit:** None\n"
                f"**Confirmation:** Finalized status required" # Clarify Solana finalization
            ),
            color=discord.Color.purple() # Solana color
        )
        embed.set_image(url=f"attachment://sol_deposit_{user_id}.png")
        embed.set_footer(text="BetSync Casino | Deposits are checked for finalization.")

        # Create View
        view = DepositView(self, user_id, address)

        # Send message and store it
        message = await ctx.reply(embed=embed, file=qr_file, view=view)
        view.message = message # Assign message to view for later editing
        self.active_deposit_views[user_id] = message # Store active view message


def setup(bot):
    # Ensure dependencies are met before adding cog
    if not PHANTOM_SEED:
        print(f"{Fore.RED}[!] Cannot load SolDeposit Cog: PHANTOM_SEED not set.{Style.RESET_ALL}")
        return
    # Add more checks if needed (e.g., for libraries)
    bot.add_cog(SolDeposit(bot))
    print(f"{Fore.GREEN}[+] {Fore.WHITE}Loaded Cog: {Fore.GREEN}Cogs.sol_deposit{Fore.WHITE}")
