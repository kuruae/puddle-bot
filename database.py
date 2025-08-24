"""
Database module for Puddle Bot

Handles database connections and operations for both PostgreSQL (production)
and SQLite (local development).
"""
import os
import sqlite3
import psycopg
from psycopg.rows import dict_row


class Database:
	"""Database handler with support for PostgreSQL and SQLite"""

	def __init__(self):
		self.connection = None
		self.is_postgres = False
		self.connect()
		self.setup_tables()

	def connect(self):
		"""Connect to database (PostgreSQL in production, SQLite locally)"""
		database_url = os.getenv('DATABASE_URL')

		if database_url and database_url.startswith('postgres'):
			# Production: PostgreSQL
			try:
				self.connection = psycopg.connect(
					database_url, row_factory=dict_row
				)
				self.is_postgres = True
				print("✅ Connected to PostgreSQL database")
			except Exception as exc:
				print(f"❌ PostgreSQL connection failed: {exc}")
				raise
		else:
			# Local development: SQLite
			try:
				self.connection = sqlite3.connect('local_bot.db')
				self.connection.row_factory = sqlite3.Row  # For dict-like access
				self.is_postgres = False
				print("✅ Connected to SQLite database (local development)")
			except Exception as exc:
				print(f"❌ SQLite connection failed: {exc}")
				raise

	def setup_tables(self):
		"""Create necessary tables"""
		cursor = self.connection.cursor()

		if self.is_postgres:
			# PostgreSQL syntax
			cursor.execute("""
				CREATE TABLE IF NOT EXISTS players (
					id BIGINT PRIMARY KEY,
					name VARCHAR(100) NOT NULL,
					created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
				)
			""")

			cursor.execute("""
				CREATE TABLE IF NOT EXISTS match_cache (
					player_id BIGINT,
					character VARCHAR(10),
					match_id VARCHAR(100),
					created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
					PRIMARY KEY (player_id, character, match_id)
				)
			""")
		else:
			# SQLite syntax
			cursor.execute("""
				CREATE TABLE IF NOT EXISTS players (
					id INTEGER PRIMARY KEY,
					name TEXT NOT NULL,
					created_at DATETIME DEFAULT CURRENT_TIMESTAMP
				)
			""")

			cursor.execute("""
				CREATE TABLE IF NOT EXISTS match_cache (
					player_id INTEGER,
					character TEXT,
					match_id TEXT,
					created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
					PRIMARY KEY (player_id, character, match_id)
				)
			""")

		self.connection.commit()
		cursor.close()

	def get_player_cache(self, player_id: str) -> dict:
		"""Get cached matches for a player"""
		cursor = self.connection.cursor()

		if self.is_postgres:
			cursor.execute(
				"SELECT character, match_id FROM match_cache "
				"WHERE player_id = %s ORDER BY created_at DESC",
				(player_id,)
			)
		else:
			cursor.execute(
				"SELECT character, match_id FROM match_cache "
				"WHERE player_id = ? ORDER BY created_at DESC",
				(player_id,)
			)

		cache = {}
		for row in cursor.fetchall():
			char = row['character']
			if char not in cache:
				cache[char] = []
			cache[char].append(row['match_id'])

		cursor.close()
		return cache

	def save_match_to_cache(self, player_id: str, character: str, match_id: str):
		"""Save a match to cache"""
		cursor = self.connection.cursor()

		if self.is_postgres:
			cursor.execute(
				"INSERT INTO match_cache (player_id, character, match_id) "
				"VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
				(player_id, character, match_id)
			)
		else:
			cursor.execute(
				"INSERT OR IGNORE INTO match_cache "
				"(player_id, character, match_id) VALUES (?, ?, ?)",
				(player_id, character, match_id)
			)

		self.connection.commit()
		cursor.close()

	def cleanup_cache(self, player_id: str, character: str, cache_size: int = 20):
		"""Keep only the most recent N matches for a character"""
		cursor = self.connection.cursor()

		if self.is_postgres:
			cursor.execute("""
				DELETE FROM match_cache
				WHERE player_id = %s AND character = %s
				AND match_id NOT IN (
					SELECT match_id FROM match_cache
					WHERE player_id = %s AND character = %s
					ORDER BY created_at DESC
					LIMIT %s
				)
			""", (player_id, character, player_id, character, cache_size))
		else:
			cursor.execute("""
				DELETE FROM match_cache
				WHERE player_id = ? AND character = ?
				AND match_id NOT IN (
					SELECT match_id FROM match_cache
					WHERE player_id = ? AND character = ?
					ORDER BY created_at DESC
					LIMIT ?
				)
			""", (player_id, character, player_id, character, cache_size))

		self.connection.commit()
		cursor.close()

	def add_player(self, player_id: str, name: str):
		"""Add a new player to track"""
		cursor = self.connection.cursor()

		if self.is_postgres:
			cursor.execute(
				"INSERT INTO players (id, name) VALUES (%s, %s) "
				"ON CONFLICT (id) DO UPDATE SET name = %s",
				(player_id, name, name)
			)
		else:
			cursor.execute(
				"INSERT OR REPLACE INTO players (id, name) VALUES (?, ?)",
				(player_id, name)
			)

		self.connection.commit()
		cursor.close()

	def get_all_players(self) -> dict:
		"""Get all tracked players"""
		cursor = self.connection.cursor()
		cursor.execute("SELECT id, name FROM players")

		players = {}
		for row in cursor.fetchall():
			players[row['name']] = str(row['id'])

		cursor.close()
		return players

	def remove_player(self, player_id: str):
		"""Remove a player from tracking"""
		cursor = self.connection.cursor()

		if self.is_postgres:
			# Remove player and their cache
			cursor.execute("DELETE FROM match_cache WHERE player_id = %s", (player_id,))
			cursor.execute("DELETE FROM players WHERE id = %s", (player_id,))
		else:
			# SQLite
			cursor.execute("DELETE FROM match_cache WHERE player_id = ?", (player_id,))
			cursor.execute("DELETE FROM players WHERE id = ?", (player_id,))

		self.connection.commit()
		cursor.close()
