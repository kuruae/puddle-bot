import json
import aiohttp
import discord
from discord.ext import tasks
from config import DISCORD_TOKEN, CHANNEL_ID, PLAYER_IDS

CACHE_FILE = "cache.json"

class GGSTBot(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.cache = {}
        self.load_cache()

    def load_cache(self):
        try:
            with open(CACHE_FILE, "r") as f:
                self.cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.cache = {}

    def save_cache(self):
        with open(CACHE_FILE, "w") as f:
            json.dump(self.cache, f)

    async def setup_hook(self):
        # Ne pas démarrer la tâche ici, attendre on_ready
        pass

    async def on_ready(self):
        print(f"Bot connecté en tant que {self.user}")
        print(f"Membre de {len(self.guilds)} serveur(s)")
        
        # Démarrer la tâche maintenant que le bot est prêt
        if not self.poll_matches.is_running():
            print("Démarrage de la surveillance des matches...")
            self.poll_matches.start()

    @tasks.loop(seconds=5)
    async def poll_matches(self):
        await self.wait_until_ready()
        
        if not self.guilds:
            print("ERREUR: Le bot n'est membre d'aucun serveur Discord!")
            return
        
        channel = self.get_channel(CHANNEL_ID)
        if channel is None:
            print(f"ERREUR: Impossible de récupérer le channel ID {CHANNEL_ID}.")
            return

        async with aiohttp.ClientSession() as session:
            for name, player_id in PLAYER_IDS.items():
                await self.check_player(session, channel, name, player_id)

        self.save_cache()

    async def check_player(self, session: aiohttp.ClientSession, channel: discord.TextChannel, name: str, player_id: str):
        player_url = f"https://puddle.farm/api/player/{player_id}"
        async with session.get(player_url) as resp:
            if resp.status != 200:
                print(f"Failed to fetch player info for {name}: {resp.status}")
                return
            player_data = await resp.json()

        player_cache = self.cache.setdefault(player_id, [])

        for char_data in player_data.get("ratings", []):
            char_short = char_data["char_short"]
            history_url = f"https://puddle.farm/api/player/{player_id}/{char_short}/history"

            async with session.get(history_url) as resp:
                if resp.status != 200:
                    continue

            history_data = await resp.json()
            matches = history_data.get("history", [])

            for match in matches[-5:]:
                match_id = f"{match['timestamp']}_{match['opponent_id']}"

                if match_id not in player_cache:
                    opponent = match["opponent_name"]
                    opponent_char = match["opponent_character"]
                    char = char_data["character"]
                    result = "win" if match["result_win"] else "loss"
                    
                    action = "vient de gagner contre" if result == "win" else "vient de perdre contre"
                    message = f"{name} ({char}) {action} {opponent} ({opponent_char})"
                    
                    await channel.send(message)
                    player_cache.append(match_id)

        self.cache[player_id] = player_cache[-20:]

intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
bot = GGSTBot(intents=intents)
bot.run(DISCORD_TOKEN)
