import logging

from decksite.data import playability
from shared import fetch_tools

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)


# A little script to run to try and marry up our (modo-bugs) bugs with their (Darybreak MTGO bug form) bugs

def main() -> None:
    their_bugs = fetch_tools.fetch_json('https://raw.githubusercontent.com/PennyDreadfulMTG/modo-bugs/master/forums.json')
    their_untracked_bugs = [bug for bug in their_bugs.values() if not bug['tracked'] and bug['status'] not in ['Fixed', 'Not A Bug', 'No Fix Planned', 'Could Not Reproduce']]
    our_bugs = fetch_tools.fetch_json('https://raw.githubusercontent.com/PennyDreadfulMTG/modo-bugs/master/bugs.json')
    our_untracked_bugs = [bug for bug in our_bugs if not bug['support_thread']]
    logger.info('= Possible missing linkage:\n')
    for our_bug in our_untracked_bugs:
        for their_bug in their_untracked_bugs:
            if our_bug['card'] in their_bug['title']:
                logger.info('Maybe')
                logger.info(our_bug['description'])
                logger.info('is tracked by them as')
                logger.info(their_bug['title'])
                logger.info(their_bug['url'])
                logger.info(our_bug['url'] + '\n')
    logger.info(f"= All of their bugs we aren't tracking ({len(their_untracked_bugs)}):\n")
    for their_bug in their_untracked_bugs:
        logger.info(f'[{their_bug["status"]}] {their_bug["title"]}\n{their_bug["url"]}\n')
    logger.info(f"= All of our bugs they aren't tracking ({len(our_untracked_bugs)}):\n")
    ranks = playability.rank()
    our_untracked_bugs.sort(key=lambda bug: (not bug['pd_legal'], ranks.get(bug['card'], float('inf')) or float('inf')))
    for our_bug in our_untracked_bugs:
        logger.info(f'[{our_bug["card"]}][{"LEGAL" if our_bug["pd_legal"] else "NOT LEGAL"}][Rank {ranks.get(our_bug["card"], float("inf"))}] {our_bug["description"]}\n{our_bug["url"]}\n')


if __name__ == '__main__':
    main()
