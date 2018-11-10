from decksite.view import View
from magic import fetcher


# pylint: disable=no-self-use
class Resources(View):
    def sections(self):
        raw_resources = fetcher.resources()
        sections = []
        for title, raw_section in raw_resources.items():
            section = {'title': title, 'items': []}
            sections.append(section)
            for text, url in raw_section.items():
                item = {'text': text, 'url': url, 'is_external': url.startswith('http') and '://pennydreadfulmagic.com/' not in url}
                section['items'].append(item)
        return sections

    def page_title(self) -> str:
        return 'Resources'
