"""
Base command utilities and decorators
"""
import os
from discord import app_commands, Interaction

def is_owner():
	"""Check if the command is run by the bot owner"""
	async def predicate(interaction: Interaction) -> bool:
		if interaction.user.id != int(os.getenv('BOT_OWNER_ID')):
			await interaction.response.send_message(
				"Owner-only command.",
				ephemeral=True
			)
			return False
		return True
	return app_commands.check(predicate)

# API Constants
API_BASE_URL = "https://puddle.farm/api"
API_PLAYER_URL = f"{API_BASE_URL}/player"