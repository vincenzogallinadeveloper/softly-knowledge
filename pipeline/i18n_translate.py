#!/usr/bin/env python3
"""
Softly Knowledge — machine-translate the Discover catalog with DeepL.

Reads the generated English catalog (i18n/en/catalog.en.json) and writes
i18n/<lang>/catalog.<lang>.json for each target language, keeping the exact same
structure (same keys, nulls stay null, alias lists keep their length). This is
SANITARY text: every output carries `_meta.review` and is never shown to a user
without a native review pass. Missing languages/strings fall back to English at
build time, so running this is purely additive and safe.

Protected and NEVER translated:
  • {placeholders}                         — kept verbatim
  • proper nouns / acronyms (PCOS, NHS, …) — kept verbatim
  • markdown link targets  [text](url)     — the (url) is kept verbatim

Auth: DeepL now rejects the legacy `auth_key` body parameter (403). We send the
`Authorization: DeepL-Auth-Key <key>` header instead.

RUN (from the repo root, the folder containing i18n/ and pipeline/):
  DEEPL_API_KEY="your-key:fx" python3 -m pipeline.i18n_translate
  DEEPL_API_KEY="…" python3 -m pipeline.i18n_translate --dry-run          # count only
  DEEPL_API_KEY="…" python3 -m pipeline.i18n_translate --langs it,es,fr   # a subset
  DEEPL_API_KEY="…" python3 -m pipeline.i18n_translate --force            # overwrite existing
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
I18N_DIR = os.path.join(HERE, "..", "i18n")
SOURCE_LOCALE = "en"

# App language code -> DeepL target code. Only DeepL-supported languages appear here;
# every other language in the app stays on the English fallback until filled in.
LANG_MAP = {
    "ar": "AR", "bg": "BG", "cs": "CS", "da": "DA", "de": "DE", "el": "EL",
    "es": "ES", "et": "ET", "fi": "FI", "fr": "FR", "hu": "HU", "id": "ID",
    "it": "IT", "ja": "JA", "ko": "KO", "lt": "LT", "lv": "LV", "nb": "NB",
    "nl": "NL", "pl": "PL", "pt": "PT-PT", "ro": "RO", "ru": "RU", "sk": "SK",
    "sl": "SL", "sv": "SV", "tr": "TR", "uk": "UK", "zh-Hans": "ZH-HANS",
    "zh-Hant": "ZH-HANT",
}

# Terms kept verbatim across every language.
KEEP_TERMS = ["PCOS", "PMDD", "PMS", "Softly", "NHS", "WHO", "ACOG", "NICE",
              "LH", "FSH", "hCG", "BBT", "IUD", "IUS", "BMI", "HPV", "STI", "IVF"]
PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z0-9_]+\}")
MD_LINK_RE = re.compile(r"(\]\()([^)]+)(\))")   # the (url) part of [text](url)

# The translatable fields, in a fixed order for deterministic output.
ATOM_FIELDS = ["title", "glance", "overview", "deep", "when_to_see_doctor", "red_flags"]
CATPATH_FIELDS = ["title", "summary"]


def protect(text):
    """Prepare one string for DeepL's XML tag-handling: escape raw XML entities in the Markdown
    (so `&`, `<`, `>` don't break the parser → HTTP 400), then wrap placeholders, proper nouns and
    markdown link targets in <x>…</x> so they're passed through untranslated."""
    # Escape entities FIRST — after this the only angle brackets are the <x> tags we add next.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = PLACEHOLDER_RE.sub(lambda m: f"<x>{m.group(0)}</x>", text)
    text = MD_LINK_RE.sub(lambda m: f"{m.group(1)}<x>{m.group(2)}</x>{m.group(3)}", text)
    for term in KEEP_TERMS:
        text = re.sub(rf"(?<![\w]){re.escape(term)}(?![\w])", f"<x>{term}</x>", text)
    return text


def unprotect(text):
    text = text.replace("<x>", "").replace("</x>", "")
    # Reverse the entity escaping (amp last so "&amp;lt;" wouldn't double-decode).
    return text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def deepl_endpoint(key):
    return "https://api-free.deepl.com/v2/translate" if key.endswith(":fx") else "https://api.deepl.com/v2/translate"


def translate_batch(texts, target, key, dry_run):
    if dry_run or not texts:
        return list(texts)
    data = [("target_lang", target), ("source_lang", "EN"),
            ("tag_handling", "xml"), ("ignore_tags", "x")]
    data += [("text", t) for t in texts]
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(deepl_endpoint(key), data=body,
                                 headers={"Authorization": f"DeepL-Auth-Key {key}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    return [t["text"] for t in payload["translations"]]


def collect_units(catalog):
    """Yield (kind, node_id, field, index) for every translatable string in the catalog.
    `index` is the alias position for alias units, else None."""
    for node_id, atom in catalog.get("atoms", {}).items():
        for field in ATOM_FIELDS:
            if isinstance(atom.get(field), str) and atom[field].strip():
                yield ("atoms", node_id, field, None)
        for i, alias in enumerate(atom.get("aliases") or []):
            if isinstance(alias, str) and alias.strip():
                yield ("atoms", node_id, "aliases", i)
    for section in ("categories", "paths"):
        for node_id, node in catalog.get(section, {}).items():
            for field in CATPATH_FIELDS:
                if isinstance(node.get(field), str) and node[field].strip():
                    yield (section, node_id, field, None)


def get_value(catalog, unit):
    kind, node_id, field, index = unit
    node = catalog[kind][node_id]
    return node[field][index] if index is not None else node[field]


def set_value(catalog, unit, value):
    kind, node_id, field, index = unit
    node = catalog[kind][node_id]
    if index is not None:
        node[field][index] = value
    else:
        node[field] = value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", help="comma-separated app language codes (default: all supported)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="overwrite existing catalog.<lang>.json")
    args = parser.parse_args()

    key = os.environ.get("DEEPL_API_KEY", "")
    if not key and not args.dry_run:
        sys.exit("DEEPL_API_KEY is not set. Export it, or pass --dry-run.")

    source_path = os.path.join(I18N_DIR, SOURCE_LOCALE, f"catalog.{SOURCE_LOCALE}.json")
    with open(source_path, encoding="utf-8") as f:
        source = json.load(f)
    checksum = source.get("_meta", {}).get("source_content_checksum", "")

    units = list(collect_units(source))
    protected = [protect(get_value(source, u)) for u in units]
    total_chars = sum(len(get_value(source, u)) for u in units)

    wanted = args.langs.split(",") if args.langs else [l for l in LANG_MAP if l != SOURCE_LOCALE]

    for lang in wanted:
        target = LANG_MAP.get(lang)
        if not target or lang == SOURCE_LOCALE:
            print(f"skip {lang}: not a DeepL target (stays on English fallback)")
            continue
        out_dir = os.path.join(I18N_DIR, lang)
        out_path = os.path.join(out_dir, f"catalog.{lang}.json")
        if os.path.exists(out_path) and not args.force:
            print(f"skip {lang}: catalog.{lang}.json already exists (use --force to overwrite)")
            continue

        print(f"{'[dry-run] ' if args.dry_run else ''}{lang} ({target}): {len(units)} strings, ~{total_chars} chars")
        if args.dry_run:
            continue

        translated = []
        for i in range(0, len(protected), 40):
            translated += translate_batch(protected[i:i + 40], target, key, args.dry_run)
            time.sleep(0.2)

        # Deep-copy the source structure, then overlay the translations onto it.
        out = json.loads(json.dumps(source))
        out["_meta"] = {
            "lang": lang,
            "is_source": False,
            "source_content_checksum": checksum,
            "review": "Machine-translated (DeepL) from en — needs native review.",
        }
        for unit, value in zip(units, translated):
            set_value(out, unit, unprotect(value))

        os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"  wrote {out_path}")

    print("\nDone. Rebuild with `python3 -m pipeline.build`, then review each language natively.")


if __name__ == "__main__":
    main()
