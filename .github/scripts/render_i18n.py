"""Render the site template once per language.

Usage: render_i18n.py <template.html> <i18n_dir> <out_dir>

Writes <out_dir>/index.html (German, the default), <out_dir>/pt/index.html, and
the robots.txt and sitemap.xml that point search engines at both. The service
list comes from <out_dir>/assets/services.json (see csv_to_json.py), so build
that first; it is written into the page so search engines see it without
running the script.
Placeholders look like {{key}}; values come from <i18n_dir>/<lang>.json and may
contain inline HTML. Keys starting with "js." are collected into {{js}}, a JSON
object the page script reads as T. The build fails on any missing translation.
"""
import datetime
import html
import json
import os
import re
import sys

SITE_URL = 'https://daracosta.de/'
# (html lang, dictionary file, output sub-path, Open Graph locale). The first entry is the default.
LOCALES = [
    ('de', 'de.json', '', 'de_DE'),
    ('pt-BR', 'pt-BR.json', 'pt/', 'pt_BR'),
]
PLACEHOLDER_RE = re.compile(r'\{\{([\w.]+)\}\}')


def load(i18n_dir, filename):
    with open(os.path.join(i18n_dir, filename), encoding='utf-8') as f:
        return json.load(f)


def esc(value):
    return html.escape(str(value or ''))


def service_markup(categories, gender, book_label, visible):
    """The category buttons and panels for one gender, as the page script used to build them."""
    hidden = '' if visible else ' hidden'
    nav = ''.join(f'''
          <button class="snav-btn{' active' if ci == 0 else ''}" data-panel="{gender}-{ci}" data-category="{esc(c['name'])}">
            <span class="snav-num">{ci + 1:02d}</span> {esc(c['name'])}
          </button>''' for ci, c in enumerate(categories))
    panels = []
    for ci, c in enumerate(categories):
        blocks = []
        for gi, g in enumerate(c['groups']):
            items = []
            for ii, i in enumerate(g['items']):
                sub = f'<div class="nail-sub">{esc(i["description"])}</div>' if i['description'] else ''
                duration = f'<span class="nail-duration">{i["duration"]} min</span>' if i['duration'] else ''
                items.append(f'''
              <div class="nail-item slide-up" style="transition-delay:{min(ii, 6) * 0.05:g}s">
                <div><div class="nail-name">{esc(i['name'])}</div>{sub}</div>
                <div class="nail-meta">
                  {duration}
                  <button type="button" class="btn-book-mini" data-item-id="{esc(i['itemId'])}" data-variant-id="{esc(i['variantId'])}" data-name="{esc(i['name'])}">{book_label}</button>
                </div>
              </div>''')
            title = f'<div class="wax-group-title">{esc(g["name"])}</div>' if g['name'] else ''
            blocks.append(f'''
          <div class="wax-block slide-up" style="transition-delay:{min(gi, 4) * 0.08:g}s">
            {title}
            <div class="nail-list">{''.join(items)}
            </div>
          </div>''')
        panels.append(f'''
        <div class="service-panel{' active' if ci == 0 else ''}" id="panel-{gender}-{ci}" data-category="{esc(c['name'])}">
          <div class="wax-groups">{''.join(blocks)}
          </div>
        </div>''')
    return (f'<div class="service-set" data-gender="{gender}"{hidden}>{nav}\n        </div>',
            f'<div class="service-set" data-gender="{gender}"{hidden}>{"".join(panels)}\n      </div>')


def service_values(services, strings):
    # "Für sie" is shown by default; the page script switches to the visitor's last choice.
    sets = [service_markup(services[g], g, strings['js.book'], g == 'ela') for g in ('ela', 'ele')]
    return {
        'page.serviceNav': ''.join(nav for nav, _ in sets),
        'page.servicePanels': ''.join(panels for _, panels in sets),
    }


def page_values(strings, lang, path, og_locale):
    depth = path.count('/')
    up = '../' * depth
    values = {k: v for k, v in strings.items() if not k.startswith('js.')}
    values.update({
        'page.lang': lang,
        'page.assets': up,
        'page.root': up or './',
        'page.url': SITE_URL + path,
        'site.url': SITE_URL,
        'site.year': str(datetime.date.today().year),
        'page.ogLocale': og_locale,
        'page.ogLocaleAlt': next(og for l, _, _, og in LOCALES if l != lang),
        'page.descriptionJson': json.dumps(strings['meta.description'], ensure_ascii=False),
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


def write(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'Wrote {path}')


def sitemap():
    alternates = ''.join(
        f'\n    <xhtml:link rel="alternate" hreflang="{lang}" href="{SITE_URL}{path}"/>'
        for lang, _, path, _ in LOCALES
    ) + f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE_URL}"/>'
    urls = ''.join(f'\n  <url>\n    <loc>{SITE_URL}{path}</loc>{alternates}\n  </url>'
                   for _, _, path, _ in LOCALES)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
            ' xmlns:xhtml="http://www.w3.org/1999/xhtml">'
            f'{urls}\n</urlset>\n')


def main(template_path, i18n_dir, out_dir):
    with open(template_path, encoding='utf-8') as f:
        template = f.read()
    dictionaries = [(lang, load(i18n_dir, filename), path, og) for lang, filename, path, og in LOCALES]

    default_lang, default_keys = dictionaries[0][0], set(dictionaries[0][1])
    for lang, strings, _, _ in dictionaries[1:]:
        if set(strings) != default_keys:
            only_default = sorted(default_keys - set(strings))
            only_here = sorted(set(strings) - default_keys)
            sys.exit(f'{lang} and {default_lang} keys differ. '
                     f'Missing in {lang}: {only_default or "-"}. Missing in {default_lang}: {only_here or "-"}.')

    used = set(PLACEHOLDER_RE.findall(template))
    unused = sorted(k for k in default_keys if not k.startswith('js.') and k not in used)
    if unused:
        print(f'warning: unused keys: {", ".join(unused)}')

    services_path = os.path.join(out_dir, 'assets', 'services.json')
    if not os.path.exists(services_path):
        sys.exit(f'{services_path} not found; run csv_to_json.py first')
    with open(services_path, encoding='utf-8') as f:
        services = json.load(f)

    for lang, strings, path, og in dictionaries:
        values = page_values(strings, lang, path, og)
        values.update(service_values(services[lang], strings))
        page = render(template, values, lang)
        dst = os.path.join(out_dir, path, 'index.html')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(page)
        print(f'Wrote {dst} ({lang})')

    write(os.path.join(out_dir, 'robots.txt'), f'User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n')
    write(os.path.join(out_dir, 'sitemap.xml'), sitemap())


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
