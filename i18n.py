"""Simple YAML-based i18n utility.

Loads all YAML files from locales/ directory. File name (without extension)
becomes the locale code (e.g. en.yml -> 'en').

Usage:
	from i18n import t
	t("help.title")

Supports simple .format(**kwargs) interpolation.
Falls back to default locale when key missing in selected locale.
If still missing, returns [key] so it's obvious in UI.

Locale selection strategy (initial version):
 - Global default set from environment variable LANG (default 'en')
 - Can be changed at runtime with set_default_locale
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import os

import logging
import yaml

_LOCALES_DIR = Path(__file__).parent / "locales"

def _normalize_locale(raw: str | None) -> str:
	"""Normalize environment LANG variants to a simple language code.

	Examples:
	  "en_US.UTF-8" -> "en"
	  "fr_FR" -> "fr"
	  "en" -> "en"
	  None / empty -> "en"
	"""
	if not raw:
		return "en"
	raw = raw.strip()
	if not raw:
		return "en"
	# Drop encoding part
	if "." in raw:
		raw = raw.split(".", 1)[0]
	# Lowercase
	raw = raw.lower()
	# Take primary subtag before underscore if present
	if "_" in raw:
		raw = raw.split("_", 1)[0]
	return raw

_DEFAULT_LOCALE = _normalize_locale(os.getenv("LANG", "en"))

class I18n:
	"""Simple i18n utility loading from YAML files."""

	def __init__(self, locales_dir: Path, default_locale: str):
		self.locales_dir = locales_dir
		self.default_locale = _normalize_locale(default_locale)
		self._translations: dict[str, dict[str, str]] = {}
		self.load_all()

		if self.default_locale not in self._translations:
			if "en" in self._translations:
				self.default_locale = "en"
			elif self._translations:
				self.default_locale = next(iter(self._translations.keys()))

	def load_all(self) -> None:
		"""loader"""
		self._translations.clear()
		if not self.locales_dir.exists():
			return
		for file in self.locales_dir.glob("*.yml"):
			locale = file.stem
			try:
				with file.open("r", encoding="utf-8") as f:
					data = yaml.safe_load(f) or {}
				flat = _flatten(data)
				self._translations[locale] = flat
			except (OSError, yaml.YAMLError) as err:  # pragma: no cover - defensive
				logging.getLogger(__name__).warning("Failed loading locale %s: %s", locale, err)

	def set_default_locale(self, locale: str) -> None:
		"""Set default language (accepts variants like en_US)."""
		norm = _normalize_locale(locale)
		if norm in self._translations:
			self.default_locale = norm

	def t(self, key: str, *, locale: Optional[str] = None, **fmt: Any) -> str:
		"""Translate key with optional locale and formatting."""
		lang = locale or self.default_locale
		val = (
			self._translations.get(lang, {}).get(key)
			or self._translations.get(self.default_locale, {}).get(key)
		)
		if val is None:
			return f"[{key}]"
		if fmt:
			# Only format if all placeholders likely present; ignore KeyError gracefully.
			try:
				val = val.format(**fmt)
			except KeyError as err:  # pragma: no cover - defensive
				logging.getLogger(__name__).debug("Missing format key %s for %s", err, key)
		return val


def _flatten(d: Dict[str, Any], parent: str = "", out: Optional[Dict[str, str]] = None) -> Dict[str, str]:
	"""Flatten nested dict into dot-separated keys."""
	if out is None:
		out = {}
	for k, v in d.items():
		full = f"{parent}.{k}" if parent else k
		if isinstance(v, dict):
			_flatten(v, full, out)
		else:
			out[full] = str(v)
	return out

# Singleton instance
i18n = I18n(_LOCALES_DIR, _DEFAULT_LOCALE)

def t(key: str, **kwargs: Any) -> str:
	"""Translate key using global i18n instance."""
	return i18n.t(key, **kwargs)
