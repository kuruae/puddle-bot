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

    @tasks.loop(minutes=3)
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

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for name, player_id in PLAYER_IDS.items():
                print(f"\nVérification de {name} (ID: {player_id})...")
                try:
                    await self.check_player(session, channel, name, player_id)
                except Exception as e:
                    print(f"  ❌ Erreur lors de la vérification de {name}: {e}")

        print("\n💾 Sauvegarde du cache...")
        self.save_cache()
        print("✅ Cycle de vérification terminé\n")

    async def check_player(self, session: aiohttp.ClientSession, channel: discord.TextChannel, name: str, player_id: str):
        player_url = f"https://puddle.farm/api/player/{player_id}"
        print(f"  Récupération des infos joueur: {player_url}")
        
        async with session.get(player_url) as resp:
            if resp.status != 200:
                print(f"  ❌ Erreur API pour {name}: {resp.status}")
                return
            player_data = await resp.json()

        print(f"  Données joueur récupérées pour {name}")
        player_cache = self.cache.setdefault(player_id, [])

        for char_data in player_data.get("ratings", []):
            char_short = char_data["char_short"]
            char_name = char_data["character"]
            print(f"    Vérification {char_name} ({char_short})...")
            
            history_url = f"https://puddle.farm/api/player/{player_id}/{char_short}/history"
            print(f"    Récupération historique: {history_url}")
            async with session.get(history_url) as resp:
                if resp.status != 200:
                    print(f"    ⚠️  Pas d'historique pour {char_name}: {resp.status}")
                    continue
                
                history_data = await resp.json()
            matches = history_data.get("history", [])
            print(f"    {len(matches)} matches trouvés pour {char_name}")

            new_matches = 0
            for match in matches[-5:]:
                match_id = f"{match['timestamp']}_{match['opponent_id']}"

                if match_id not in player_cache:
                    opponent = match["opponent_name"]
                    opponent_char = match["opponent_character"]
                    char = char_data["character"]
                    result = "win" if match["result_win"] else "loss"
                    
                    if result == "win":
                        embed = discord.Embed(
                            title="🏆 Victoire!",
                            description=f"**{name}** ({char}) vient de gagner contre **{opponent}** ({opponent_char})",
                            color=0x00FF00 # vert
                        )
                    else:
                        embed = discord.Embed(
                            title="💀 Défaite",
                            description=f"**{name}** ({char}) vient de perdre contre **{opponent}** ({opponent_char})",
                            color=0xFF0000  # rouge
                        )

                    if 'floor' in match:
                        embed.add_field(name="Étage", value=match['floor'], inline=True)
                    if 'own_rating_value' in match:
                        embed.add_field(name="Rating", value=f"{match['own_rating_value']:.0f}", inline=True)
                    
                    embed.set_footer(text=f"puddle.farm • {match['timestamp']}")
                    
                    print(f"    📢 Nouveau match: {name} ({char}) {result} vs {opponent} ({opponent_char})")
                    await channel.send(embed=embed)
                    player_cache.append(match_id)
                    new_matches += 1
            
            if new_matches == 0:
                print(f"    ✓ Aucun nouveau match pour {char_name}")

        self.cache[player_id] = player_cache[-100:]

intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
bot = GGSTBot(intents=intents)
bot.run(DISCORD_TOKEN)
