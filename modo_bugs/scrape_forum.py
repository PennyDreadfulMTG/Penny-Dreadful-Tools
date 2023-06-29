import json
import os

from . import fetcher


def main() -> None:
    known = {}
    if os.path.exists('forums.json'):
        with open('forums.json', 'r') as fp:
            known = json.load(fp)

    with open('bugs.json') as f:
        bugs = f.read()

    posts = fetcher.get_forum_posts('https://forums.mtgo.com/index.php?forums/bug-reports.16/', True)
    checked = [p.url for p in posts]
    bad = []
    for p in posts:
        if p.label is not None:
            is_tracked = False
            if p.url in bugs:
                is_tracked = True

            if p.url not in known and not is_tracked:
                fetcher.forum_to_discord(p)
            known[p.url] = {'title': p.title, 'url': p.url, 'status': p.label, 'tracked': is_tracked}

    for url, k in known.items():
        if not k['tracked']:
            if url in bugs:
                k['tracked'] = True
        if url not in checked and k['status'] not in ['Fixed', 'Not A Bug', 'No Fix Planned']:
            k['status'] = fetcher.get_daybreak_label(url)
            if k['status'] is None:
                bad.append(url)

    for url in bad:
        del known[url]

    with open('forums.json', 'w') as fp:
        json.dump(known, fp, indent=2)
