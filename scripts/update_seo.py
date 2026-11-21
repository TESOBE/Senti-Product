#!/usr/bin/env python3
"""
Write what search engines and AI tools read, from one list of pages:

- in each page's <head>: the title, the canonical address, Open Graph and Twitter tags, and JSON-LD structured data,
  between <!-- seo: and <!-- /seo --> (the block is replaced each time, so it is safe to run again);
- docs/sitemap.xml, docs/robots.txt and docs/llms.txt.

Run it after adding or renaming a page, or changing a title or description:

    python3 scripts/update_seo.py

The description in each page's <meta name="description"> is the one used everywhere, so it is written in one place.
Everything that belongs to this site is in the settings below; the rest is the same for every TESOBE product site.
"""

import datetime
import html
import json
import pathlib
import re
import subprocess

# ---- Settings for this site ----

SITE = 'https://senti.tesobe.com/'
SITE_NAME = 'TESOBE Senti'
SHARE_IMAGE = 'img/social.jpg'
SHARE_IMAGE_ALT = 'TESOBE Senti: watches your APIs and apps, and suggests what matters'

# Each page: its file, its title, the heading it is listed under in llms.txt, and for a product page the software it
# describes (with its repository when the code is public). The order is the order of the sitemap and llms.txt.
PAGES = [
    {'file': 'index.html', 'title': 'TESOBE Senti: watches your APIs and apps, and suggests security and performance fixes', 'group': 'Senti',
     'app': {'name': 'TESOBE Senti', 'category': 'DeveloperApplication'}},
]

# llms.txt: the summary under the site's name, more detail, and links beyond this site's own pages.
LLMS_SUMMARY = (
    'TESOBE Senti watches a running API, app, website or service for hours, not seconds: its source code, logs, metrics '
    'and telemetry. It sends one short briefing with at most three suggestions, ranked by impact, and fixes them when '
    'asked, on the customer\'s own infrastructure with read-only credentials and capped AI spend. It is made by TESOBE GmbH '
    'in Berlin, and is set up for each customer\'s own system. It comes ready for the Open Bank Project (OBP-API and its apps).'
)
LLMS_DETAILS = ''
LLMS_MORE = {
    'Optional': [
        ('Senti configured for OBP', 'https://obp-api-product.tesobe.com/senti.html', 'Senti ready for OBP-API and its apps.'),
        ('Contact TESOBE', 'https://www.tesobe.com/#contact', 'talk to the team that makes it.'),
    ],
}

# ---- The same for every TESOBE product site ----

DOCS = pathlib.Path(__file__).resolve().parent.parent / 'docs'
LICENCE = 'https://www.gnu.org/licenses/agpl-3.0.html'
TESOBE = {
    '@type': 'Organization',
    '@id': 'https://www.tesobe.com/#organization',
    'name': 'TESOBE GmbH',
    'url': 'https://www.tesobe.com',
    'sameAs': ['https://github.com/OpenBankProject', 'https://www.openbankproject.com'],
}


def page_url(file_name):
    """The page's public address; index.html is the site's root."""
    return SITE if file_name == 'index.html' else SITE + file_name


def description_of(text, file_name):
    """The page's own meta description, which every other tag repeats."""
    match = re.search(r'<meta name="description" content="([^"]*)">', text)
    if not match:
        raise SystemExit(f'{file_name} has no <meta name="description">; add one first.')
    return html.unescape(match.group(1))


def structured_data(page, description):
    """JSON-LD: the page, the site it belongs to, TESOBE, and for a product page the software itself."""
    url = page_url(page['file'])
    webpage = {'@type': 'WebPage', '@id': url + '#webpage', 'url': url, 'name': page['title'], 'description': description,
               'isPartOf': {'@id': SITE + '#website'}, 'inLanguage': 'en'}
    graph = [
        TESOBE,
        {'@type': 'WebSite', '@id': SITE + '#website', 'url': SITE, 'name': SITE_NAME, 'publisher': {'@id': TESOBE['@id']}, 'inLanguage': 'en'},
        webpage,
    ]
    app = page.get('app')
    if app:
        software = {
            '@type': 'SoftwareApplication',
            '@id': url + '#software',
            'name': app['name'],
            'description': description,
            'url': url,
            'applicationCategory': app['category'],
            'operatingSystem': 'Linux, Docker, Kubernetes',
            'license': LICENCE,
            'author': {'@id': TESOBE['@id']},
            'publisher': {'@id': TESOBE['@id']},
        }
        if app.get('repo'):
            software['sameAs'] = [app['repo']]
        graph.append(software)
        webpage['mainEntity'] = {'@id': url + '#software'}
    return json.dumps({'@context': 'https://schema.org', '@graph': graph}, indent=1, ensure_ascii=False)


