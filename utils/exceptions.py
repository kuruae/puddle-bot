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

class ProcessingError(BotError):
	"""Non-fatal error during match processing (logic / data issues)."""
	def __init__(self, message: str):
		super().__init__(message)