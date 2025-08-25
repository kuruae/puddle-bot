"""
Custom exceptions for the bot.
"""
class BotError(Exception):
	"""Base exception for bot-related errors"""

class CharNotFound(BotError):
	"""Exception raised when a character is not found."""
	def __init__(self, char_short: str):
		self.char_short = char_short
		super().__init__(f"Character not found: {char_short}")