"""
Discord slash commands for the puddle bot
"""
import os
import aiohttp
import discord
from discord import app_commands, Interaction
from discord.ext import commands
from database import Database

# API URLs
API_BASE_URL = "https://puddle.farm/api"
API_PLAYER_URL = f"{API_BASE_URL}/player"


def is_owner():
    """Check if the command is run by the bot owner"""
    async def predicate(interaction: Interaction) -> bool:
        return interaction.user.id == int(os.getenv('BOT_OWNER_ID'))
    return app_commands.check(predicate)

class GGSTCommands(commands.Cog):
    """Command handlers for puddle bot"""

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
                        await interaction.followup.send(
                            f"❌ Joueur ID `{player_id}` introuvable sur puddle.farm"
                        )
                        return

            self.db.add_player(player_id, name)
            await interaction.followup.send(
                f"✅ Joueur **{name}** (ID: `{player_id}`) ajouté à la surveillance!"
            )

        except (aiohttp.ClientError, aiohttp.ServerTimeoutError, ValueError) as exc:
            await interaction.followup.send(f"❌ Erreur: {exc}")




    @app_commands.command(name="list_players", description="Show all players being tracked")
    async def list_players(self, interaction: discord.Interaction):
        """List all tracked players

        should work too

        """
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




    @app_commands.command(name="stats", description="Show statistics for a tracked player")
    @app_commands.describe(name="The player's name")
    async def stats(self, interaction: discord.Interaction, name: str):
        """Show player statistics"""
        await interaction.response.defer()

        try:
            players = self.db.get_all_players()
            if name not in players:
                await interaction.followup.send(
                    f"❌ Joueur **{name}** non trouvé.", ephemeral=True
                )
                return

            player_id = players[name]

            # Fetch current player data
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_PLAYER_URL}/{player_id}") as resp:
                    if resp.status != 200:
                        await interaction.followup.send(
                            f"❌ Impossible de récupérer les données pour {name}"
                        )
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
                            char_info.append(
                                f"**{char_name}**: {rating:.0f} ({match_count} matches)"
                            )

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

        except (aiohttp.ClientError, aiohttp.ServerTimeoutError, ValueError, KeyError) as exc:
            await interaction.followup.send(f"❌ Erreur: {exc}")




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


# Function to setup commands
async def setup(bot):
    """Setup function for loading the cog"""
    cog = GGSTCommands(bot)
    await bot.add_cog(cog)

    # Manually add commands to the tree if needed
    print(f"Added {len(cog.get_app_commands())} app commands to cog")
