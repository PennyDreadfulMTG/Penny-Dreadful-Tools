from shared import fetch_tools


def main() -> None:
    their_bugs = fetch_tools.fetch_json('https://raw.githubusercontent.com/PennyDreadfulMTG/modo-bugs/master/forums.json')
    their_untracked_bugs = [bug for bug in their_bugs.values() if not bug['tracked'] and bug['status'] not in ['Fixed', 'Not A Bug', 'No Fix Planned', 'Could Not Reproduce']]
    our_bugs = fetch_tools.fetch_json('https://raw.githubusercontent.com/PennyDreadfulMTG/modo-bugs/master/bugs.json')
    our_untracked_bugs = [bug for bug in our_bugs if not bug['support_thread']]
    print('= Possible missing linkage:\n')
    for our_bug in our_untracked_bugs:
        for their_bug in their_untracked_bugs:
            if our_bug['card'] in their_bug['title']:
                print('Maybe\n', our_bug['description'], '\nis tracked by them as\n', their_bug['title'])
                print(their_bug['url'])
                print(our_bug['url'] + '\n')
    print("= All of their bugs we aren't tracking:\n")
    for their_bug in their_untracked_bugs:
        print(f'[{their_bug["status"]}] {their_bug["title"]}\n{their_bug["url"]}\n')
    print("= All of our bugs they aren't tracking:\n")
    for our_bug in our_untracked_bugs:
        print(f'[{our_bug["card"]}] {our_bug["description"]}\n{our_bug["url"]}\n')


if __name__ == '__main__':
    main()
