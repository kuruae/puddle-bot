"""
Miscellaneous commands (help, fun commands, admin commands)
"""
import os
import discord
from discord import app_commands
from discord.ext import commands
from .base_command import is_owner


class Miscellaneous(commands.Cog, name="Miscellaneous"):
	"""Miscellaneous commands"""

	def __init__(self, bot):
		self.bot = bot

	@app_commands.command(name="help", description="Show help information")
	@app_commands.describe(option="(Unused) Option for future use")
	async def help_command(self, interaction: discord.Interaction, option: str | None = None):
		"""Show help information"""
		str(option)
		embed = discord.Embed(
			title="Puddle Bot",
			description="Bot qui surveille les matches GGST sur puddle.farm",
			color=0x0099FF
		)

		embed.add_field(
			name="📋 Commandes",
			value=(
				"`/add_player <id> <nom>` - Ajouter un joueur\n"
				"`/list_players` - Liste des joueurs surveillés\n"
				"`/remove_player <nom>` - Retirer un joueur\n"
				"`/stats <nom>/<id>` - Statistiques d'un joueur\n"
				"`/top [personnage]` - Classement des joueurs\n"
				"`/help` - Afficher cette aide"
			),
			inline=False
		)

		embed.add_field(
			name="Informations",
			value="Le bot vérifie automatiquement les nouveaux matches toutes les 2 minutes.",
			inline=False
		)

		embed.set_footer(text="Source: github.com/kuruae/puddle-bot")
		await interaction.response.send_message(embed=embed)

	@app_commands.command(name="hugo", description="Sends millia oki disk to hugo")
	@is_owner()
	async def hugo_command(self, interaction: discord.Interaction):
		"""Sends millia oki disk to hugo"""
		hugo_id = os.getenv('HUGO_USER_ID')

		if not hugo_id:
			await interaction.response.send_message(
				"❌ HUGO_USER_ID n'est pas configuré.", 
				ephemeral=True
			)
			return

		message_content = f"<@{hugo_id}> sale loser"

		embed = discord.Embed(
			title="🥏 Millia Oki Disk",
			description="bloques ça pour voir",
			color=0xFF69B4
		)

		embed.set_image(url=(
			"https://media.discordapp.net/attachments/1239571704812933218/"
			"1399147784065650748/60d0c8465ff6c.png?ex=6889ebaa&is=68889a2a&"
			"hm=9d811f7f7f9c755740b5da25bff8cc4adc0d6d35b4c8211d829ee4e04b33aa57&="
			"&format=webp&quality=lossless&width=1876&height=1604"
		))

		await interaction.response.send_message(
			content=message_content,
			embed=embed
		)

	@app_commands.command(name="sync_guild", description="Sync commands to this server only")
	@is_owner()
	async def sync_guild_only(self, interaction: discord.Interaction):
		"""Sync commands to current guild only (faster for testing)"""
		await interaction.response.defer(ephemeral=True)

		try:
			synced = await self.bot.tree.sync(guild=interaction.guild)
			await interaction.followup.send(
				f"✅ Synced {len(synced)} commands to **{interaction.guild.name}**"
			)
		except discord.app_commands.errors.CommandSyncFailure as e:
			await interaction.followup.send(f"❌ Sync failed: {str(e)}")
		except discord.HTTPException as e:
			await interaction.followup.send(f"❌ Discord HTTP error: {str(e)}")


async def setup(bot):
	"""Setup function for loading the cog"""
	await bot.add_cog(Miscellaneous(bot))