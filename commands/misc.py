"""
Miscellaneous commands (help, fun commands, admin commands)
"""
import os
import discord
from discord import app_commands
from discord.ext import commands
from i18n import t
from api_client import PuddleApiClient
from .base_command import is_owner

RED = 0xFF0000
GREEN = 0x00FF00
class Miscellaneous(commands.Cog, name="Miscellaneous"):
	"""Miscellaneous commands"""

	def __init__(self, bot):
		self.bot = bot

	@app_commands.command(name="help", description="Show help information")
	@app_commands.describe(option="(Unused) Option for future use")
	async def help_command(self, interaction: discord.Interaction, option: str | None = None):
		"""Show help information"""
		str(option)
		# Use global default locale (from LANG env) via i18n singleton.
		embed = discord.Embed(
			title=t("help.title"),
			description=t("help.description"),
			color=0x0099FF
		)

		embed.add_field(
			name="📋 Commandes",  # keeping emoji + label static for now; could localize later
			value=t("help.commands_block"),
			inline=False
		)

		embed.add_field(
			name=t("help.info_field_name"),
			value=t("info.auto_check", interval=2),
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
				t("errors.hugo_id_missing"),
				ephemeral=True
			)
			return

		message_content = t("fun.hugo_message", user_id=hugo_id)

		embed = discord.Embed(
			title=t("fun.hugo_title"),
			description=t("fun.hugo_description"),
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


	@app_commands.command(name="health", description="Checks API health")
	async def health_check(self, interaction: discord.Interaction):
		"""Check API health using the centralized API client."""
		await interaction.response.defer(ephemeral=True)
		color = RED
		status = t("health.fail")
		async with PuddleApiClient() as api:
			if await api.health():
				color = GREEN
				status = t("health.ok")
		embed = discord.Embed(title=t("health.title"), color=color)
		embed.add_field(name=t("health.status_field"), value=status, inline=False)
		await interaction.followup.send(embed=embed)


async def setup(bot):
	"""Setup function for loading the cog"""
	await bot.add_cog(Miscellaneous(bot))