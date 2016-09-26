import json, urllib.request

from pkg_resources import parse_version

class Fetcher():
  def version(self):
    return parse_version(json.loads(self.open('https://mtgjson.com/json/version.json')))

  def all_cards(self):
    return json.loads(self.open('https://mtgjson.com/json/AllCards.json'))

  def open(self, url):
    print("Fetching " + url)
    return urllib.request.urlopen(url).read().decode("utf-8")
