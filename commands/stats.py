"""Player statistics commands using the central PuddleApiClient."""
import logging
import discord
from discord import app_commands
from discord.ext import commands
from database import Database
from utils import calculate_rank, str_elo, to_int, debug_logging_decorator
from api_client import PuddleApiClient, ApiError

MIN_MATCHES = 1
NUMBER_OF_CHARACTERS = 3  # Number of characters to display in stats

log = logging.getLogger(__name__)

class PlayerStats(commands.Cog, name="Player Stats"):
	"""Commands for viewing player statistics"""

	def __init__(self, bot):
		self.bot = bot
		self.db: Database = bot.db

	@debug_logging_decorator
	def _format_character_info(self, char_data: dict) -> str:
		"""Helper function to format a single character's information"""
		char_name = char_data["character"]
		rating_int = to_int(char_data.get("rating", 0)) or 0
		rating_display = str_elo(rating_int)
		log.debug("rating int = %s\nrating display = %s", rating_int, rating_display)
		match_count = char_data.get("match_count", 0)

		info_lines = [f"**{char_name}**: {rating_display} - {calculate_rank(rating_int)} ({match_count} matches)"]

		if char_data.get("top_char", 0) > 0:
			info_lines.append(f"┗ Rang: #{char_data['top_char']}")

		top_defeated = char_data.get("top_defeated")
		if isinstance(top_defeated, dict) and top_defeated.get("value", 0) > 0:
			opp_rate_int = to_int(top_defeated.get("value", 0))
			opp_rate_display = str_elo(opp_rate_int)
			log.debug("opp_rate int = %s\nopp_rate display = %s", opp_rate_int, opp_rate_display)
			# opp_rank = calculate_rank(opp_rate_int)
			# not using it for now, I feel like it would become too cluttered
			info_lines.append(
				f"┗ Meilleure win: **{top_defeated.get('name','?')}** "
				f"({top_defeated.get('char_short','?')}) - {opp_rate_display}"
			)

		return "\n".join(info_lines)

	def _resolve_player_identifier(self, name_or_id: str) -> tuple[str, str | None]:
		"""Return (player_id, player_name_if_tracked)"""
		players = self.db.get_all_players()

		if name_or_id in players:
			return players[name_or_id], name_or_id

		return name_or_id, None

	async def _fetch_player_data(self, player_id: str) -> dict | None:
		"""Fetch player data via API client. Returns None if not found."""
		async with PuddleApiClient() as api:
			try:
				return await api.get_player(player_id)
			except ApiError:
				return None

	def _filter_and_sort_characters(self, player_data: dict, min_matches: int = MIN_MATCHES) -> list[dict]:
		"""Return characters with at least min_matches sorted desc by rating."""
		ratings = player_data.get("ratings", []) or []
		filtered = [c for c in ratings if c.get("match_count", 0) >= min_matches]
		return sorted(filtered, key=lambda x: x.get("rating", 0), reverse=True)

	def _build_stats_embed(self, player_name: str, player_data: dict) -> discord.Embed:
		"""Construct the statistics embed from player data."""
		embed = discord.Embed(
			title=f"🤓☝️ Statistiques de {player_name}",
			color=0x0099FF
		)

		# Global ranking
		if player_data.get("top_global", 0) > 0:
			embed.add_field(
				name="🏆 Classement Global",
				value=f"#{player_data['top_global']}",
				inline=False
			)

		sorted_chars = self._filter_and_sort_characters(player_data)

		if sorted_chars:
			for i, char in enumerate(sorted_chars[:NUMBER_OF_CHARACTERS], 1):
				embed.add_field(
					name=f"Personnage #{i}",
					value=self._format_character_info(char),
					inline=False
				)
		else:
			embed.add_field(
				name="Personnages",
				value=f"Aucun personnage avec {MIN_MATCHES}+ matches",
				inline=False
			)

		embed.set_footer(text="puddle.farm")
		return embed

	@app_commands.command(name="stats", description="Show statistics for a player")
	@app_commands.describe(name_or_id="The player's name (if tracked) or puddle.farm ID")
	async def stats(self, interaction: discord.Interaction, name_or_id: str):
		"""Show player statistics"""
		await interaction.response.defer()

		try:
			# Resolve identifier (may give us tracked name)
			player_id, tracked_name = self._resolve_player_identifier(name_or_id)

			# Fetch data
			player_data = await self._fetch_player_data(player_id)
			if not player_data:
				await interaction.followup.send(
					f"❌ Joueur `{name_or_id}` introuvable sur puddle.farm"
				)
				return

			# Use tracked name, else API name, else original input
			player_name = tracked_name or player_data.get("name", name_or_id)

			embed = self._build_stats_embed(player_name, player_data)
			await interaction.followup.send(embed=embed)

		except (ApiError, ValueError, KeyError) as exc:
			await interaction.followup.send(f"❌ Erreur: {exc}")


	async def get_popularity_request(self) -> dict | None:
		"""Fetch character popularity data via API client."""
		async with PuddleApiClient() as api:
			try:
				return await api.get_popularity()
			except ApiError:
				return None

	@app_commands.command(name="distribution", description="Display character distribution"
							" across the past month")
	async def distribution(self, interaction: discord.Interaction):
		"""Display character distribution across the past month"""
		await interaction.response.defer()
		try:
			data = await self.get_popularity_request()
			if not data:
				await interaction.followup.send("❌ Impossible de récupérer les données.")
				return

			per_player_list = data.get("per_player", [])
			total = data.get("per_player_total")

			per_player_list = sorted(per_player_list, key=lambda d: d.get("value", 0), reverse=True)

			lines: list[str] = []
			for _rank, entry in enumerate(per_player_list, 1):
				name = entry.get("name", "Inconnu")
				count = entry.get("value", 0)
				pct = (count / total * 100) if total else 0

				lines.append(f"**{name}** — {count} joueurs ({pct:.2f}%)")

			description = "\n".join(lines)

			embed = discord.Embed(
				title="Distribution des Personnages (Players)",
				description=description,
				color=0x0099FF
			)
			embed.set_footer(
				text=f"Total joueurs: {total} • puddle.farm • {data.get('last_update', '?')}"
			)
			await interaction.followup.send(embed=embed)
		except (ApiError, ValueError, KeyError) as e:
			await interaction.followup.send(f"❌ Erreur interne distribution: {e}")


async def setup(bot):
	"""Setup function for loading the cog"""
	await bot.add_cog(PlayerStats(bot))
