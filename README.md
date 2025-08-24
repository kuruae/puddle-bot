# OUTDATED

TODO: update this doc, make a centralized API client with proper async context management (top priority but im lazy), everything else should come after

# GGST Discord Bot

This bot posts Guilty Gear Strive match results to a Discord channel using the Puddle Farm API.

## Setup

1. Install the dependencies:

```bash
pip install -r requirements.txt
```

2. Make `config.py` and set your Discord bot token. You can copy `conf_example.py` to `config.py` and fill in your details.
3. Run the bot:

```bash
python bot.py
```

The bot checks new matches every n minutes and announces them in the channel specified in `config.py`.
