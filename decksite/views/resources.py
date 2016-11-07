import json

from magic import fetcher

from decksite.view import View

# pylint: disable=no-self-use
class Resources(View):
    def sections(self):
        raw_resources = fetcher.resources()
        sections = []
        for title, raw_section in raw_resources.items():
            section = {'title': title, 'items': []}
            sections.append(section)
            for text, url in raw_section.items():
                item = {'text': text, 'url': url}
                section['items'].append(item)
        return sections

    def subtitle(self):
        return 'Resources'
