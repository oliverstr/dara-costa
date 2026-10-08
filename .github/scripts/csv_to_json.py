"""Convert a SumUp items export (CSV) into the services.json used by the site.

Usage: csv_to_json.py <export.csv> <services.json> <i18n_dir>

Each service is a parent row whose item name ends in "[ela]" or "[ele]", followed by
variant rows (empty item name) whose SKU picks the site language ("de" or "pt") and
whose "Variations" value is the name shown there. Category values may carry a
sub-group suffix, e.g. "Waxing[Gesicht]". Category and sub-group names are German;
their translations live in <i18n_dir>/categories.json.

Output: {"<lang>": {"ela": [category, ...], "ele": [...]}, ...}
"""
import csv
import html
import json
import os
import re
import sys
import unicodedata

COLUMNS = {
    'name': 'Item name',
    'variation': 'Variations',
    'sku': 'SKU',
    'category': 'Category',
    'description': 'Description (Online Store and Invoices only)',
    'duration': 'Duration [minutes] (Bookings only)',
    'price': 'Price',
    'itemId': 'Item id (Do not change)',
    'variantId': 'Variant id (Do not change)',
}
# SKU on the variant row -> page language. The first entry is the source language (German).
LOCALES = {'de': 'de', 'pt': 'pt-BR'}
GENDERS = ('ela', 'ele')
CATEGORY_RE = re.compile(r'^(.+?)\s*\[([^\]]+)\]\s*$')
GENDER_RE = re.compile(r'^(.*?)\s*\[(ela|ele)\]\s*$', re.IGNORECASE)
TAG_RE = re.compile(r'<[^>]+>')


def sort_key(value):
    # Accent-insensitive so "Íntima" sorts next to "I", not after "Z".
    decomposed = unicodedata.normalize('NFKD', value or '')
    return ''.join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def text(value):
    value = html.unescape(TAG_RE.sub('', value or '')).strip()
    return value or None


def number(value, cast):
    value = (value or '').strip()
    return cast(value) if value else None


def split_category(value):
    value = (value or '').strip()
    match = CATEGORY_RE.match(value)
    return (match.group(1).strip(), match.group(2).strip()) if match else (value, None)


def read_rows(src):
    with open(src, encoding='utf-8-sig', newline='') as f:
        header = f.readline()
        f.seek(0)
        # SumUp exports have come with both separators.
        delimiter = ';' if header.count(';') > header.count(',') else ','
        reader = csv.DictReader(f, delimiter=delimiter)
        missing = [c for c in COLUMNS.values() if c not in (reader.fieldnames or [])]
        if missing:
            sys.exit(f'Missing columns in {src}: {", ".join(missing)}')
        return list(reader)


def parse_services(rows):
    """Group variant rows under their parent row."""
    services = []
    for row in rows:
        name = row[COLUMNS['name']].strip()
        if name:
            match = GENDER_RE.match(name)
            if not match:
                sys.exit(f'Item "{name}" has no [ela]/[ele] suffix')
            services.append({'row': row, 'label': name, 'gender': match.group(2).lower(), 'variants': {}})
            continue
        if not services:
            sys.exit('Variant row before any item row')
        service = services[-1]
        sku = row[COLUMNS['sku']].strip().lower()
        if sku not in LOCALES:
            sys.exit(f'Item "{service["label"]}" has a variant with unknown SKU "{sku}"')
        if LOCALES[sku] in service['variants']:
            sys.exit(f'Item "{service["label"]}" has more than one "{sku}" variant')
        service['variants'][LOCALES[sku]] = row

    for service in services:
        missing = [sku for sku, lang in LOCALES.items() if lang not in service['variants']]
        if missing:
            sys.exit(f'Item "{service["label"]}" has no variant for SKU {", ".join(missing)}')
    return services


def load_translations(i18n_dir, services):
    with open(os.path.join(i18n_dir, 'categories.json'), encoding='utf-8') as f:
        translations = json.load(f)
    names = set()
    for service in services:
        category, group = split_category(service['row'][COLUMNS['category']])
        names.update(n for n in (category, group) if n)
    langs = list(LOCALES.values())[1:]
    missing = sorted(f'{n} ({lang})' for n in names for lang in langs
                     if not translations.get(n, {}).get(lang))
    if missing:
        sys.exit(f'Missing translations in {i18n_dir}/categories.json: {", ".join(missing)}')
    return translations


def build(services, lang, gender, translations):
    def tr(name):
        return translations.get(name, {}).get(lang, name) if name else name

    tree = {}
    for service in services:
        if service['gender'] != gender:
            continue
        row, variant = service['row'], service['variants'][lang]
        category, group = split_category(row[COLUMNS['category']])
        tree.setdefault(tr(category), {}).setdefault(tr(group), []).append({
            'name': variant[COLUMNS['variation']].strip(),
            'description': text(row[COLUMNS['description']]),
            'duration': number(row[COLUMNS['duration']], int),
            'price': number(variant[COLUMNS['price']], float),
            'itemId': row[COLUMNS['itemId']].strip(),
            'variantId': variant[COLUMNS['variantId']].strip(),
        })

    return [
        {
            'name': category,
            'groups': [
                {'name': group, 'items': sorted(items, key=lambda i: sort_key(i['name']))}
                # Ungrouped items (None key) come first.
                for group, items in sorted(groups.items(), key=lambda g: sort_key(g[0]))
            ],
        }
        for category, groups in sorted(tree.items(), key=lambda c: sort_key(c[0]))
    ]


def main(src, dst, i18n_dir):
    services = parse_services(read_rows(src))
    translations = load_translations(i18n_dir, services)
    output = {
        lang: {gender: build(services, lang, gender, translations) for gender in GENDERS}
        for lang in LOCALES.values()
    }

    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write('\n')
    counts = ', '.join(f'{g}: {sum(s["gender"] == g for s in services)}' for g in GENDERS)
    print(f'Wrote {len(services)} items ({counts}) in {len(LOCALES)} languages to {dst}')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
