"""
Match tracking and processing logic for puddle bot
"""
from typing import Optional
import aiohttp
import discord

from database import Database

# Configuration constants
REQUEST_TIMEOUT = 10  # seconds
MATCHES_TO_CHECK = 5  # number of recent matches to check per character
CACHE_SIZE = 20  # maximum number of matches to keep in cache per player

# Discord embed colors
COLOR_WIN = 0x00FF00  # Green
COLOR_LOSS = 0xFF0000  # Red

# API URLs
API_BASE_URL = "https://puddle.farm/api"
API_PLAYER_URL = f"{API_BASE_URL}/player"


class MatchTracker:
    """Handles match tracking and processing"""

    def __init__(self, db: Database):
        self.db = db

    async def fetch_player_data(self, session: aiohttp.ClientSession,
                                player_id: str, name: str) -> Optional[dict]:
        """Fetch player data from puddle.farm API"""
        player_url = f"{API_PLAYER_URL}/{player_id}"
        print(f"  Récupération des infos joueur: {player_url}")

        async with session.get(player_url) as resp:
            if resp.status != 200:
                print(f"  ❌ Erreur API pour {name}: {resp.status}")
                return None
            return await resp.json()

    async def fetch_character_history(self, session: aiohttp.ClientSession,
                                      player_id: str, char_short: str,
                                      char_name: str) -> Optional[dict]:
        """Fetch match history for a specific character"""
        history_url = f"{API_PLAYER_URL}/{player_id}/{char_short}/history"
        print(f"    Récupération historique: {history_url}")

        async with session.get(history_url) as resp:
            if resp.status != 200:
                print(f"    ⚠️  Pas d'historique pour {char_name}: {resp.status}")
                return None
            return await resp.json()

    def create_match_embed(self, name: str, char: str, opponent: str,
                          opponent_char: str, match: dict, result: str) -> discord.Embed:
        """Create a Discord embed for a match result"""
        if result == "win":
            embed = discord.Embed(
                title="🏆 Victoire!",
                description=(
                    f"**{name}** ({char}) vient de gagner contre "
                    f"**{opponent}** ({opponent_char})"
                ),
                color=COLOR_WIN
            )
        else:
            embed = discord.Embed(
                title="💀 Défaite",
                description=(
                    f"**{name}** ({char}) vient de perdre contre "
                    f"**{opponent}** ({opponent_char})"
                ),
                color=COLOR_LOSS
            )

        # Add additional match info
        if 'floor' in match:
            embed.add_field(name="Étage", value=match['floor'], inline=True)
        if 'own_rating_value' in match:
            embed.add_field(
                name="Rating", value=f"{match['own_rating_value']:.0f}", inline=True
            )

        embed.set_footer(text=f"puddle.farm • {match['timestamp']}")
        return embed

    async def process_character_matches(self, session: aiohttp.ClientSession,
                                      channel: discord.TextChannel, name: str,
                                      player_id: str, char_data: dict,
                                      player_cache: dict) -> int:
        """Process matches for a specific character"""
        char_short = char_data["char_short"]
        char_name = char_data["character"]
        print(f"    Vérification {char_name} ({char_short})...")

        char_cache = player_cache.get(char_short, [])

        history_data = await self.fetch_character_history(
            session, player_id, char_short, char_name
        )
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

                print(
                    f"    📢 Nouveau match trouvé: {name} ({char}) {result} "
                    f"vs {opponent} ({opponent_char})"
                )

        # Send matches in chronological order (oldest first)
        for match_info in reversed(new_matches_list):
            embed = self.create_match_embed(
                name, match_info['char'], match_info['opponent'],
                match_info['opponent_char'], match_info['match'], match_info['result']
            )

            await channel.send(embed=embed)
            self.db.save_match_to_cache(player_id, char_short, match_info['match_id'])

        # Cleanup old cache entries
        if new_matches_list:
            self.db.cleanup_cache(player_id, char_short, CACHE_SIZE)

        return len(new_matches_list)

    async def check_player(self, session: aiohttp.ClientSession,
                          channel: discord.TextChannel, name: str, player_id: str) -> None:
        """Check a player's recent matches"""
        player_data = await self.fetch_player_data(session, player_id, name)
        if not player_data:
            return

        print(f"  Données joueur récupérées pour {name}")
        player_cache = self.db.get_player_cache(player_id)

        total_new_matches = 0
        for char_data in player_data.get("ratings", []):
            new_matches = await self.process_character_matches(
                session, channel, name, player_id, char_data, player_cache
            )
            total_new_matches += new_matches

        if total_new_matches > 0:
            print(f"  ✅ {total_new_matches} nouveaux matches pour {name}")

    async def poll_all_players(self, channel: discord.TextChannel) -> None:
        """Poll all tracked players for new matches"""
        print("🔍 Vérification des matches en cours...")

        players = self.db.get_all_players()
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for name, player_id in players.items():
                print(f"\nVérification de {name} (ID: {player_id})...")
                try:
                    await self.check_player(session, channel, name, player_id)
                except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as exc:
                    print(f"  ❌ Erreur lors de la vérification de {name}: {exc}")

        print("✅ Cycle de vérification terminé\n")
