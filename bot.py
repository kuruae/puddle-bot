"""
GGST Match Tracker Discord Bot / Puddle Bot

This bot tracks Guilty Gear Strive matches from puddle.farm API
and posts updates to Discord channels.
"""
import os
import asyncio
import traceback
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv

from database import Database
from match_tracker import MatchTracker

#API source: https://github.com/nemasu/puddle-farm/blob/master/api.yaml

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

if not DISCORD_TOKEN:
	raise ValueError("DISCORD_TOKEN environment variable is required")
if not CHANNEL_ID:
	raise ValueError("CHANNEL_ID environment variable is required")

# Constants
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '2'))  # 2 minutes default


class GGSTBot(commands.Bot):
	"""Main GGST Match Tracker Bot"""

	def __init__(self):
		intents = discord.Intents.default()
		intents.guilds = True
		intents.guild_messages = True
		intents.message_content = True

		super().__init__(command_prefix='!', intents=intents)

		# Initialize components
		self.db = Database()
		self.match_tracker = MatchTracker(self.db)

	async def setup_hook(self):
		"""Called when the bot is starting up"""
		# Explicit list of cog modules for clarity / controlled loading order
		cogs_to_load = [
			'commands.player_management',
			'commands.stats',
			'commands.leaderboard',
			'commands.misc'
		]

		loaded, failed = [], {}
		for ext in cogs_to_load:
			try:
				await self.load_extension(ext)
				loaded.append(ext)
			except (commands.ExtensionError, ImportError, AttributeError) as exc:
				failed[ext] = str(exc)

		# Log summary
		if loaded:
			print("✅ Loaded cogs:")
			for ext in loaded:
				print(f"  - {ext}")
		if failed:
			print("❌ Failed to load:")
			for ext, err in failed.items():
				print(f"  - {ext}: {err}")
		if not loaded:
			print("❌ No cogs loaded; aborting command sync")
			return

		# Sync slash commands
		try:
			synced = await self.tree.sync()
			print(f"✅ Synchronized {len(synced)} slash command(s)")
			for cmd in synced:
				print(f"  - /{cmd.name}: {cmd.description}")
		except (discord.HTTPException, discord.Forbidden, discord.LoginFailure) as exc:
			print(f"❌ Failed to sync commands: {exc}")
			traceback.print_exc()

	async def on_ready(self):
		"""Called when the bot is ready"""
		print(f"Bot connecté en tant que {self.user}")
		print(f"Membre de {len(self.guilds)} serveur(s)")

		# Show server and channel info
		for guild in self.guilds:
			print(f"Serveur: {guild.name} (ID: {guild.id})")

		# Debug: Show loaded commands
		print(f"Commandes dans l'arbre: {len(self.tree.get_commands())}")
		for cmd in self.tree.get_commands():
			print(f"  - /{cmd.name}")

		channel = self.get_channel(CHANNEL_ID)
		if channel:
			print(f"Canal cible: #{channel.name} dans {channel.guild.name}")
		else:
			print(f"ERREUR: Canal ID {CHANNEL_ID} introuvable!")
			return

		# Start polling task
		if not self.poll_matches.is_running():
			print("Démarrage de la surveillance des matches...")
			self.poll_matches.start()

	@tasks.loop(minutes=POLL_INTERVAL)
	async def poll_matches(self):
		"""Periodic task to check for new matches"""
		await self.wait_until_ready()

		if not self.guilds:
			print("ERREUR: Le bot n'est membre d'aucun serveur Discord!")
			return

		channel = self.get_channel(CHANNEL_ID)
		if channel is None:
			print(f"ERREUR: Impossible de récupérer le channel ID {CHANNEL_ID}.")
			return

		await self.match_tracker.poll_all_players(channel)


async def main():
	"""Main entry point"""
	bot = GGSTBot()

	try:
		await bot.start(DISCORD_TOKEN)
	except KeyboardInterrupt:
		print("\n🛑 Bot arrêté par l'utilisateur")
	except (discord.LoginFailure, discord.HTTPException, ValueError) as exc:
		print(f"❌ Erreur fatale: {exc}")
	finally:
		await bot.close()


if __name__ == "__main__":
	asyncio.run(main())
