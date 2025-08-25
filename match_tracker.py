"""
Match tracking and processing logic for puddle bot
"""
from datetime import datetime, timedelta
import json
import aiohttp
import discord

from database import Database
from utils.helpers import calculate_rank, str_elo, to_int

# Configuration constants
REQUEST_TIMEOUT = 10  # seconds
MATCHES_TO_CHECK = 5  # number of recent matches to check per character
CACHE_SIZE = 20  # maximum number of matches to keep in cache per player
TIMEZONE_OFFSET_HOURS = 2  # API timestamp -> local display offset (API is UTC)

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
								player_id: str, name: str) -> dict | None:
		"""Fetch player data from puddle.farm API"""
		player_url = f"{API_PLAYER_URL}/{player_id}"
		print(f"  Récupération des infos joueur: {player_url}")
		try:
			async with session.get(player_url) as resp:
				if resp.status != 200:
					print(f"  ❌ Erreur API pour {name}: {resp.status}")
					return None
				try:
					return await resp.json()
				except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
					print(f"  ❌ JSON invalide pour {name}: {e}")
					return None
		except aiohttp.ClientError as e:
			print(f"  ❌ Requête échouée pour {name}: {e}")
			return None

	async def fetch_character_history(self, session: aiohttp.ClientSession,
									  player_id: str, char_short: str,
									  char_name: str) -> dict | None:
		"""Fetch match history for a specific character"""
		history_url = f"{API_PLAYER_URL}/{player_id}/{char_short}/history"
		print(f"\tRécupération historique: {history_url}")
		try:
			async with session.get(history_url) as resp:
				if resp.status != 200:
					print(f"\t⚠️  Pas d'historique pour {char_name}: {resp.status}")
					return None
				try:
					return await resp.json()
				except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
					print(f"\t⚠️  JSON invalide pour {char_name}: {e}")
					return None
		except aiohttp.ClientError as e:
			print(f"\t⚠️  Requête échouée pour {char_name}: {e}")
			return None

	def create_match_embed(self, name: str, char: str, opponent: str,
						   opponent_char: str, match: dict, result: str) -> discord.Embed:
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

		own_val = to_int(match.get("own_rating_value"))
		opp_val = to_int(match.get("opponent_rating_value"))

		if own_val is not None:
			own_display = str_elo(own_val)
			own_rank = calculate_rank(own_val)
			embed.add_field(
				name=name,
				value=f"Rating: {own_display}\nRang: {own_rank}",
				inline=False
			)

		if opp_val is not None:
			opp_display = str_elo(opp_val)
			opp_rank = calculate_rank(opp_val)
			embed.add_field(
				name=opponent,
				value=f"Rating: {opp_display}\nRang: {opp_rank}",
				inline=False
			)

		try:
			api_time = datetime.strptime(match['timestamp'], '%Y-%m-%d %H:%M:%S')
			local_time = api_time + timedelta(hours=TIMEZONE_OFFSET_HOURS)
			formatted_time = local_time.strftime('%Y-%m-%d %H:%M:%S')
		except (ValueError, KeyError, TypeError):
			formatted_time = match.get('timestamp', '?')

		embed.set_footer(text=f"puddle.farm • {formatted_time}")
		return embed

	async def process_character_matches(self, session: aiohttp.ClientSession,
										channel: discord.TextChannel, name: str,
										player_id: str, char_data: dict,
										player_cache: dict) -> int:
		"""Process matches for a specific character"""
		char_short = char_data.get("char_short")
		char_name = char_data.get("character")
		if not char_short or not char_name:
			return 0
		print(f"\tVérification {char_name} ({char_short})...")

		char_cache = player_cache.get(char_short, [])

		history_data = await self.fetch_character_history(session, player_id, char_short, char_name)
		if not history_data:
			return 0

		matches = history_data.get("history", [])
		print(f"\t{len(matches)} matches trouvés pour {char_name}")

		new_matches_list: list[dict] = []
		for match in matches[:MATCHES_TO_CHECK]:
			try:
				match_id = f"{match['timestamp']}_{match['opponent_id']}"
			except KeyError:
				continue
			if match_id in char_cache:
				continue

			opponent = match.get("opponent_name", "?")
			opponent_char = match.get("opponent_character", "?")
			char = char_name
			result = "win" if match.get("result_win") else "loss"

			new_matches_list.append({
				'match': match,
				'match_id': match_id,
				'opponent': opponent,
				'opponent_char': opponent_char,
				'char': char,
				'result': result
			})

			print(f"\t📢 Nouveau match trouvé: {name} ({char}) {result} vs {opponent} ({opponent_char})")

		# Send matches in chronological order (oldest first)
		for match_info in reversed(new_matches_list):
			try:
				embed = self.create_match_embed(
					name, match_info['char'], match_info['opponent'],
					match_info['opponent_char'], match_info['match'], match_info['result']
				)
				await channel.send(embed=embed)
				self.db.save_match_to_cache(player_id, char_short, match_info['match_id'])
			except (discord.HTTPException, discord.Forbidden, discord.NotFound) as e:
				print(f"\t❌ Envoi échoué pour match {match_info.get('match_id')}: {e}")
				continue

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
					print(f"  ❌ Erreur réseau pour {name}: {exc}")
				except discord.DiscordException as exc:
					print(f"  ❌ Erreur Discord pour {name}: {exc}")
				except (KeyError, ValueError, TypeError) as exc:
					print(f"  ❌ Erreur de traitement pour {name}: {exc}")

		print("✅ Cycle de vérification terminé\n")
