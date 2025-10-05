# puddle-bot

A Discord bot for tracking Guilty Gear Strive matches using [puddle.farm](https://puddle.farm).

## 📚 About This Project

I built this bot because my friend and I wanted to track our friends and their matches
while also learning async python. Despite starting together, I ended up developing it alone as I used this as an opportunity to learn a lot of new things like CI/CD pipelines and automated heroku deployments which required more control.

Along the way, I ended up learning:

- **Async Python**: Finally wrapped my head around `asyncio`, async context managers, and how to not block the event loop
- **API Design**: Built a proper HTTP client with retry logic and rate limiting
- **Databases**: Learned how to use PostgreSQL with `asyncpg` and connection pooling
- **Discord Bots**: Figured out slash commands, embeds, and why cogs are actually pretty neat for organization
- **Internationalization**: The bot was originally in French, so I had to build a proper i18n system to support multiple languages since having English is a must

Most features were added while actually learning how to implement them. The code probably reflects that but I tried to keep it clean and modular enough to be easily maintainable and extensible since this is an aspect I care about.

## ✨ Features

- **Real-time Match Tracking**: Automatically polls player profiles and announces new matches
- **Player Management**: Add/remove players to track, view comprehensive statistics  
- **Leaderboards**: Global and character-specific rankings with pagination
- **Multi-language Support**: English and French localization with easy addition of new languages
- **Robust API Client**: Async HTTP client with retry logic, rate limiting, and error handling ([detailed docs](api_client/api_client.md))
- **Admin Tools**: CI/CD integration, bot management, diagnostics, and code evaluation for development
- **Health Monitoring**: API connectivity checks and status reporting

## 🎮 Commands

| Command | Description |
|---------|-------------|
| `/add_player <id> <name>` | Add a player to tracking |
| `/remove_player <name>` | Remove a player from tracking |
| `/list_players` | Show all tracked players |
| `/stats <name/id>` | View detailed player statistics |
| `/top [character]` | Show leaderboards (global or character-specific) |
| `/distribution` | Character popularity across the playerbase |
| `/health` | Check API connectivity status |
| `/help` | Show command reference |

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- a discord bot token
- Database: PostgreSQL (recommended for production) or SQLite (auto-generated if no DATABASE_URL provided)

### Local Development

1. **Clone and setup**
   ```bash
   git clone https://github.com/kuruae/puddle-bot.git
   cd puddle-bot
   uv sync
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```
   Required variables:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   CHANNEL_ID=123456789012345678
   ```
   
   Optional variables:
   ```env
   DATABASE_URL=postgresql://user:pass@localhost/dbname  # defaults to SQLite if not set
   OWNER_ID=your_discord_id  # for admin commands
   LANG=en          # language (en/fr, defaults to en)
   POLL_INTERVAL=2  # minutes between match checks (defaults to 2)
   LOCALES_DIR=locales  # directory for translation files (defaults to locales)
   ```

3. **Run the bot**
   ```bash
   uv run python bot.py
   ```

### Heroku Deployment

This bot is configured for easy Heroku deployment:

1. **Create Heroku app**
   ```bash
   heroku create your-bot-name
   heroku addons:create heroku-postgresql:mini
   ```

2. **Set environment variables**
   ```bash
   heroku config:set DISCORD_TOKEN=your_token
   heroku config:set CHANNEL_ID=your_channel_id
   heroku config:set LANG=en
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

The `Procfile` is already configured to run the bot as a worker dyno.

## 🏗️ Architecture

The API Client handles all communication with puddle.farm—see [api_client.md](api_client/api_client.md) for implementation details including retry policies, rate limiting, and error handling.

```
                         ┌─────────────────┐
                         │  puddle.farm    │
                         │      API        │
                         └─────────────────┘
                                   ▲
                                   │ HTTP requests
                                   │
                         ┌─────────────────┐
                         │   API Client    │
                         │ (api_client.py) │
                         │ • Retry logic   │
                         │ • Rate limiting │
                         └─────────────────┘
                                   ▲
                          ┌────────┴──────────┐
                          │                   │
                ┌──────────────────┐ ┌─────────────────┐
                │  Match Tracker   │ │ Command Cogs    │
                │(match_tracker.py)│ │ • player_mgmt   │
                │ • Poll matches   │ │ • stats         │
                │ • Create embeds  │ │ • leaderboard   │
                └──────────────────┘ │ • admin         │
                          │          └─────────────────┘
                          │                   │
                          ▼                   │
                ┌─────────────────┐           │
                │    Database     │           │
                │ (database.py)   │◄──────────┘
                │ • Player cache  │
                │ • Match history │
                └─────────────────┘
                          ▲
                          │
                ┌─────────────────┐
                │  Discord Bot    │
                │    (bot.py)     │
                │ • Event loop    │
                │ • Cog loading   │
                │ • i18n support  │
                └─────────────────┘
                          ▲
                          │
                ┌─────────────────┐
                │   Discord API   │
                │ • Slash commands│
                │ • Message embeds│
                └─────────────────┘
```

## 🌍 Internationalization

The bot supports multiple languages through YAML configuration:

- **Adding a new language**: Create `locales/xx.yml` (where `xx` is the language code)
- **Switching languages**: Set `LANG=xx` in your environment
- **Translation structure**: Organized by feature (help, stats, admin, etc.)

Example translation entry:
```yaml
stats:
  title: "🤓☝️ Stats for {player}"
  player_not_found: "❌ Player `{identifier}` not found"
```

## 🧪 Testing

Run tests with:
```bash
uv run python -m pytest tests/
```

The test suite is the lacking part right now, it will be improved soon 🫡

## 📊 Monitoring

The bot includes built-in health monitoring:
- API connectivity checks (`/health` command)
- Structured logging with configurable levels (info, debug, warning, error)
- Error classification and retry policies
- Rate limiting to respect API constraints

## 🛠️ Development

- **Linting**: `pylint` with custom configuration
- **CI/CD**: GitHub Actions for automated checks
- **Dependencies**: Managed via `uv` and `pyproject.toml`


## 📋 Roadmap

- [ ] Per-guild language preferences
- [ ] Player matchup analysis and predictions
- [ ] Automatic ELO synchronization with rate limiting
- [ ] Username-based player lookup (not just IDs)
- [ ] Prometheus metrics for operational monitoring
- [ ] Hot-reload for translation files

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [nemasu's puddle.farm](https://github.com/nemasu/puddle-farm) for providing the GGST match data API
