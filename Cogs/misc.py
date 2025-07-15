games = [
            "🎲 **dice** - Roll dice and predict outcomes",
            "🪙 **coinflip** - Classic heads or tails",
            "🎰 **wheel** - Spin the fortune wheel",
            "🎰 **slots** - Premium slot machine with multiple paylines",
            "💎 **mines** - Navigate through a minefield",
            "🃏 **blackjack** - Beat the dealer to 21",
            "🎯 **limbo** - High-risk, high-reward multiplier game",
            "🎮 **hilo** - Guess if the next card is higher or lower",
            "🎲 **keno** - Pick numbers and win big",
            "⚽ **penalty** - Score penalty shots",
            "🏃 **crosstheroad** - Cross the road safely",
            "🎪 **plinko** - Drop the ball and watch it bounce",
            "🎰 **cases** - Open cases for rewards",
            "🎯 **pump** - Time your pump perfectly",
            "🏁 **race** - Bet on racing outcomes",
            "🃏 **baccarat** - Classic casino card game",
            "🔥 **tower** - Climb the tower for rewards",
            "❌⭕ **tictactoe** - Play tic-tac-toe with friends",
            "🃏 **poker** - Texas Hold'em poker",
            "🎲 **match** - Memory matching game",
            "📱 **carddraw** - Draw cards for prizes"
        ]

help_commands = [
            "🎲 `dice <amount> <prediction>` - Roll dice game",
            "🪙 `coinflip <amount> <side>` - Flip a coin",
            "🎰 `wheel <amount>` - Spin the wheel",
            "🎰 `slots <amount> [spins]` - Premium slot machine",
            "💎 `mines <amount> <mines>` - Minesweeper game",
            "🃏 `blackjack <amount>` - Blackjack card game",
            "🎯 `limbo <amount> <multiplier>` - Limbo game",
            "🎮 `hilo <amount>` - Higher or lower game",
            "🎲 `keno <amount> <numbers>` - Keno lottery",
            "⚽ `penalty <amount>` - Penalty shootout",
            "🏃 `crosstheroad <amount>` - Cross the road",
            "🎪 `plinko <amount> <lines>` - Plinko game",
            "🎰 `cases <amount>` - Open mystery cases",
            "🎯 `pump <amount>` - Pump timing game",
            "🏁 `race <amount> <horse>` - Horse racing",
            "🃏 `baccarat <amount> <bet>` - Baccarat card game",
            "🔥 `tower <amount>` - Tower climbing game"
]

user_games = {}  # Track active games per user

async def slots(ctx, amount, spins=1):
    user_id = ctx.author.id
    if user_id in user_games:
        await ctx.send("Please wait for your current game to finish.")
        return

    user_games[user_id] = True  # Mark game as running
    try:
        # Slots game logic here
        await ctx.send(f"Starting slots game for {ctx.author.name} with amount {amount} and {spins} spins.")
        # Simulate game delay
        await asyncio.sleep(5)
    finally:
        del user_games[user_id]  # Game finished, remove from active games


async def games_command(ctx):
    await ctx.send("\n".join(games))

async def help_command(ctx):
    await ctx.send("\n".join(help_commands))

import asyncio
# Example usage (replace with actual bot command handlers)
class Context:  # Mock context for testing
    def __init__(self, author):
        self.author = author

    async def send(self, message):
        print(message)

class Author:
    def __init__(self, id, name):
        self.id = id
        self.name = name

async def main():
    user1 = Author(123, "Alice")
    user2 = Author(456, "Bob")
    ctx1 = Context(user1)
    ctx2 = Context(user2)

    await games_command(ctx1)
    await help_command(ctx1)
    await slots(ctx1, 100)
    await slots(ctx1, 50) # will be blocked
    await asyncio.sleep(1)
    await slots(ctx2, 200) # will not be blocked since it is different user

if __name__ == "__main__":
    asyncio.run(main())