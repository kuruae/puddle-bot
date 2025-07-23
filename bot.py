import json
import aiohttp
import discord
from discord.ext import tasks
from config import DISCORD_TOKEN, CHANNEL_ID, PLAYER_IDS


# API ressources: https://github.com/nemasu/puddle-farm/blob/master/api.yaml

CACHE_FILE = "cache.json"
REQUEST_TIMEOUT = 10  # seconds
POLL_INTERVAL = 2  # minutes
MATCHES_TO_CHECK = 5  # number of recent matches to check per character
CACHE_SIZE = 100  # maximum number of matches to keep in cache per player

# Discord embed colors
COLOR_WIN = 0x00FF00  # Green
COLOR_LOSS = 0xFF0000  # Red

# API URLs
API_BASE_URL = "https://puddle.farm/api"
API_PLAYER_URL = f"{API_BASE_URL}/player"

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
        
        # Show server and channel info
        for guild in self.guilds:
            print(f"Serveur: {guild.name} (ID: {guild.id})")
        
        channel = self.get_channel(CHANNEL_ID)
        if channel:
            print(f"Canal cible: #{channel.name} dans {channel.guild.name}")
        else:
            print(f"ERREUR: Canal ID {CHANNEL_ID} introuvable!")
            return
        
        # Démarrer la tâche maintenant que le bot est prêt
        if not self.poll_matches.is_running():
            print("Démarrage de la surveillance des matches...")
            self.poll_matches.start()

    @tasks.loop(minutes=POLL_INTERVAL)
    async def poll_matches(self):
        await self.wait_until_ready()
        print("🔍 Vérification des matches en cours...")
        
        if not self.guilds:
            print("ERREUR: Le bot n'est membre d'aucun serveur Discord!")
            return
        
        channel = self.get_channel(CHANNEL_ID)
        if channel is None:
            print(f"ERREUR: Impossible de récupérer le channel ID {CHANNEL_ID}.")
            return

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
            for name, player_id in PLAYER_IDS.items():
                print(f"\nVérification de {name} (ID: {player_id})...")
                try:
                    await self.check_player(session, channel, name, player_id)
                except Exception as e:
                    print(f"  ❌ Erreur lors de la vérification de {name}: {e}")

        print("\n💾 Sauvegarde du cache...")
        self.save_cache()
        print("✅ Cycle de vérification terminé\n")

    async def fetch_player_data(self, session: aiohttp.ClientSession, player_id: str, name: str):
        """Fetch player data from puddle.farm API"""
        player_url = f"{API_PLAYER_URL}/{player_id}"
        print(f"  Récupération des infos joueur: {player_url}")
        
        async with session.get(player_url) as resp:
            if resp.status != 200:
                print(f"  ❌ Erreur API pour {name}: {resp.status}")
                return None
            return await resp.json()

    async def fetch_character_history(self, session: aiohttp.ClientSession, player_id: str, char_short: str, char_name: str):
        """Fetch match history for a specific character"""
        history_url = f"{API_PLAYER_URL}/{player_id}/{char_short}/history"
        print(f"    Récupération historique: {history_url}")
        
        async with session.get(history_url) as resp:
            if resp.status != 200:
                print(f"    ⚠️  Pas d'historique pour {char_name}: {resp.status}")
                return None
            return await resp.json()

    def create_match_embed(self, name: str, char: str, opponent: str, opponent_char: str, match: dict, result: str):
        """Create a Discord embed for a match result"""
        if result == "win":
            embed = discord.Embed(
                title="🏆 Victoire!",
                description=f"**{name}** ({char}) vient de gagner contre **{opponent}** ({opponent_char})",
                color=COLOR_WIN
            )
        else:
            embed = discord.Embed(
                title="💀 Défaite",
                description=f"**{name}** ({char}) vient de perdre contre **{opponent}** ({opponent_char})",
                color=COLOR_LOSS
            )

        # additional match info
        if 'floor' in match:
            embed.add_field(name="Étage", value=match['floor'], inline=True)
        if 'own_rating_value' in match:
            embed.add_field(name="Rating", value=f"{match['own_rating_value']:.0f}", inline=True)
        
        embed.set_footer(text=f"puddle.farm • {match['timestamp']}")
        return embed

    async def process_character_matches(self, session: aiohttp.ClientSession, channel: discord.TextChannel, 
                                      name: str, player_id: str, char_data: dict, player_cache: list):
        """Process matches for a specific character"""
        char_short = char_data["char_short"]
        char_name = char_data["character"]
        print(f"    Vérification {char_name} ({char_short})...")
        
        # Fetch match history
        history_data = await self.fetch_character_history(session, player_id, char_short, char_name)
        if not history_data:
            return 0
        
        matches = history_data.get("history", [])
        print(f"    {len(matches)} matches trouvés pour {char_name}")
        
        new_matches = 0
        for match in matches[-MATCHES_TO_CHECK:]:  # Check last N matches
            match_id = f"{match['timestamp']}_{match['opponent_id']}"
            
            if match_id not in player_cache:
                # Extract match info
                opponent = match["opponent_name"]
                opponent_char = match["opponent_character"]
                char = char_data["character"]
                result = "win" if match["result_win"] else "loss"
                
                # Create and send embed
                embed = self.create_match_embed(name, char, opponent, opponent_char, match, result)
                
                print(f"    📢 Nouveau match: {name} ({char}) {result} vs {opponent} ({opponent_char})")
                await channel.send(embed=embed)
                player_cache.append(match_id)
                new_matches += 1
        
        if new_matches == 0:
            print(f"    ✓ Aucun nouveau match pour {char_name}")
        
        return new_matches

    async def check_player(self, session: aiohttp.ClientSession, channel: discord.TextChannel, name: str, player_id: str):
        """Main function to check a player's recent matches"""
        # Fetch player data
        player_data = await self.fetch_player_data(session, player_id, name)
        if not player_data:
            return
        
        print(f"  Données joueur récupérées pour {name}")
        player_cache = self.cache.setdefault(player_id, [])
        
        # Process each character
        total_new_matches = 0
        for char_data in player_data.get("ratings", []):
            new_matches = await self.process_character_matches(session, channel, name, player_id, char_data, player_cache)
            total_new_matches += new_matches
        
        # Clean up cache (keep last N matches)
        self.cache[player_id] = player_cache[-CACHE_SIZE:]
        
        if total_new_matches > 0:
            print(f"  ✅ {total_new_matches} nouveaux matches pour {name}")
        else:
            print(f"  ✓ Aucun nouveau match pour {name}")

intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
bot = GGSTBot(intents=intents)
bot.run(DISCORD_TOKEN)
