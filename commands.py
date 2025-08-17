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
        if interaction.user.id != int(os.getenv('BOT_OWNER_ID')):
            await interaction.response.send_message(
                "Owner-only command.",
                ephemeral=True
            )
            return False
        return True
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





    # -------------------------
    # Stats helper methods
    # -------------------------

    def _format_character_info(self, char_data: dict) -> str:
        """Helper function to format a single character's information"""
        char_name = char_data["character"]
        rating = char_data.get("rating", 0)
        match_count = char_data.get("match_count", 0)

        # Base character info
        info_lines = [f"**{char_name}**: {rating:.0f} ({match_count} matches)"]

        # Add character rank if available
        if char_data.get("top_char", 0) > 0:
            info_lines.append(f"└ Rang: #{char_data['top_char']}")

        # Add best victory for this character
        if "top_defeated" in char_data and char_data["top_defeated"]["value"] > 0:
            top_defeated = char_data["top_defeated"]
            info_lines.append(
                f"└ Meilleure victoire: **{top_defeated['name']}** "
                f"({top_defeated['char_short']}) - {top_defeated['value']:.0f}"
            )

        return "\n".join(info_lines)


    def _resolve_player_identifier(self, name_or_id: str) -> tuple[str, str | None]:
        """Return (player_id, player_name_if_tracked)

        If the provided input matches a tracked player name, we map to its ID.
        Otherwise we assume it is already an ID.
        """
        players = self.db.get_all_players()

        if name_or_id in players:
            return players[name_or_id], name_or_id

        return name_or_id, None


    async def _fetch_player_data(self, player_id: str) -> dict | None:
        """Fetch player data from puddle.farm. Returns None if not found."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_PLAYER_URL}/{player_id}") as resp:
                if resp.status != 200:
                    return None
                return await resp.json()


    def _filter_and_sort_characters(self, player_data: dict, min_matches: int = 15) -> list[dict]:
        """Return characters with at least min_matches sorted desc by rating."""
        ratings = player_data.get("ratings", []) or []
        filtered = [c for c in ratings if c.get("match_count", 0) >= min_matches]
        return sorted(filtered, key=lambda x: x.get("rating", 0), reverse=True)


    def _build_stats_embed(self, player_name: str, player_data: dict) -> discord.Embed:
        """Construct the statistics embed from player data."""
        embed = discord.Embed(
            title=f"🖩 Statistiques de {player_name}",
            color=0x0099FF
        )

        # Global ranking
        if player_data.get("top_global", 0) > 0:
            embed.add_field(
                name="🏆 Classement Global",
                value=f"#{player_data['top_global']}",
                inline=False
            )

        # Characters (top 3)
        sorted_chars = self._filter_and_sort_characters(player_data)

        if sorted_chars:
            for i, char in enumerate(sorted_chars[:3], 1):
                embed.add_field(
                    name=f"Personnage #{i}",
                    value=self._format_character_info(char),
                    inline=False
                )
        else:
            embed.add_field(
                name="Personnages",
                value="Aucun personnage avec 15+ matches",
                inline=False
            )

        embed.set_footer(text="puddle.farm")
        return embed


    @app_commands.command(name="stats", description="Show statistics for a player")
    @app_commands.describe(name_or_id="The player's name (if tracked) or puddle.farm ID")
    async def stats(self, interaction: discord.Interaction, name_or_id: str):
        """Show player statistics"""
        await interaction.response.defer()

        try:
            # Resolve identifier (may give us tracked name)
            player_id, tracked_name = self._resolve_player_identifier(name_or_id)

            # Fetch data
            player_data = await self._fetch_player_data(player_id)
            if not player_data:
                await interaction.followup.send(
                    f"❌ Joueur `{name_or_id}` introuvable sur puddle.farm"
                )
                return

            # Use tracked name, else API name, else original input
            player_name = tracked_name or player_data.get("name", name_or_id)

            embed = self._build_stats_embed(player_name, player_data)
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
                "`/stats <nom>/<id>` - Statistiques d'un joueur\n"
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
