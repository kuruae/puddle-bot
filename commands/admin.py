"""Administrative and developer utility slash commands."""
from __future__ import annotations

import io
import os
import textwrap
import traceback
import asyncio
from typing import Any, Dict, List, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from .base_command import is_owner

LOG_FILE_ENV: str = "BOT_LOG_FILE"
INLINE_LOG_CHAR_LIMIT: int = 4000
DEFAULT_LOG_LINES: int = 40
TRACEBACK_CHAR_LIMIT: int = 1900
EVAL_TIMEOUT: int = 40  # seconds


class Admin(commands.Cog, name="Admin"):
	"""Cog providing diagnostic, maintenance and owner-only utilities."""

	def __init__(self, bot: commands.Bot):
		self.bot = bot

	@app_commands.command(name="ping", description="Show bot latency (ms)")
	async def ping(self, interaction: discord.Interaction) -> None:
		"""Reply with the current websocket latency in milliseconds."""
		latency_ms = round(self.bot.latency * 1000, 1) if self.bot.latency else 0
		await interaction.response.send_message(f"🏓 Pong! Latence: {latency_ms} ms")

	@app_commands.command(name="reload", description="Reload all loaded cogs")
	@is_owner()
	async def reload(self, interaction: discord.Interaction) -> None:
		"""Hot-reload every currently loaded extension (owner only)."""
		await interaction.response.defer(ephemeral=True)
		extensions: List[str] = list(self.bot.extensions.keys())
		reloaded: List[str] = []
		failures: List[Tuple[str, str]] = []
		for ext in extensions:
			try:
				await self.bot.reload_extension(ext)
				reloaded.append(ext)
			except (commands.ExtensionError, ModuleNotFoundError, AttributeError) as err:
				failures.append((ext, str(err)))

		lines: List[str] = [f"🔄 {len(reloaded)} extension(s) reloaded"]
		if reloaded:
			lines.extend(reloaded)
		if failures:
			lines.append("❌ Failures:")
			lines.extend([f"{ext}: {err}" for ext, err in failures])
		await interaction.followup.send("\n".join(lines), ephemeral=True)

	@app_commands.command(name="shutdown", description="Gracefully shut down the bot")
	@is_owner()
	async def shutdown(self, interaction: discord.Interaction) -> None:
		"""Close the Discord connection and terminate the process."""
		await interaction.response.send_message("Arrêt du bot...", ephemeral=True)
		await self.bot.close()

	@app_commands.command(name="logs", description="Show recent log lines")
	@app_commands.describe(lines="Number of tail lines from configured log file")
	@is_owner()
	async def logs(self, interaction: discord.Interaction, lines: int = DEFAULT_LOG_LINES) -> None:
		"""Display the last N lines from the log file (if configured)."""
		await interaction.response.defer(ephemeral=True)
		log_path = os.getenv(LOG_FILE_ENV)
		if not log_path or not os.path.isfile(log_path):
			await interaction.followup.send(
				f"Fichier de log introuvable (variable {LOG_FILE_ENV} manquante ou invalide).",
				ephemeral=True,
			)
			return
		try:
			with open(log_path, "r", encoding="utf-8") as fp:
				recent_lines: List[str] = fp.readlines()[-lines:]
		except OSError as err:
			await interaction.followup.send(f"Erreur d'accès log: {err}", ephemeral=True)
			return

		text = "".join(recent_lines)
		if len(text) <= INLINE_LOG_CHAR_LIMIT:
			snippet = text[-INLINE_LOG_CHAR_LIMIT:]
			await interaction.followup.send(f"```log\n{snippet}\n```", ephemeral=True)
		else:
			buffer = io.StringIO(text)
			await interaction.followup.send(
				content=f"Dernières {lines} lignes", file=discord.File(buffer, filename="logs.txt"), ephemeral=True
			)

	@app_commands.command(name="eval", description="Execute Python code (owner only)")
	@app_commands.describe(code="Python code to run; wrap in ``` for blocks")
	@is_owner()
	async def eval(self, interaction: discord.Interaction, code: str) -> None:
		"""Execute arbitrary async Python in a restricted environment.

		Dangerous by nature; restricted to owner. Supports awaiting inside the body.
		Returns the function's return value if not None.
		"""
		await interaction.response.defer(ephemeral=True)

		# Clean code block formatting
		if code.startswith("```") and code.endswith("```"):
			inner = code[3:-3].strip()
			if inner.lower().startswith(("python\n", "py\n")):
				inner = inner.split("\n", 1)[1]
			code = inner

		# Wrap in async function
		wrapped = "async def __eval_fn__(bot, interaction, _print_buffer):\n" + textwrap.indent(code, "    ")

		# Enhanced safe builtins - add more useful functions
		safe_builtins: Dict[str, Any] = {
			"len": len,
			"range": range,
			"min": min,
			"max": max,
			"sum": sum,
			"sorted": sorted,
			"enumerate": enumerate,
			"zip": zip,
			"map": map,
			"filter": filter,
			"abs": abs,
			"round": round,
			"str": str,
			"int": int,
			"float": float,
			"bool": bool,
			"list": list,
			"dict": dict,
			"tuple": tuple,
			"set": set,
			"type": type,
			"isinstance": isinstance,
			"hasattr": hasattr,
			"getattr": getattr,
		}

		# Create print buffer to capture print() output
		print_buffer = io.StringIO()

		# Custom print function that writes to our buffer
		def safe_print(*args, **kwargs):
			print(*args, **kwargs, file=print_buffer)

		# Enhanced environment with more useful modules
		env: Dict[str, Any] = {
			"bot": self.bot,
			"interaction": interaction,
			"discord": discord,
			"asyncio": asyncio,
			"print": safe_print,
			"_print_buffer": print_buffer,
			"__builtins__": safe_builtins,
			"__name__": "__eval__",
		}

		try:
			# Compile the code
			compiled = compile(wrapped, filename="<eval>", mode="exec")

			# Execute with timeout protection
			exec(compiled, env) # pylint: disable=exec-used # nosec
			func = env["__eval_fn__"]

			# Run with timeout
			result = await asyncio.wait_for(
				func(self.bot, interaction, print_buffer),
				timeout=EVAL_TIMEOUT
			)

		except asyncio.TimeoutError:
			await interaction.followup.send(
				f"⏰ Code execution timed out after {EVAL_TIMEOUT} seconds",
				ephemeral=True
			)
			return

		except SyntaxError as err:
			await interaction.followup.send(
				f"❌ Syntax Error: `{err}`\nLine {err.lineno}: {err.text}",
				ephemeral=True
			)
			return

		except Exception as err: # pylint: disable=broad-except
			tb_text = "".join(traceback.format_exception(type(err), err, err.__traceback__))
			# Clean up the traceback to remove our wrapper
			lines = tb_text.split('\n')
			cleaned_lines = []
			skip_next = False

			for line in lines:
				if '__eval_fn__' in line or skip_next:
					skip_next = '__eval_fn__' in line
					continue
				cleaned_lines.append(line)

			cleaned_tb = '\n'.join(cleaned_lines)

			if len(cleaned_tb) > TRACEBACK_CHAR_LIMIT:
				cleaned_tb = cleaned_tb[-TRACEBACK_CHAR_LIMIT:]
				cleaned_tb = "...\n" + cleaned_tb

			await interaction.followup.send(
				f"❌ **Error:**\n```py\n{cleaned_tb}\n```",
				ephemeral=True
			)
			return

		# Collect output
		print_output = print_buffer.getvalue()

		# Format response
		response_parts = []

		if result is not None:
			response_parts.append(f"**Return Value:**\n```py\n{repr(result)}\n```")

		if print_output:
			# Limit print output length
			if len(print_output) > 1000:
				print_output = print_output[:1000] + "\n... (output truncated)"
			response_parts.append(f"**Output:**\n```\n{print_output}\n```")

		if not response_parts:
			response_parts.append("✅ Code executed successfully (no output)")

		# Send response (may need to split if too long)
		full_response = "\n\n".join(response_parts)

		if len(full_response) > 1900:
			# Send as file if too long
			buffer = io.StringIO(full_response)
			await interaction.followup.send(
				"✅ Code executed (output too long, sent as file):",
				file=discord.File(buffer, filename="eval_output.txt"),
				ephemeral=False
			)
		else:
			await interaction.followup.send(full_response, ephemeral=False)

	@app_commands.command(name="evalpy", description="Execute Python code with syntax highlighting")
	@app_commands.describe(code="Python code to run (no need for code blocks)")
	@is_owner()
	async def evalpy(self, interaction: discord.Interaction, code: str) -> None:
		"""Alternative eval command that assumes Python code without blocks"""
		# Just call the main eval but format the code
		formatted_code = f"```python\n{code}\n```"
		await self.eval(interaction, formatted_code)


async def setup(bot: commands.Bot) -> None:
	"""Add the Admin cog to the bot."""
	await bot.add_cog(Admin(bot))
