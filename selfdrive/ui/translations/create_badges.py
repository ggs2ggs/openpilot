#!/usr/bin/env python3
import json
import os
import requests

from common.basedir import BASEDIR
from selfdrive.ui.update_translations import LANGUAGES_FILE, TRANSLATIONS_DIR

TRANSLATION_TAG = "<translation"
UNFINISHED_TRANSLATION_TAG = "<translation type=\"unfinished\""
TRANSLATION_BADGE = "translation_badge_{}.svg"

if __name__ == "__main__":
  with open(LANGUAGES_FILE, "r") as f:
    translation_files = json.load(f)

  print("Copy into selfdrive/ui/translations/README.md:\n")
  for name, file in translation_files.items():
    if not len(file):
      continue

    with open(os.path.join(TRANSLATIONS_DIR, f"{file}.ts"), "r") as f:
      tr_file = f.read()

    print(f"[![language](https://raw.githubusercontent.com/commaai/openpilot/badges/{TRANSLATION_BADGE.format(file)})]({file}.ts)")

    total_translations = 0
    unfinished_translations = 0
    for line in tr_file.splitlines():
      if TRANSLATION_TAG in line:
        total_translations += 1
      if UNFINISHED_TRANSLATION_TAG in line:
        unfinished_translations += 1

    percent_finished = (1 - unfinished_translations / total_translations) * 100.
    percent_finished = int(percent_finished * 10) / 10  # round down (99.99% shouldn't be 100%)
    color = "green" if percent_finished == 100 else "orange" if percent_finished >= 70 else "red"

    r = requests.get(f"https://img.shields.io/badge/LANGUAGE {name}-FINISHED: {percent_finished}%25-{color}")
    assert r.status_code == 200, "Error downloading badge"

    with open(os.path.join(BASEDIR, TRANSLATION_BADGE.format(file)), "wb") as f:
      f.write(bytes(r.content))
