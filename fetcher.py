import json, os, shutil, urllib.request, zipfile

from pkg_resources import parse_version

class Fetcher():
  def legal_cards(self):
    return [s.lower() for s in self.open('http://pdmtgo.com/legal_cards.txt', 'latin-1').split('\n')]

  def version(self):
    return parse_version(json.loads(self.open('https://mtgjson.com/json/version.json')))

  def mtgo_status(self):
    return json.loads(self.open('https://magic.wizards.com/sites/all/modules/custom/wiz_services/mtgo_status.php'))['status']

  def all_cards(self):
    if os.path.isdir('./ziptemp'):
      shutil.rmtree('./ziptemp')

    os.mkdir('./ziptemp')
    urllib.request.urlretrieve('https://mtgjson.com/json/AllCards.json.zip', './ziptemp/AllCards.json.zip')
    allcards_zip = zipfile.ZipFile('./ziptemp/AllCards.json.zip', 'r')
    allcards_zip.extractall('./ziptemp/unzip')
    allcards_zip.close()
    allcards_json = json.load(open('./ziptemp/unzip/AllCards.json', encoding='utf-8'))
    shutil.rmtree('./ziptemp')
    return allcards_json

  def open(self, url, character_encoding = 'utf-8'):
    print("Fetching {0}".format(url))
    return urllib.request.urlopen(url).read().decode(character_encoding)
