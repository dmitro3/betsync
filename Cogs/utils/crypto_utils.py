
import requests

def get_crypto_prices():
    """
    Fetch live cryptocurrency prices from CoinGecko
    Returns: Dictionary of crypto prices in USD
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,litecoin,solana,tether",
        "vs_currencies": "usd"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            # Convert to more usable format with consistent keys
            prices = {
                "btc": data.get("bitcoin", {}),
                "eth": data.get("ethereum", {}),
                "ltc": data.get("litecoin", {}),
                "sol": data.get("solana", {}),
                "usdt": data.get("tether", {})
            }
            return prices
        else:
            print(f"Failed to fetch crypto prices. Status Code: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error fetching crypto prices: {e}")
        return {}
