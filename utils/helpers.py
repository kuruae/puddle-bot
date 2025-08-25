"""Helper functions and constants (not a cog)."""
import utils.exceptions as bot_exceptions

_CHAR_SHORT_CODES: set[str] = {
	"SO",  # Sol
	"KY",  # Ky
	"MA",  # May
	"AX",  # Axl
	"CH",  # Chipp
	"PO",  # Potemkin
	"FA",  # Faust
	"MI",  # Millia
	"ZA",  # Zato-1
	"RA",  # Ramlethal
	"LE",  # Leo
	"NA",  # Nagoriyuki
	"GI",  # Giovanna
	"AN",  # Anji
	"IN",  # I-No
	"GO",  # Goldlewis
	"JC",  # Jack-O'
	"HA",  # Happy Chaos
	"BA",  # Baiken
	"TE",  # Testament
	"BI",  # Bridget
	"SI",  # Sin
	"BE",  # Bedman?
	"AS",  # Asuka
	"JN",  # Johnny
	"EL",  # Elphelt
	"AB",  # A.B.A.
	"SL",  # Slayer
	"DI",  # Dizzy
	"VE",  # Venom
	"UN",  # Unika
	"LU",  # Lucy
}

_RANKS: dict[str, int] = {
	"Vanquisher": 45000,

	"Diamond 3": 40800,
	"Diamond 2": 36600,
	"Diamond 1": 32400,

	"Platinum 3": 28400,
	"Platinum 2": 24400,
	"Platinum 1": 20400,

	"Gold 3": 18000,
	"Gold 2": 15600,
	"Gold 1": 13200,

	"Silver 3": 11000,
	"Silver 2": 8800,
	"Silver 1": 6600,

	"Bronze 3": 5400,
	"Bronze 2": 4200,
	"Bronze 1": 3000,

	"Iron 3": 2000,
	"Iron 2": 1000,
	"Iron 1": 1,
}

def verify_char_short(char_short: str) -> str:
	"""Validate and normalize a character short code from user input.

	Returns the normalized character short code if valid.

	Raises:
		CharNotFound: If the character short code is invalid.
	"""
	code = char_short.strip().upper()
	if code not in _CHAR_SHORT_CODES:
		raise bot_exceptions.CharNotFound(f"Personnage invalide: {code}")
	return code


def calculate_rank(elo: int) -> str:
	"""Calculate the rank based on the elo."""
	for rank, threshold in _RANKS.items():
		if elo >= threshold:
			return rank
	return "Unranked"


def str_elo(elo: int) -> str:
	"""Normalize / format the elo rating.

	Why the 8 and 4 magic numbers:
		It seems that currently, after reaching vanquisher the elo system changes from 'RP' to 'DR'
		When this happens, the API sends the DR elo as a 8 digits number starting by 1000
		and ending by the actual elo.
	"""
	string_elo = str(elo)
	if elo > 45000 and len(string_elo) == 8:
		string_elo = string_elo[4:]
		string_elo += " DR"
	else:
		string_elo += " RP"

	return string_elo