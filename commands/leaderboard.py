"""
Leaderboard commands with pagination
"""
import discord
from discord import app_commands
from discord.ext import commands

import utils.exceptions as bot_exceptions
from utils import verify_char_short, str_elo
from api_client import PuddleApiClient, ApiError


class LeaderboardView(discord.ui.View):
	"""Interactive pagination view for leaderboard."""
	def __init__(self, pages: list[discord.Embed], user_id: int, timeout: float = 120):
		super().__init__(timeout=timeout)
		self.pages = pages
		self.index = 0
		self.user_id = user_id

		self.prev_button: discord.ui.Button | None = None
		self.next_button: discord.ui.Button | None = None

		for child in self.children:
			if isinstance(child, discord.ui.Button):
				if child.custom_id == "lb_prev":
					self.prev_button = child
				elif child.custom_id == "lb_next":
					self.next_button = child
		self._update_button_states()

	def _update_button_states(self):
		"""Enable/disable navigation buttons based on current index."""
		if self.prev_button:
			self.prev_button.disabled = self.index <= 0
		if self.next_button:
			self.next_button.disabled = self.index >= len(self.pages) - 1

	@discord.ui.button(label="◀️", style=discord.ButtonStyle.primary, custom_id="lb_prev")
	async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button):
		"""Go to previous page."""
		self.index = max(self.index - 1, 0)
		self._update_button_states()
		await interaction.response.edit_message(embed=self.pages[self.index], view=self)

	@discord.ui.button(label="▶️", style=discord.ButtonStyle.primary, custom_id="lb_next")
	async def next(self, interaction: discord.Interaction, _button: discord.ui.Button):
		"""Go to next page."""
		self.index = min(self.index + 1, len(self.pages) - 1)
		self._update_button_states()
		await interaction.response.edit_message(embed=self.pages[self.index], view=self)

class Leaderboard(commands.Cog, name="Leaderboard"):
	"""Commands for viewing leaderboards"""

	def __init__(self, bot):
		self.bot = bot

	async def _fetch_leaderboard(self, character: str | None = None) -> list[dict]:
		"""Fetch top players (global or per character) using the API client."""
		async with PuddleApiClient() as api:
			try:
				if character:
					payload = await api.get_top_char(character)
				else:
					payload = await api.get_top()
			except ApiError:
				return []

		if not payload:
			return []
		if isinstance(payload, list):
			return payload
		if isinstance(payload, dict):
			if isinstance(payload.get("ranks"), list):
				return payload["ranks"]
			for val in payload.values():
				if isinstance(val, list):
					return val
		return []

	def _build_leaderboard_pages(self, data: list[dict],
								 character: str | None = None,
								 page_size: int = 10) -> list[discord.Embed]:
		"""Turn raw leaderboard data into a list of embeds (pages)."""
		pages: list[discord.Embed] = []
		if not data:
			embed = discord.Embed(
				title="🏆 Classement",
				description="Aucune donnée disponible.",
				color=0x0099FF
			)
			pages.append(embed)
			return pages

		total = len(data)
		title = "🏆 Classement Global" if not character else f"🏆 Classement {character}"
		for start in range(0, total, page_size):
			slice_ = data[start:start + page_size]
			lines = []

			for idx, entry in enumerate(slice_, start=start + 1):
				name = entry.get("name", "?")
				rating = str_elo(entry.get("rating"))
				char_long = entry.get("char_long")
				# Show character tag only if character filter not applied
				if not character and char_long:
					line = f"**#{idx}** {name} ({char_long}) - {rating}"
				else:
					line = f"**#{idx}** {name} - {rating}"
				lines.append(line)

			page_num = (start // page_size) + 1
			page_total = (total + page_size - 1) // page_size
			embed = discord.Embed(
				title=title,
				description="\n".join(lines) or "(vide)",
				color=0x0099FF
			)
			embed.set_footer(text=f"Page {page_num}/{page_total} • puddle.farm")
			pages.append(embed)
		return pages

	@app_commands.command(name="top", description="Show top players in the database.")
	@app_commands.describe(character="Optional: Filter by character (short code like SO, KY, etc.)")
	async def top(self, interaction: discord.Interaction, character: str | None = None):
		"""Show top players leaderboard (with pagination)."""
		await interaction.response.defer()
		try:
			char: str | None = None
			if character:
				char = verify_char_short(character)
			data = await self._fetch_leaderboard(char)
			pages = self._build_leaderboard_pages(data, char)
			view = LeaderboardView(pages, interaction.user.id)
			await interaction.followup.send(embed=pages[0], view=view)
		except bot_exceptions.CharNotFound as e:
			await interaction.followup.send(f"❌ {e}. Use ``/help characters`` to get all short codes.")
		except ApiError as exc:
			await interaction.followup.send(f"❌ Erreur API classement: {exc}")


async def setup(bot):
	"""Setup function for loading the cog"""
	await bot.add_cog(Leaderboard(bot))