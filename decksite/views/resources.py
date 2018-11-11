from typing import List

from mypy_extensions import TypedDict

from decksite.view import View
from magic import fetcher

ResourceDescription = TypedDict('ResourceDescription',
                                {
                                    'text': str,
                                    'url': str,
                                    'is_external': bool,
                                })
SectionDescription = TypedDict('SectionDescription',
                               {
                                   'title': str,
                                   'items': List[ResourceDescription],
                               })

# pylint: disable=no-self-use
class Resources(View):
    def sections(self):
        raw_resources = fetcher.resources()
        sections: List[SectionDescription] = []
        for title, raw_section in raw_resources.items():
            section: SectionDescription = {'title': title, 'items': []}
            sections.append(section)
            for text, url in raw_section.items():
                item: ResourceDescription = {'text': text, 'url': url, 'is_external': url.startswith('http') and '://pennydreadfulmagic.com/' not in url}
                section['items'].append(item)
        return sections

    def page_title(self) -> str:
        return 'Resources'
