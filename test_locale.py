#!/usr/bin/env python3

import os
from dotenv import load_dotenv, dotenv_values
from i18n import i18n, _normalize_locale, _DEFAULT_LOCALE

print("=== Before loading .env ===")
print(f"System LANG: {repr(os.getenv('LANG'))}")

# Load .env
load_dotenv()

print("=== After loading .env ===")
print(f"Raw LANG from env: {repr(os.getenv('LANG'))}")
print(f"Values from .env file: {dotenv_values('.env')}")
print(f"Normalized LANG: {repr(_normalize_locale(os.getenv('LANG')))}")
print(f"_DEFAULT_LOCALE: {repr(_DEFAULT_LOCALE)}")
print(f"i18n.default_locale: {repr(i18n.default_locale)}")
print(f"Available translations: {list(i18n._translations.keys())}")

# Test a translation
test_key = "help.description"
result = i18n.t(test_key)
print(f"Translation of '{test_key}': {repr(result)}")

# Test with explicit locale
result_en = i18n.t(test_key, locale="en")
result_fr = i18n.t(test_key, locale="fr")
print(f"Translation of '{test_key}' with locale='en': {repr(result_en)}")
print(f"Translation of '{test_key}' with locale='fr': {repr(result_fr)}")
