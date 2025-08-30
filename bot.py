"""
GGST Match Tracker Discord Bot / Puddle Bot

This bot tracks Guilty Gear Strive matches from puddle.farm API
and posts updates to Discord channels.
"""
import os
import logging
import sys
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

logger = logging.getLogger(__name__)

def configure_logging(level: str = "INFO") -> None:
	"""
	Configure root logging once at startup.
	level: text level (DEBUG/INFO/WARNING/ERROR)
	"""
	log_level = getattr(logging, level.upper(), logging.INFO)
	handler = logging.StreamHandler(sys.stdout)
	handler.setFormatter(logging.Formatter(
		"%(asctime)s %(levelname).1s %(name)s: %(message)s",
		datefmt="%H:%M:%S"
	))
	root = logging.getLogger()
	root.setLevel(log_level)
	root.handlers.clear()
	root.addHandler(handler)

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
			'commands.misc',
			'commands.admin'
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
			logger.info("✅ Loaded cogs:")
			for ext in loaded:
				logger.info(' - %s', ext)
		if failed:
			logger.error("❌ Failed to load:")
			for ext, err in failed.items():
				logger.error(' - %s: %s', ext, err)
		if not loaded:
			logger.error("❌ No cogs loaded; aborting command sync")
			return

		# Sync slash commands
		try:
			synced = await self.tree.sync()
			logger.info('✅ Synchronized %d slash command(s)', len(synced))
			for cmd in synced:
				logger.info('  - /%s: %s', cmd.name, cmd.description)
		except (discord.HTTPException, discord.Forbidden, discord.LoginFailure) as exc:
			logger.error('❌ Failed to sync commands: %s', exc)
			traceback.print_exc()

	async def on_ready(self):
		"""Called when the bot is ready"""
		logger.info('Bot connecté en tant que %s', self.user)
		logger.info('Membre de %d serveur(s)', len(self.guilds))

		# Show server and channel info
		for guild in self.guilds:
			logger.info('Serveur: %s (ID: %d)', guild.name, guild.id)

		# Debug: Show loaded commands
		logger.info('Commandes dans l\'arbre: %d', len(self.tree.get_commands()))
		for cmd in self.tree.get_commands():
			logger.info('  - /%s', cmd.name)

		channel = self.get_channel(CHANNEL_ID)
		if channel:
			logger.info('Canal cible: #%s dans %s', channel.name, channel.guild.name)
		else:
			logger.error('ERREUR: Canal ID %d introuvable!', CHANNEL_ID)
			return

		# Start polling task
		if not self.poll_matches.is_running():
			logger.info("Démarrage de la surveillance des matches...")
			self.poll_matches.start()

	@tasks.loop(minutes=POLL_INTERVAL)
	async def poll_matches(self):
		"""Periodic task to check for new matches"""
		await self.wait_until_ready()

		if not self.guilds:
			logger.error("ERREUR: Le bot n'est membre d'aucun serveur Discord!")
			return

		channel = self.get_channel(CHANNEL_ID)
		if channel is None:
			logger.error('ERREUR: Impossible de récupérer le channel ID %d.', CHANNEL_ID)
			return

		await self.match_tracker.poll_all_players(channel)


async def main():
	"""Main entry point"""
	configure_logging()
	bot = GGSTBot()

	try:
		await bot.start(DISCORD_TOKEN)
	except KeyboardInterrupt:
		logging.info("\n🛑 Bot arrêté par l'utilisateur")
	except (discord.LoginFailure, discord.HTTPException, ValueError) as exc:
		logging.critical("❌ Erreur fatale: %s", exc)
	finally:
		await bot.close()


if __name__ == "__main__":
	asyncio.run(main())
