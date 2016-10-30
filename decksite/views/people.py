from flask import url_for

from decksite.view import View

# pylint: disable=no-self-use
class People(View):
    def __init__(self, people):
        self.people = people
        for person in self.people:
            person.url = url_for('person', person_id=person.id)


    def subtitle(self):
        return 'People'
