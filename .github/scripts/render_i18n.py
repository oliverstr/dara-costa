"""Render the site template once per language.

Usage: render_i18n.py <template.html> <i18n_dir> <out_dir>

Writes <out_dir>/index.html (German, the default) and <out_dir>/pt/index.html.
Placeholders look like {{key}}; values come from <i18n_dir>/<lang>.json and may
contain inline HTML. Keys starting with "js." are collected into {{js}}, a JSON
object the page script reads as T. The build fails on any missing translation.
"""
import json
import os
import re
import sys

SITE_URL = 'https://oliverstr.github.io/dara-costa/'
# (html lang, dictionary file, output sub-path). The first entry is the default.
LOCALES = [
    ('de', 'de.json', ''),
    ('pt-BR', 'pt-BR.json', 'pt/'),
]
PLACEHOLDER_RE = re.compile(r'\{\{([\w.]+)\}\}')


def load(i18n_dir, filename):
    with open(os.path.join(i18n_dir, filename), encoding='utf-8') as f:
        return json.load(f)


def page_values(strings, lang, path):
    depth = path.count('/')
    up = '../' * depth
    values = {k: v for k, v in strings.items() if not k.startswith('js.')}
    values.update({
        'page.lang': lang,
        'page.assets': up,
        'page.root': up or './',
        'page.url': SITE_URL + path,
        'site.url': SITE_URL,
        # "</" would end the inline <script> early.
        'js': json.dumps({k[3:]: v for k, v in strings.items() if k.startswith('js.')},
                         ensure_ascii=False).replace('</', '<\\/'),
    })
    return values


def render(template, values, lang):
    missing = sorted({k for k in PLACEHOLDER_RE.findall(template) if k not in values})
    if missing:
        sys.exit(f'{lang}: no value for {", ".join(missing)}')
    return PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], template)


def main(template_path, i18n_dir, out_dir):
    with open(template_path, encoding='utf-8') as f:
        template = f.read()
    dictionaries = [(lang, load(i18n_dir, filename), path) for lang, filename, path in LOCALES]

    default_lang, default_keys = dictionaries[0][0], set(dictionaries[0][1])
    for lang, strings, _ in dictionaries[1:]:
        if set(strings) != default_keys:
            only_default = sorted(default_keys - set(strings))
            only_here = sorted(set(strings) - default_keys)
            sys.exit(f'{lang} and {default_lang} keys differ. '
                     f'Missing in {lang}: {only_default or "-"}. Missing in {default_lang}: {only_here or "-"}.')

    used = set(PLACEHOLDER_RE.findall(template))
    unused = sorted(k for k in default_keys if not k.startswith('js.') and k not in used)
    if unused:
        print(f'warning: unused keys: {", ".join(unused)}')

    for lang, strings, path in dictionaries:
        html = render(template, page_values(strings, lang, path), lang)
        dst = os.path.join(out_dir, path, 'index.html')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'Wrote {dst} ({lang})')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
