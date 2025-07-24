import os
import json
import asyncio
import aiohttp
import discord
from discord.ext import tasks, commands
from database import Database
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv()

# Load environment variables with fallbacks
try:
    # Try to import from config.py for backwards compatibility
    from config import DISCORD_TOKEN as CONFIG_TOKEN, CHANNEL_ID as CONFIG_CHANNEL_ID
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', CONFIG_TOKEN)
    CHANNEL_ID = int(os.getenv('CHANNEL_ID', CONFIG_CHANNEL_ID))
except ImportError:
    # Use environment variables only
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
    
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is required")
    if not CHANNEL_ID:
        raise ValueError("CHANNEL_ID environment variable is required")

# Constants
REQUEST_TIMEOUT = 10  # seconds
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', 360))  # 6 minutes default
MATCHES_TO_CHECK = 5  # number of recent matches to check per character
CACHE_SIZE = 20  # maximum number of matches to keep in cache per player

# Discord embed colors
COLOR_WIN = 0x00FF00  # Green
COLOR_LOSS = 0xFF0000  # Red

# API URLs
API_BASE_URL = "https://puddle.farm/api"
API_PLAYER_URL = f"{API_BASE_URL}/player"

class GGSTBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True
        
        super().__init__(command_prefix='!', intents=intents)
        self.db = Database()
    
    async def on_ready(self):
        print(f"Bot connecté en tant que {self.user}")
        print(f"Membre de {len(self.guilds)} serveur(s)")
        
        channel = self.get_channel(CHANNEL_ID)
        if channel:
            print(f"Canal cible: #{channel.name} dans {channel.guild.name}")
        else:
            print(f"ERREUR: Canal ID {CHANNEL_ID} introuvable!")
            return
        
        if not self.poll_matches.is_running():
            print("Démarrage de la surveillance des matches...")
            self.poll_matches.start()
    
    @commands.command(name='add_player')
    async def add_player_command(self, ctx, player_id: str, *, name: str):
        """Add a new player to track"""
        try:
            # Verify player exists in puddle.farm
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_PLAYER_URL}/{player_id}") as resp:
                    if resp.status != 200:
                        await ctx.send(f"❌ Joueur ID {player_id} introuvable sur puddle.farm")
                        return
            
            self.db.add_player(player_id, name)
            await ctx.send(f"✅ Joueur {name} (ID: {player_id}) ajouté à la surveillance!")
            
        except Exception as e:
            await ctx.send(f"❌ Erreur: {e}")
    
    @commands.command(name='list_players')
    async def list_players_command(self, ctx):
        """List all tracked players"""
        players = self.db.get_all_players()
        if not players:
            await ctx.send("Aucun joueur surveillé.")
            return
        
        player_list = "\n".join([f"• {name} (ID: {player_id})" for name, player_id in players.items()])
        embed = discord.Embed(
            title="🎮 Joueurs Surveillés",
            description=player_list,
            color=0x0099FF
        )
        await ctx.send(embed=embed)
    
    @tasks.loop(seconds=POLL_INTERVAL)
    async def poll_matches(self):
        await self.wait_until_ready()
        print("🔍 Vérification des matches en cours...")
        
        channel = self.get_channel(CHANNEL_ID)
        if channel is None:
            print(f"ERREUR: Impossible de récupérer le channel ID {CHANNEL_ID}.")
            return

        players = self.db.get_all_players()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
            for name, player_id in players.items():
                print(f"\nVérification de {name} (ID: {player_id})...")
                try:
                    await self.check_player(session, channel, name, player_id)
                except Exception as e:
                    print(f"  ❌ Erreur lors de la vérification de {name}: {e}")

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

    async def process_character_matches(self, session, channel, name, player_id, char_data, player_cache):
        """Process matches for a specific character"""
        char_short = char_data["char_short"]
        char_name = char_data["character"]
        print(f"    Vérification {char_name} ({char_short})...")
        
        char_cache = player_cache.get(char_short, [])
        
        history_data = await self.fetch_character_history(session, player_id, char_short, char_name)
        if not history_data:
            return 0
        
        matches = history_data.get("history", [])
        print(f"    {len(matches)} matches trouvés pour {char_name}")
        
        new_matches_list = []
        for match in matches[:MATCHES_TO_CHECK]:
            match_id = f"{match['timestamp']}_{match['opponent_id']}"
            
            if match_id not in char_cache:
                opponent = match["opponent_name"]
                opponent_char = match["opponent_character"]
                char = char_data["character"]
                result = "win" if match["result_win"] else "loss"
                
                new_matches_list.append({
                    'match': match,
                    'match_id': match_id,
                    'opponent': opponent,
                    'opponent_char': opponent_char,
                    'char': char,
                    'result': result
                })
                
                print(f"    📢 Nouveau match trouvé: {name} ({char}) {result} vs {opponent} ({opponent_char})")

        # Send matches in chronological order
        for match_info in reversed(new_matches_list):
            embed = self.create_match_embed(name, match_info['char'], match_info['opponent'], 
                                          match_info['opponent_char'], match_info['match'], match_info['result'])
            
            await channel.send(embed=embed)
            self.db.save_match_to_cache(player_id, char_short, match_info['match_id'])
        
        # Cleanup old cache entries
        if new_matches_list:
            self.db.cleanup_cache(player_id, char_short, CACHE_SIZE)
        
        return len(new_matches_list)

    async def check_player(self, session: aiohttp.ClientSession, channel: discord.TextChannel, name: str, player_id: str):
        """Check a player's recent matches"""
        player_data = await self.fetch_player_data(session, player_id, name)
        if not player_data:
            return
        
        print(f"  Données joueur récupérées pour {name}")
        player_cache = self.db.get_player_cache(player_id)
        
        total_new_matches = 0
        for char_data in player_data.get("ratings", []):
            new_matches = await self.process_character_matches(session, channel, name, player_id, char_data, player_cache)
            total_new_matches += new_matches
        
        if total_new_matches > 0:
            print(f"  ✅ {total_new_matches} nouveaux matches pour {name}")
    
if __name__ == "__main__":
    bot = GGSTBot()
    bot.run(DISCORD_TOKEN)
