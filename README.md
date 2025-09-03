# OUTDATED

TODO: 

update this doc, ~~make a centralized API client with proper async context management (top priority but im lazy)~~(UPDATE: DONE), everything else should come after in term of development, improve logging and error handling(started to work on it already) etc etc yyeyeyeyeyehh

in terms of functionnalities: ~~fix top/leaderboard command~~(done), ~~get the stats command and the tracker to include a link to puddle.farm~~(apparently not possible to hyperlink the footer), search rating by username instead of IDs for users who aren't inside the bot's database, add support for multiple languages, sync profiles to their current elo (must be integrated with a 1-2 minutes rate limit per player profile), player matchup prediction algorithm aware of character matchups (either global to the playerbase or using each player past performances in the character matchup, idk yet)

~~# GGST Discord Bot~~

~~This bot posts Guilty Gear Strive match results to a Discord channel using the Puddle Farm API.~~

~~## Setup~~

~~1. Install the dependencies:~~

```bash
pip install -r requirements.txt
```

~~2. Make `config.py` and set your Discord bot token. You can copy `conf_example.py` to `config.py` and fill in your details.~~
~~3. Run the bot:~~

```bash
python bot.py
```

~~The bot checks new matches every n minutes and announces them in the channel specified in `config.py`.~~
