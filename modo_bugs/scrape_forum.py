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

    posts = fetcher.get_forum_posts('https://forums.mtgo.com/index.php?forums/bug-reports.16/')
    for p in posts:
        if p.label is not None:
            is_tracked = False
            if p.url in bugs:
                is_tracked = True

            if not p.url in known and not is_tracked:
                fetcher.forum_to_discord(p)
            known[p.url] = {'title': p.title, 'url': p.url, 'status': p.label, 'tracked': is_tracked}

    with open('forums.json', 'w') as fp:
        json.dump(known, fp, indent=2)