def seo_block(page, description):
    """The head tags this script owns, between its markers."""
    url = page_url(page['file'])
    image = SITE + SHARE_IMAGE
    title = html.escape(page['title'], quote=True)
    text = html.escape(description, quote=True)
    return '\n'.join([
        '<!-- seo: written by scripts/update_seo.py; change the page list there, not here -->',
        f'<link rel="canonical" href="{url}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{html.escape(SITE_NAME, quote=True)}">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{text}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{image}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{html.escape(SHARE_IMAGE_ALT, quote=True)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{title}">',
        f'<meta name="twitter:description" content="{text}">',
        f'<meta name="twitter:image" content="{image}">',
        '<script type="application/ld+json">',
        structured_data(page, description),
        '</script>',
        '<!-- /seo -->',
    ])


def update_page(page):
    """Set the title and replace (or add, after the description) the block of tags. Returns the description."""
    path = DOCS / page['file']
    text = path.read_text(encoding='utf-8')
    description = description_of(text, page['file'])
    text = re.sub(r'<title>[^<]*</title>', lambda _: '<title>' + html.escape(page['title'], quote=False) + '</title>', text, count=1)
    block = seo_block(page, description)
    marked = re.compile(r'<!-- seo:.*?<!-- /seo -->', re.S)
    if marked.search(text):
        text = marked.sub(lambda _: block, text, count=1)
    else:
        text = re.sub(r'(<meta name="description" content="[^"]*">)', lambda found: found.group(1) + '\n' + block, text, count=1)
    path.write_text(text, encoding='utf-8')
    return description


def last_changed(file_name, today):
    """The date of the page's last commit, so the sitemap only changes when a page does; today if git cannot say."""
    repo = DOCS.parent
    try:
        found = subprocess.run(
            ['git', '-c', f'safe.directory={repo}', 'log', '-1', '--format=%cs', '--', f'docs/{file_name}'],
            cwd=repo, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        found = ''
    return found or today


def write_sitemap(today):
    rows = '\n'.join(
        f'  <url><loc>{page_url(page["file"])}</loc><lastmod>{last_changed(page["file"], today)}</lastmod></url>' for page in PAGES
    )
    (DOCS / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + '\n</urlset>\n', encoding='utf-8')


def write_robots():
    (DOCS / 'robots.txt').write_text('User-agent: *\nAllow: /\n\nSitemap: ' + SITE + 'sitemap.xml\n', encoding='utf-8')


def write_llms(descriptions):
    """llms.txt: a short Markdown guide to the site for AI tools (https://llmstxt.org)."""
    lines = [f'# {SITE_NAME}', '', f'> {LLMS_SUMMARY}', '']
    if LLMS_DETAILS:
        lines += [LLMS_DETAILS, '']
    groups = []
    for page in PAGES:
        if page['group'] not in groups:
            groups.append(page['group'])
    for group in groups:
        lines += [f'## {group}', '']
        for page in PAGES:
            if page['group'] == group:
                name = page['title'].split(' | ')[0]
                lines.append(f'- [{name}]({page_url(page["file"])}): {descriptions[page["file"]]}')
        lines.append('')
    for heading, links in LLMS_MORE.items():
        lines += [f'## {heading}', '']
        lines += [f'- [{name}]({url}): {text}' for name, url, text in links]
        lines.append('')
    (DOCS / 'llms.txt').write_text('\n'.join(lines), encoding='utf-8')


def main():
    files_on_disk = {path.name for path in DOCS.glob('*.html')}
    listed = {page['file'] for page in PAGES}
    if files_on_disk - listed:
        raise SystemExit('Pages missing from PAGES in scripts/update_seo.py: ' + ', '.join(sorted(files_on_disk - listed)))
    descriptions = {page['file']: update_page(page) for page in PAGES}
    today = datetime.date.today().isoformat()
    write_sitemap(today)
    write_robots()
    write_llms(descriptions)
    print(f'Updated {len(PAGES)} pages, sitemap.xml, robots.txt and llms.txt')


if __name__ == '__main__':
    main()
