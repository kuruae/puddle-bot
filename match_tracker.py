"""Match tracking and processing logic.

Now that a centralized `PuddleApiClient` exists we keep this module focused
purely on orchestration (deciding which players / characters to poll and
emitting Discord embeds) rather than HTTP details. Former thin wrappers over
client methods have been inlined to reduce indirection.
"""
from datetime import datetime, timedelta
import logging
import aiohttp
import discord

from database import Database
from api_client import PuddleApiClient, RetryPolicy, SimpleRateLimiter, ApiError
from utils import calculate_rank, str_elo, to_int

# Configuration constants
REQUEST_TIMEOUT = 10               # seconds total per HTTP request
MATCHES_TO_CHECK = 5               # how many recent matches to inspect per character
CACHE_SIZE = 20                    # max cached match ids per player/character
TIMEZONE_OFFSET_HOURS = 2          # API timestamp -> local display offset (API is UTC)

# Discord embed colors
COLOR_WIN = 0x00FF00  # Green
COLOR_LOSS = 0xFF0000  # Red

# API URLs
API_BASE_URL = "https://puddle.farm/api"
API_PLAYER_URL = f"{API_BASE_URL}/player"


logger = logging.getLogger(__name__)


class MatchTracker:
	"""Poll tracked players and announce new matches.

	Responsibilities intentionally narrow:
	- iterate tracked players
	- fetch player + character history via `PuddleApiClient`
	- detect unseen matches vs cache
	- emit Discord embeds & update cache

	HTTP details (retries / rate limiting / timeouts) are delegated to the API client.
	"""

	def __init__(self, db: Database):
		self.db = db
		# Reusable API client components; a session is created each poll cycle.
		self._retry_policy = RetryPolicy()
		self._rate_limiter = SimpleRateLimiter(capacity=12, interval=1.0)  # ~12 req/sec soft cap

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

	async def process_character_matches(self, api: PuddleApiClient,
										channel: discord.TextChannel, name: str,
										player_id: str, char_data: dict,
										player_cache: dict) -> int:
		"""Process matches for a specific character"""
		char_short = char_data.get("char_short")
		char_name = char_data.get("character")
		if not char_short or not char_name:
			return 0
		logger.debug("Verif personnage %s (%s) pour %s", char_name, char_short, name)

		char_cache = player_cache.get(char_short, [])

		try:
			history_data = await api.get_player_history(player_id, char_short)
		except (aiohttp.ClientError, ApiError) as e:
			logger.warning("Historique indisponible pour %s (%s): %s", char_name, char_short, e)
			return 0
		if not history_data:
			return 0

		matches = history_data.get("history", [])
		logger.debug("%d matches trouvés pour %s", len(matches), char_name)

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

			logger.info("Nouveau match: %s (%s) %s vs %s (%s)", name, char, result, opponent, opponent_char)

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
				logger.error("Envoi échoué match %s: %s", match_info.get('match_id'), e)
				continue

		if new_matches_list:
			self.db.cleanup_cache(player_id, char_short, CACHE_SIZE)

		return len(new_matches_list)

	async def check_player(self, api: PuddleApiClient, channel: discord.TextChannel, name: str, player_id: str) -> None:
		"""Check a player's recent matches"""
		try:
			player_data = await api.get_player(player_id)
		except (aiohttp.ClientError, ApiError) as e:
			logger.error("Profil joueur indisponible %s (%s): %s", name, player_id, e)
			return
		if not player_data:
			logger.warning("Aucune donnée joueur pour %s (%s)", name, player_id)
			return

		logger.debug("Profil récupéré pour %s", name)
		player_cache = self.db.get_player_cache(player_id)

		total_new_matches = 0
		for char_data in player_data.get("ratings", []):
			new_matches = await self.process_character_matches(
				api, channel, name, player_id, char_data, player_cache
			)
			total_new_matches += new_matches

		if total_new_matches > 0:
			logger.info("%d nouveaux matches pour %s", total_new_matches, name)

	async def poll_all_players(self, channel: discord.TextChannel) -> None:
		"""Poll all tracked players for new matches"""
		logger.info("Début cycle de vérification des matches")

		players = self.db.get_all_players()
		# Create a client per poll cycle; internal session reused across requests then closed.
		async with PuddleApiClient(
			base_url=API_BASE_URL,
			timeout=REQUEST_TIMEOUT,
			retry_policy=self._retry_policy,
			rate_limiter=self._rate_limiter,
		) as api:
			for name, player_id in players.items():
				logger.info("Vérification de %s (%s)", name, player_id)
				try:
					await self.check_player(api, channel, name, player_id)
				except (aiohttp.ClientError, aiohttp.ServerTimeoutError, ApiError) as exc:
					logger.error("Erreur réseau/API %s: %s", name, exc)
				except discord.DiscordException as exc:
					logger.error("Erreur Discord %s: %s", name, exc)
				except (KeyError, ValueError, TypeError) as exc:
					logger.exception("Erreur de traitement %s: %s", name, exc)

		logger.info("Cycle de vérification terminé")
