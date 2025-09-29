"""
Player management commands (add, remove, list players)
"""
import discord
from discord import app_commands
from discord.ext import commands
from database import Database
from i18n import t
from api_client import PuddleApiClient, ApiError


class PlayerManagement(commands.Cog, name="Player Management"):
	"""Commands for managing tracked players"""

	def __init__(self, bot):
		self.bot = bot
		self.db: Database = bot.db

	@app_commands.command(name="add_player", description="Add a player to the tracker")
	@app_commands.describe(
		player_id="The player's ID from puddle.farm",
		name="The player's display name"
	)
	async def add_player(self, interaction: discord.Interaction, player_id: str, name: str):
		"""Add a new player to track"""
		await interaction.response.defer()

		try:
			async with PuddleApiClient() as api:
				player = await api.get_player(player_id)
				if not player:
					await interaction.followup.send(
						t("players.add.not_found_by_id", player_id=player_id)
					)
					return

			self.db.add_player(player_id, name)
			await interaction.followup.send(
				t("players.add.added", name=name, player_id=player_id)
			)
		except (ApiError, ValueError) as exc:
			await interaction.followup.send(t("errors.generic", error=exc))

	@app_commands.command(name="list_players", description="Show all players being tracked")
	async def list_players(self, interaction: discord.Interaction):
		"""List all tracked players"""
		players = self.db.get_all_players()
		if not players:
			await interaction.response.send_message(t("players.list.none"), ephemeral=True)
			return

		player_list = "\n".join([
			f"• **{name}** (ID: `{player_id}`)"
			for name, player_id in players.items()
		])
		embed = discord.Embed(
			title=t("players.list.title"),
			description=player_list,
			color=0x0099FF
		)
		await interaction.response.send_message(embed=embed)

	@app_commands.command(name="remove_player", description="Remove a player from tracking")
	@app_commands.describe(name="The player's name to remove")
	async def remove_player(self, interaction: discord.Interaction, name: str):
		"""Remove a player from tracking"""
		try:
			players = self.db.get_all_players()
			if name not in players:
				await interaction.response.send_message(
					t("players.remove.not_found", name=name), ephemeral=True
				)
				return

			player_id = players[name]
			self.db.remove_player(player_id)
			await interaction.response.send_message(
				t("players.remove.removed", name=name)
			)

		except (ValueError, KeyError) as exc:
			await interaction.response.send_message(t("errors.generic", error=exc), ephemeral=True)


async def setup(bot):
	"""Setup function for loading the cog"""
	await bot.add_cog(PlayerManagement(bot))
