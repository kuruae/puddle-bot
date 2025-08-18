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

# @TODO: Separate commands into different files bc they are getting too large
#
#       I don't know if python supports multiple files for a single cog, nor how
#       to do it if so, and I have to read about how/if python has interfaces
#       or abstract classes, so I can define a common interface for all commands.
#       Maybe if Hugo started helping me it would be done already </3

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




    # -------------------------
    # Leaderboard helpers
    # -------------------------

    async def _fetch_leaderboard(self, character: str | None = None) -> list[dict]:
        """Fetch top players from puddle.farm, optionally filtered by character.

        Returns a list (expected up to 100 entries).
        """
        if character:
            url = f"{API_PLAYER_URL}/top_char/{character}"
        else:
            url = f"{API_PLAYER_URL}/top"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                return await resp.json()


    def _build_leaderboard_pages(self, data: list[dict],
                                    character: str | None = None,
                                    page_size: int = 10) -> list[discord.Embed]:
        """Turn raw leaderboard data into a list of embeds (pages)."""
        pages: list[discord.Embed] = []
        if not data:
            embed = discord.Embed(
                title="🏆 Classement",
                description="Aucune donnée disponible.",
                color=0x0099FF
            )
            pages.append(embed)
            return pages

        total = len(data)
        title = "🏆 Classement Global" if not character else f"🏆 Classement {character}"
        for start in range(0, total, page_size):

            slice_ = data[start:start + page_size]
            lines = []

            for idx, entry in enumerate(slice_, start=start + 1):
                name = entry.get("name", "?")
                rating = entry.get("rating")
                char_long = entry.get("char_long")
                # Show character tag only if character filter not applied
                if not character and char_long:
                    line = f"**#{idx}** {name} ({char_long}) - {rating:.0f}"
                else:
                    line = f"**#{idx}** {name} - {rating:.0f}"
                lines.append(line)
            page_num = (start // page_size) + 1
            page_total = (total + page_size - 1) // page_size
            embed = discord.Embed(
                title=title,
                description="\n".join(lines) or "(vide)",
                color=0x0099FF
            )
            embed.set_footer(text=f"Page {page_num}/{page_total} • puddle.farm")
            pages.append(embed)
        return pages

    class LeaderboardView(discord.ui.View):
        """Interactive pagination view for leaderboard."""
        def __init__(self, pages: list[discord.Embed], user_id: int, timeout: float = 120):
            super().__init__(timeout=timeout)
            self.pages = pages
            self.index = 0
            self.user_id = user_id

            self.prev_button: discord.ui.Button | None = None
            self.next_button: discord.ui.Button | None = None

            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    if child.custom_id == "lb_prev":
                        self.prev_button = child
                    elif child.custom_id == "lb_next":
                        self.next_button = child
            self._update_button_states()

        def _update_button_states(self):
            """Enable/disable navigation buttons based on current index."""
            if self.prev_button:
                self.prev_button.disabled = self.index <= 0
            if self.next_button:
                self.next_button.disabled = self.index >= len(self.pages) - 1

        @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, custom_id="lb_prev")
        async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button):
            """Go to previous page."""
            self.index = max(self.index - 1, 0)
            self._update_button_states()
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)

        @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, custom_id="lb_next")
        async def next(self, interaction: discord.Interaction, _button: discord.ui.Button):
            """Go to next page."""
            self.index = min(self.index + 1, len(self.pages) - 1)
            self._update_button_states()
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)

        @discord.ui.button(label="🛑", style=discord.ButtonStyle.danger, custom_id="leaderboard_stop")
        async def end(self, interaction: discord.Interaction, _button: discord.ui.Button):  # type: ignore
            """Disable pagination controls."""
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            await interaction.response.edit_message(view=self)
            super().stop()

    @app_commands.command(name="top", description="Show top players in the database")
    @app_commands.describe(character="Filter by character name (optional)")
    async def top(self, interaction: discord.Interaction, character: str | None = None):
        """Show top players leaderboard (with pagination)."""
        await interaction.response.defer()
        try:
            data = await self._fetch_leaderboard(character)
            pages = self._build_leaderboard_pages(data, character)
            view = self.LeaderboardView(pages, interaction.user.id)
            await interaction.followup.send(embed=pages[0], view=view)
        except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as exc:
            await interaction.followup.send(f"❌ Erreur de récupération du classement: {exc}")




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
            # Split long URL across lines for pylint line length
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
