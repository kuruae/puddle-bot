"""
Discord slash commands for the GGST bot
"""
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from database import Database

# API URLs
API_BASE_URL = "https://puddle.farm/api"
API_PLAYER_URL = f"{API_BASE_URL}/player"


class GGSTCommands(commands.Cog):
    """Command handlers for GGST bot"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
    


    @app_commands.command(name="add_player", description="Add a player to the tracker")
    @app_commands.describe(
        player_id="The player's ID from puddle.farm",
        name="The player's display name"
    )
    async def add_player(self, interaction: discord.Interaction, player_id: str, name: str):
        """Add a new player to track
        
        takes player ID and name, verifies player exists on puddle.farm
        command should be working so far?
        """
        await interaction.response.defer()
        
        try:
            # Verify player exists in puddle.farm
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_PLAYER_URL}/{player_id}") as resp:
                    if resp.status != 200:
                        await interaction.followup.send(f"❌ Joueur ID `{player_id}` introuvable sur puddle.farm")
                        return
            
            self.db.add_player(player_id, name)
            await interaction.followup.send(f"✅ Joueur **{name}** (ID: `{player_id}`) ajouté à la surveillance!")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur: {e}")
    



    @app_commands.command(name="list_players", description="Show all players being tracked")
    async def list_players(self, interaction: discord.Interaction):
        """List all tracked players
        
        should work too
        
        """
        players = self.db.get_all_players()
        if not players:
            await interaction.response.send_message("Aucun joueur surveillé.", ephemeral=True)
            return
        
        player_list = "\n".join([f"• **{name}** (ID: `{player_id}`)" for name, player_id in players.items()])
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
                await interaction.response.send_message(f"❌ Joueur **{name}** non trouvé dans la liste.", ephemeral=True)
                return
            
            player_id = players[name]
            self.db.remove_player(player_id)
            await interaction.response.send_message(f"✅ Joueur **{name}** retiré de la surveillance!")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur: {e}", ephemeral=True)
    



    @app_commands.command(name="stats", description="Show statistics for a tracked player")
    @app_commands.describe(name="The player's name")
    async def stats(self, interaction: discord.Interaction, name: str):
        """Show player statistics"""
        await interaction.response.defer()
        
        try:
            players = self.db.get_all_players()
            if name not in players:
                await interaction.followup.send(f"❌ Joueur **{name}** non trouvé.", ephemeral=True)
                return
            
            player_id = players[name]
            
            # Fetch current player data
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_PLAYER_URL}/{player_id}") as resp:
                    if resp.status != 200:
                        await interaction.followup.send(f"❌ Impossible de récupérer les données pour {name}")
                        return
                    
                    player_data = await resp.json()
                    
                    # Create stats embed
                    embed = discord.Embed(
                        title=f"📊 Statistiques de {name}",
                        color=0x0099FF
                    )
                    
                    # Add character ratings
                    ratings = player_data.get("ratings", [])
                    if ratings:
                        char_info = []
                        for char in ratings[:5]:  # Show top 5 characters
                            char_name = char["character"]
                            rating = char.get("rating", 0)
                            match_count = char.get("match_count", 0)
                            char_info.append(f"**{char_name}**: {rating:.0f} ({match_count} matches)")
                        
                        embed.add_field(
                            name="🥊 Personnages Principaux",
                            value="\n".join(char_info),
                            inline=False
                        )
                    
                    # Add global rank if available
                    if "top_global" in player_data:
                        embed.add_field(
                            name="🏆 Classement Global",
                            value=f"#{player_data['top_global']}",
                            inline=True
                        )
                    
                    embed.set_footer(text="Données de puddle.farm")
                    await interaction.followup.send(embed=embed)
                    
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur: {e}")
    


	
    @app_commands.command(name="help", description="Show help information")
    async def help_command(self, interaction: discord.Interaction):
        """Show help information"""
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
                "`/stats <nom>` - Statistiques d'un joueur\n"
                "`/help` - Afficher cette aide"
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Information",
            value="Le bot vérifie automatiquement les nouveaux matches toutes les 2 minutes.",
            inline=False
        )
        
        embed.set_footer(text="Source: github.com/kuruae/puddle-bot")
        await interaction.response.send_message(embed=embed)


# Function to setup commands
async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(GGSTCommands(bot))
