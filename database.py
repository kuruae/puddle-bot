import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

class Database:
    def __init__(self):
        self.connection = None
        self.connect()
        self.setup_tables()
    
    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                os.getenv('DATABASE_URL'),
                cursor_factory=RealDictCursor
            )
            print("✅ Connected to PostgreSQL database")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
    
    def setup_tables(self):
        """Create necessary tables"""
        cursor = self.connection.cursor()
        
        # Players table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id BIGINT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Match cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS match_cache (
                player_id BIGINT,
                character VARCHAR(10),
                match_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (player_id, character, match_id)
            )
        """)
        
        self.connection.commit()
        cursor.close()
    
    def get_player_cache(self, player_id: str) -> dict:
        """Get cached matches for a player"""
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT character, match_id FROM match_cache WHERE player_id = %s ORDER BY created_at DESC",
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
        cursor.execute(
            "INSERT INTO match_cache (player_id, character, match_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (player_id, character, match_id)
        )
        self.connection.commit()
        cursor.close()
    
    def cleanup_cache(self, player_id: str, character: str, cache_size: int = 20):
        """Keep only the most recent N matches for a character"""
        cursor = self.connection.cursor()
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
        self.connection.commit()
        cursor.close()
    
    def add_player(self, player_id: str, name: str):
        """Add a new player to track"""
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO players (id, name) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET name = %s",
            (player_id, name, name)
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