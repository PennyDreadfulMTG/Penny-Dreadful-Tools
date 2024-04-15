from typing import TypedDict

from decksite.view import View
from magic import fetcher

class ResourceDescription(TypedDict):
    text: str
    url: str
    is_external: bool
class SectionDescription(TypedDict):
    title: str
    items: list[ResourceDescription]

class Resources(View):
    def sections(self) -> list[SectionDescription]:
        raw_resources = fetcher.resources()
        sections: list[SectionDescription] = []
        for title, raw_section in raw_resources.items():
            section: SectionDescription = {'title': title, 'items': []}
            sections.append(section)
            for text, url in raw_section.items():
                item: ResourceDescription = {'text': text, 'url': url, 'is_external': url.startswith('http') and '://pennydreadfulmagic.com/' not in url}
                section['items'].append(item)
        return sections

    def page_title(self) -> str:
        return 'Resources'
