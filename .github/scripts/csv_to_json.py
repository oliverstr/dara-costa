"""Convert a SumUp items export (CSV) into the nested services.json used by the site.

Usage: csv_to_json.py <export.csv> <services.json>

Category values may carry a sub-group suffix, e.g. "Depilação [Rosto]".
"""
import csv
import html
import json
import re
import sys
import unicodedata

COLUMNS = {
    'name': 'Item name',
    'category': 'Category',
    'description': 'Description (Online Store and Invoices only)',
    'duration': 'Duration [minutes] (Bookings only)',
    'price': 'Price',
    'itemId': 'Item id (Do not change)',
    'variantId': 'Variant id (Do not change)',
}
CATEGORY_RE = re.compile(r'^(.+?)\s*\[([^\]]+)\]\s*$')
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


def main(src, dst):
    with open(src, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS.values() if c not in (reader.fieldnames or [])]
        if missing:
            sys.exit(f'Missing columns in {src}: {", ".join(missing)}')
        rows = list(reader)

    tree = {}
    for row in rows:
        category, group = split_category(row[COLUMNS['category']])
        tree.setdefault(category, {}).setdefault(group, []).append({
            'name': row[COLUMNS['name']].strip(),
            'description': text(row[COLUMNS['description']]),
            'duration': number(row[COLUMNS['duration']], int),
            'price': number(row[COLUMNS['price']], float),
            'itemId': row[COLUMNS['itemId']].strip(),
            'variantId': row[COLUMNS['variantId']].strip(),
        })

    services = [
        {
            'name': category,
            'groups': [
                {'name': group, 'items': sorted(items, key=lambda i: sort_key(i['name']))}
                # Ungrouped items ('' key) come first.
                for group, items in sorted(groups.items(), key=lambda g: sort_key(g[0]))
            ],
        }
        for category, groups in sorted(tree.items(), key=lambda c: sort_key(c[0]))
    ]

    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(services, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'Wrote {len(rows)} items in {len(services)} categories to {dst}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
