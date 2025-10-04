"""Tests for i18n module"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import yaml
from i18n import I18n, _normalize_locale, _flatten


class TestI18n(unittest.TestCase):
	"""Test i18n functionality"""

	def test_normalize_locale(self):
		"""Test locale normalization"""
		self.assertEqual(_normalize_locale("en_US.UTF-8"), "en")
		self.assertEqual(_normalize_locale("fr_FR"), "fr")
		self.assertEqual(_normalize_locale("en"), "en")
		self.assertEqual(_normalize_locale(None), "en")
		self.assertEqual(_normalize_locale(""), "en")

	def test_flatten_dict(self):
		"""Test dictionary flattening"""
		nested = {"help": {"title": "Test", "desc": "Description"}}
		expected = {"help.title": "Test", "help.desc": "Description"}
		self.assertEqual(_flatten(nested), expected)

	def test_translation_fallback(self):
		"""Test translation with fallback behavior"""
		with TemporaryDirectory() as tmpdir:
			locales_dir = Path(tmpdir)

			# Create test locale files
			en_file = locales_dir / "en.yml"
			en_file.write_text(yaml.dump({"test": {"key": "English value"}}))

			fr_file = locales_dir / "fr.yml"
			fr_file.write_text(yaml.dump({"test": {"key": "French value"}}))

			i18n = I18n(locales_dir, "fr")

			# Test normal translation
			self.assertEqual(i18n.t("test.key"), "French value")

			# Test fallback to English
			self.assertEqual(i18n.t("missing.key"), "[missing.key]")

			# Test formatting
			fr_file.write_text(yaml.dump({"greet": "Hello {name}!"}))
			i18n.load_all()
			self.assertEqual(i18n.t("greet", name="World"), "Hello World!")


if __name__ == "__main__":
	unittest.main()