import ccxt

print("Crypto Trading Bot Ready!")

# Example: connect to Binance
exchange = ccxt.binance({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET_KEY'
})

balance = exchange.fetch_balance()
print(balance)
