import json, urllib.request

from pkg_resources import parse_version

class Fetcher():
  def legal_cards(self):
    return [s.lower() for s in self.open('http://pdmtgo.com/legal_cards.txt', 'latin-1').split('\n')]

  def version(self):
    return parse_version(json.loads(self.open('https://mtgjson.com/json/version.json')))

  def all_cards(self):
    return json.loads(self.open('https://mtgjson.com/json/AllCards.json'))

  def open(self, url, character_encoding = 'utf-8'):
    print("Fetching " + url)
    return urllib.request.urlopen(url).read().decode(character_encoding)
