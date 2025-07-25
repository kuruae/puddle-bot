import os
import asyncio
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv

from database import Database
from match_tracker import MatchTracker

#API source: https://github.com/nemasu/puddle-farm/blob/master/api.yaml

# Load environment variables from .env file for local development
load_dotenv()

# Load environment variables with fallbacks
try:
    # Try to import from config.py for backwards compatibility
    from config import DISCORD_TOKEN as CONFIG_TOKEN, CHANNEL_ID as CONFIG_CHANNEL_ID
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', CONFIG_TOKEN)
    CHANNEL_ID = int(os.getenv('CHANNEL_ID', CONFIG_CHANNEL_ID))
except ImportError:
    # Use environment variables only
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
    
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is required")
    if not CHANNEL_ID:
        raise ValueError("CHANNEL_ID environment variable is required")

# Constants
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', 2))  # 2 minutes default


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
        # Load command cogs
        await self.load_extension('commands')  # the parameter matches the filename

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            print(f"✅ Synchronized {len(synced)} slash command(s)")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Called when the bot is ready"""
        print(f"Bot connecté en tant que {self.user}")
        print(f"Membre de {len(self.guilds)} serveur(s)")
        
        # Show server and channel info
        for guild in self.guilds:
            print(f"Serveur: {guild.name} (ID: {guild.id})")
        
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
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
