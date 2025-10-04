"""Test configuration and fixtures"""
import asyncio
from unittest.mock import AsyncMock
from api_client import PuddleApiClient


def mock_api_client():
	"""Mock API client for testing without network calls"""
	client = AsyncMock(spec=PuddleApiClient)
	client.health.return_value = True
	client.get_player.return_value = {
		"name": "TestPlayer",
		"ratings": [
			{
				"character": "Sol Badguy",
				"char_short": "SO",
				"rating": 1500,
				"match_count": 10
			}
		]
	}
	return client


def event_loop():
	"""Create an instance of the default event loop for the test session."""
	loop = asyncio.new_event_loop()
	yield loop
	loop.close()