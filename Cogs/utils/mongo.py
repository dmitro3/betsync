from pymongo import MongoClient
import os
import datetime
import asyncio # Added for create_task
from colorama import Back, Fore, Style
from dotenv import load_dotenv
from Cogs.utils.notifier import Notifier # Import Notifier

load_dotenv()

mongodb = MongoClient(os.environ["MONGO"])


class Users:

    def __init__(self):
        self.db = mongodb["BetSync"]
        self.collection = self.db["users"]

    def get_all_users(self):
        return self.collection.find()

    def register_new_user(self, user_data):
        discordid = user_data["discord_id"]
        if self.collection.count_documents({"discord_id": discordid}):
            return False
        else:
            new_user = self.collection.insert_one(user_data)
            return new_user.inserted_id

    def fetch_user(self, user_id):
        if self.collection.count_documents({"discord_id": user_id}):
            return self.collection.find_one({"discord_id": user_id})

        else:
            return False

    def update_balance(self, user_id, amount, currency_type="points", operation="$inc"):
        """Updates the balance field for the specified user.

        Args:
            user_id (int): The Discord ID of the user.
            amount (float): The amount to update.
            currency_type (str, optional): Kept for backwards compatibility. Default is "tokens".
            operation (str, optional): The MongoDB operation to perform, "$set" or "$inc". Defaults to "$set".

        Returns:
            dict: The response from MongoDB.
        """
        try:
            if operation == "$set":
                response = self.collection.update_one(
                    {"discord_id": user_id},
                    {"$set": {"points": amount}}
                )
            else:  # $inc
                response = self.collection.update_one(
                    {"discord_id": user_id},
                    {"$inc": {"points": amount}}
                )
            self.save(user_id)
            return response
        except Exception as e:
            print(f"Error updating balance: {e}")
            return None

    def update_history(self, user_id, history_entry):
        """Add an entry to user's bet history with 100 entry limit"""
        try:
            self.collection.update_one(
                {"discord_id": user_id},
                {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
            )
            return True
        except Exception as e:
            print(f"Error updating user history: {e}")
            return False
            
    def save(self, user_id):
        """
        Syncs a user's wallet based on their points and primary coin.
        Updates the wallet value based on how many points the user has.
        
        Args:
            user_id (int): The Discord ID of the user.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        from colorama import Fore, Style
        import datetime
        
        try:
            # Get user data
            user_data = self.fetch_user(user_id)
            if not user_data:
                print(f"{Fore.RED}[!] {Fore.WHITE}Cannot save user {Fore.RED}{user_id}{Fore.WHITE}: User not found")
                return False
                
            # Currency conversion rates from main.py
            crypto_values = {
                "BTC": 0.00000024,  # 1 point = 0.00000024 btc
                "LTC": 0.00023,     # 1 point = 0.00023 ltc
                "ETH": 0.000010,    # 1 point = 0.000010 eth
                "USDT": 0.0212,     # 1 point = 0.0212 usdt
                "SOL": 0.0001442    # 1 point = 0.0001442 sol
            }
            
            # Get current primary coin and points
            current_primary_coin = user_data.get("primary_coin", "BTC")
            points = user_data.get("points", 0)
            wallet = user_data.get("wallet", {
                "BTC": 0,
                "SOL": 0,
                "ETH": 0,
                "LTC": 0,
                "USDT": 0
            })
            
            # Calculate wallet amount based on the points the user has
            current_coin_amount = points * crypto_values[current_primary_coin]
            
            # Update wallet with current coin value
            wallet[current_primary_coin] = current_coin_amount
            
            # Update database with the wallet value
            update_result = self.collection.update_one(
                {"discord_id": user_id},
                {
                    "$set": {
                        f"wallet.{current_primary_coin}": current_coin_amount
                    }
                }
            )
            
            # Log the action with timestamp
            rn = datetime.datetime.now().strftime("%X")
            print(f"{Fore.GREEN}[+] {Fore.WHITE}{rn} Synced user {Fore.CYAN}{user_id}{Fore.WHITE} wallet: {Fore.YELLOW}{current_primary_coin}={current_coin_amount:.8f}{Fore.WHITE} from {Fore.GREEN}{points}{Fore.WHITE} points")
            
            return True
            
        except Exception as e:
            rn = datetime.datetime.now().strftime("%X")
            print(f"{Fore.RED}[!] {Fore.WHITE}{rn} Error saving user {user_id}: {Fore.RED}{str(e)}{Fore.WHITE}")
            return False


class Servers:

    def __init__(self):
        self.db = mongodb["BetSync"]
        self.collection = self.db["servers"]

    def get_total_all_servers(self):
        return self.collection.count_documents({})

    def new_server(self, dump):
        server_id = dump["server_id"]
        if self.collection.count_documents({"server_id": server_id}):
            return False
        else:
            new_server_ = self.collection.insert_one(dump) 
            return self.collection.find_one({"server_id": server_id})

    def update_server_profit(self, ctx, server_id, amount, game=None):
        """Updates server profit and sends a webhook notification."""
        try:
            # Get server info
            server_info = self.collection.find_one({"server_id": server_id})
            if not server_info:
                print(f"Error: Server {server_id} not found.")
                return False
            server_name = server_info.get("server_name", f"Unknown Server ({server_id})")
            current_wallet = server_info.get("wallet", {})

            # Get user's primary coin and calculate crypto value
            users_db = Users()
            user_data = users_db.fetch_user(ctx.author.id)
            if not user_data:
                 print(f"Error: User {ctx.author.id} not found for server profit update.")
                 # For now, let's assume we need the user's primary coin
                 return False

            primary_coin = user_data.get("primary_coin", "BTC") # Default to BTC if not set
            crypto_values = {
                "BTC": 0.00000024,
                "LTC": 0.00023,
                "ETH": 0.000010,
                "USDT": 0.0212,
                "SOL": 0.0001442
            }
            # Use .get() with default 0 to avoid KeyError if primary_coin isn't in crypto_values
            crypto_value_change = amount * crypto_values.get(primary_coin, 0) # Profit/Loss in crypto

            # Get current balance for the specific coin before update
            current_coin_balance = current_wallet.get(primary_coin, 0)

            # Update server profit in DB
            update_result = self.collection.update_one(
                {"server_id": server_id},
                {"$inc": {f"wallet.{primary_coin}": crypto_value_change}}
            )

            if update_result.modified_count == 0 and not update_result.upserted_id:
                 print(f"Warning: Server profit update didn't modify document for server {server_id}.")
                 # Continue for logging and notification, but be aware.

            # Calculate new balance
            new_coin_balance = current_coin_balance + crypto_value_change

            # Update daily profit data
            PD = ProfitData()
            PD.update_daily_profit(primary_coin, crypto_value_change)

            # Log the update
            rn = datetime.datetime.now().strftime("%X")
            profit_color = Fore.GREEN if crypto_value_change >= 0 else Fore.RED
            print(f"{Back.CYAN}  {Style.DIM}{server_name} - {server_id}{Style.RESET_ALL}{Back.RESET}{Fore.CYAN}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{profit_color}{amount} Points ({crypto_value_change:+.8f} {primary_coin}){Fore.WHITE}{Style.RESET_ALL}  {Fore.MAGENTA}{game}, sv_profit{Fore.WHITE}")

            # Send webhook notification asynchronously
            notifier = Notifier()
            asyncio.create_task(notifier.server_profit_update(
                server_id=server_id,
                server_name=server_name,
                profit_loss_amount=crypto_value_change,
                new_wallet_balance=new_coin_balance,
                currency=primary_coin
            ))

            return True
        except Exception as e:
            print(f"Error updating server profit: {e}")
            # Optionally log the full traceback
            # import traceback
            # traceback.print_exc()
            return False

    def get_np(self, game=None):
        if game:
            npc = self.db["net_profit"]
            return npc.find_one({"game": game})
        else:
            npc = self.db["net_profit"]
            return npc.find_one({})

    def update_history(self, server_id, history_entry):
        """Add an entry to server's bet history with 100 entry limit"""
        try:
            self.collection.update_one(
                {"server_id": server_id},
                {"$push": {"server_bet_history": {"$each": [history_entry], "$slice": -100}}}
            )
            return True
        except Exception as e:
            print(f"Error updating server history: {e}")
            return False

    def add_bet_to_history(self, server_id, history_entry):
        """Alias for update_history for backward compatibility"""
        return self.update_history(server_id, history_entry)

    def fetch_server(self, server_id):
        if self.collection.count_documents({"server_id": server_id}):
            return self.collection.find_one({"server_id": server_id})
        else:
            return False


class ServerProfit:
    def __init__(self):
        self.db = mongodb["BetSync"]
        self.collection = self.db["server_profit"]

    def get_server_profit(self, server_id=None, date=None):
        """
        Get server profit data for a specific server, date, or all servers

        Args:
            server_id: Optional server ID to filter by
            date: Optional date to filter by (defaults to today)

        Returns:
            A single document or list of documents matching the criteria
        """
        # Default to today if no date specified
        if date is None:
            date = datetime.date.today().strftime("%Y-%m-%d")

        # If server_id is provided, return just that server's data
        if server_id:
            return self.collection.find_one({"server_id": server_id, "date": date})

        # Otherwise return all servers for the date
        return list(self.collection.find({"date": date}))

    def update_server_profit(self, server_id, server_name, amount):
        """
        Update server profit for today

        Args:
            server_id: The Discord server ID
            server_name: The name of the server
            amount: The profit amount to add

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get today's date
            today = datetime.date.today().strftime("%Y-%m-%d")

            # Use upsert to handle both new records and updates
            result = self.collection.update_one(
                {"server_id": server_id, "date": today},
                {
                    "$inc": {"profit": amount},
                    "$setOnInsert": {
                        "date": today,
                        "server_id": server_id,
                        "server_name": server_name
                    }
                },
                upsert=True
            )

            rn = datetime.datetime.now().strftime("%X")
            print(f"{Back.CYAN}  {Style.DIM}{server_id}{Style.RESET_ALL}{Back.RESET}{Fore.CYAN}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{Fore.GREEN}{amount} ({round((amount)*0.0212, 3)}$){Fore.WHITE}{Style.RESET_ALL}  {Fore.MAGENTA}sv_profit_record{Fore.WHITE}")

            return True
        except Exception as e:
            print(f"Error updating server profit: {e}")
            return False

    def get_all_server_profits(self, date=None):
        """Get profit data for all servers on a specific date"""
        if date is None:
            date = datetime.date.today().strftime("%Y-%m-%d")

        return list(self.collection.find({"date": date}))


class ProfitData:
    def __init__(self):
        self.db = mongodb["BetSync"]
        self.collection = self.db["profit_data"]

    def update_daily_profit(self, coin, amount, game=None):
        # Convert datetime.date to string format (YYYY-MM-DD)
        today = datetime.date.today().strftime("%Y-%m-%d")
        try:
            # Use upsert to handle both document creation and updating
            # This creates the document if it doesn't exist, or updates it if it does
            # The setOnInsert ensures we set initial values only if creating a new document
            result = self.collection.update_one(
                {"date": today},
                {
                    "$inc": {f"wallet.{coin}": amount},
                    "$setOnInsert": {
                        "date": today,
                        #"games": {}  # Initialize games object if needed
                    }
                },
                upsert=True  # Create document if it doesn't exist
            )

            return result
        except Exception as e:
            print(f"Error updating daily profit: {e}")
            print(f"Details: {str(e)}")  # More detailed error logging
            return False

    def get_profit_data(self, date=None):
        if date:
            # Convert date to string if it's a datetime object
            if isinstance(date, (datetime.date, datetime.datetime)):
                date = date.strftime("%Y-%m-%d")
            return self.collection.find_one({"date": date})
        else:
            return list(self.collection.find())