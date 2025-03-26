
import requests
import os
from colorama import Fore
import json
from datetime import datetime, timedelta

class CryptoPrice:
    def __init__(self):
        self.api_url = "https://api.coingecko.com/api/v3/simple/price"
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 300  # Cache duration in seconds (5 minutes)
        self.supported_currencies = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "LTC": "litecoin", 
            "SOL": "solana",
            "USDT": "tether"
        }
        
    def get_prices(self, currencies=None):
        """
        Get current prices for specified cryptocurrencies
        If currencies is None, fetch all supported currencies
        Returns a dictionary with currency codes as keys and prices in USD as values
        """
        if currencies is None:
            currencies = list(self.supported_currencies.keys())
        
        # Convert to lowercase for consistent handling
        currencies = [c.upper() for c in currencies]
        
        # Check which currencies need to be fetched (not in cache or cache expired)
        currencies_to_fetch = []
        result = {}
        
        current_time = datetime.now()
        for currency in currencies:
            if currency not in self.supported_currencies:
                print(f"{Fore.RED}[-] {Fore.WHITE}Unsupported currency: {Fore.RED}{currency}{Fore.WHITE}")
                continue
                
            # Use cache if available and not expired
            if (currency in self.cache and currency in self.cache_time and 
                current_time - self.cache_time[currency] < timedelta(seconds=self.cache_duration)):
                result[currency] = self.cache[currency]
            else:
                currencies_to_fetch.append(currency)
        
        # If there are currencies to fetch, make API call
        if currencies_to_fetch:
            ids = [self.supported_currencies[currency] for currency in currencies_to_fetch if currency in self.supported_currencies]
            if not ids:
                return result
                
            params = {
                "ids": ",".join(ids),
                "vs_currencies": "usd"
            }
            
            try:
                response = requests.get(self.api_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Update cache and result
                    for currency in currencies_to_fetch:
                        coin_id = self.supported_currencies.get(currency)
                        if coin_id in data:
                            price = data[coin_id].get("usd", 0)
                            self.cache[currency] = price
                            self.cache_time[currency] = current_time
                            result[currency] = price
                else:
                    print(f"{Fore.RED}[-] {Fore.WHITE}Failed to fetch crypto prices. Status Code: {Fore.RED}{response.status_code}{Fore.WHITE}")
            except Exception as e:
                print(f"{Fore.RED}[-] {Fore.WHITE}Error fetching crypto prices: {Fore.RED}{str(e)}{Fore.WHITE}")
        
        return result
    
    def get_price(self, currency):
        """Get price for a single currency"""
        currency = currency.upper()
        if currency not in self.supported_currencies:
            print(f"{Fore.RED}[-] {Fore.WHITE}Unsupported currency: {Fore.RED}{currency}{Fore.WHITE}")
            return None
            
        prices = self.get_prices([currency])
        return prices.get(currency)
    
    def get_conversion_rate(self, from_currency, to_currency, amount=1):
        """
        Convert between two cryptocurrencies
        Returns the equivalent amount in the target currency
        """
        prices = self.get_prices([from_currency, to_currency])
        
        if from_currency not in prices or to_currency not in prices:
            return None
            
        # Calculate conversion: (amount in from_currency) * (to_currency price / from_currency price)
        if prices[from_currency] == 0:
            return 0
            
        return amount * (prices[to_currency] / prices[from_currency])
    
    def get_token_value_in_crypto(self, token_amount, currency):
        """
        Convert token amount to equivalent cryptocurrency amount
        Based on token value of 0.0212 USD
        """
        token_value_usd = 0.0212  # USD value per token
        usd_value = token_amount * token_value_usd
        
        currency_price = self.get_price(currency)
        if not currency_price or currency_price == 0:
            return None
            
        return usd_value / currency_price
    
    def get_crypto_value_in_tokens(self, crypto_amount, currency):
        """
        Convert cryptocurrency amount to equivalent token amount
        Based on token value of 0.0212 USD
        """
        token_value_usd = 0.0212  # USD value per token
        
        currency_price = self.get_price(currency)
        if not currency_price:
            return None
            
        usd_value = crypto_amount * currency_price
        return usd_value / token_value_usd

# Example usage:
# crypto = CryptoPrice()
# prices = crypto.get_prices()
# btc_price = crypto.get_price("BTC")
# tokens_in_btc = crypto.get_token_value_in_crypto(100, "BTC")
import requests
import logging
from colorama import Fore

class CryptoUtils:
    @staticmethod
    def get_crypto_prices():
        """
        Fetch the current prices of various cryptocurrencies from CoinGecko API.
        
        Returns:
            dict: Dictionary containing prices or None if the API call fails
        """
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,litecoin,solana,tether",
            "vs_currencies": "usd"
        }
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"{Fore.RED}[-] {Fore.WHITE}Failed to fetch crypto prices. Status Code: {Fore.RED}{response.status_code}{Fore.WHITE}")
                return None
        except Exception as e:
            logging.error(f"{Fore.RED}[-] {Fore.WHITE}Error fetching crypto prices: {e}")
            return None
    
    @staticmethod
    def convert_tokens_to_crypto(token_amount, crypto_symbol):
        """
        Converts a given amount of tokens to a cryptocurrency value.
        
        Args:
            token_amount (float): Amount of tokens to convert
            crypto_symbol (str): Symbol of cryptocurrency to convert to (BTC, ETH, etc.)
            
        Returns:
            float: The equivalent amount in the specified cryptocurrency
        """
        # Get current crypto prices
        prices = CryptoUtils.get_crypto_prices()
        if not prices:
            return None
            
        # Token value in USD (based on the site's conversion rate)
        usd_value = token_amount * 0.0212
        
        # Map symbols to CoinGecko IDs
        symbol_to_id = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "LTC": "litecoin",
            "SOL": "solana",
            "USDT": "tether"
        }
        
        # Get price of the crypto (in USD)
        crypto_id = symbol_to_id.get(crypto_symbol.upper())
        if not crypto_id or crypto_id not in prices:
            return None
            
        crypto_price_usd = prices[crypto_id].get("usd")
        if not crypto_price_usd:
            return None
            
        # Convert USD value to crypto amount
        return usd_value / crypto_price_usd
