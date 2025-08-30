"""
Player management commands (add, remove, list players)
"""
import discord
from discord import app_commands
from discord.ext import commands
from database import Database
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
						f"❌ Joueur ID `{player_id}` introuvable sur puddle.farm"
					)
					return

			self.db.add_player(player_id, name)
			await interaction.followup.send(
				f"✅ Joueur **{name}** (ID: `{player_id}`) ajouté à la surveillance!"
			)
		except (ApiError, ValueError) as exc:
			await interaction.followup.send(f"❌ Erreur: {exc}")

	@app_commands.command(name="list_players", description="Show all players being tracked")
	async def list_players(self, interaction: discord.Interaction):
		"""List all tracked players"""
		players = self.db.get_all_players()
		if not players:
			await interaction.response.send_message("Aucun joueur surveillé.", ephemeral=True)
			return

		player_list = "\n".join([
			f"• **{name}** (ID: `{player_id}`)"
			for name, player_id in players.items()
		])
		embed = discord.Embed(
			title="🎮 Joueurs Surveillés",
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
					f"❌ Joueur **{name}** non trouvé dans la liste.", ephemeral=True
				)
				return

			player_id = players[name]
			self.db.remove_player(player_id)
			await interaction.response.send_message(
				f"✅ Joueur **{name}** retiré de la surveillance!"
			)

		except (ValueError, KeyError) as exc:
			await interaction.response.send_message(f"❌ Erreur: {exc}", ephemeral=True)


async def setup(bot):
	"""Setup function for loading the cog"""
	await bot.add_cog(PlayerManagement(bot))
