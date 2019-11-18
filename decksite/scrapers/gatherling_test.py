import os

from bs4 import BeautifulSoup

from decksite.data import competition
from decksite.scrapers import gatherling


def test_top_n() -> None:
    for n in [4, 8]:
        filename = 'gatherling.top{n}.html'.format(n=n)
        soup = get_soup(filename)
        assert competition.Top(n) == gatherling.find_top_n(soup)

def test_get_dt_and_series() -> None:
    dt, competition_series = gatherling.get_dt_and_series('APAC Penny Dreadful Sundays 7.02', '18 February 2018')
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-02-18 07:00'
    assert competition_series == 'APAC Penny Dreadful Sundays'

    dt, competition_series = gatherling.get_dt_and_series('Penny Dreadful Saturdays 1.99', '06 January 2018')
    assert competition_series == 'Penny Dreadful Saturdays'
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-01-06 18:30'

    dt, competition_series = gatherling.get_dt_and_series('Penny Dreadful Sundays 3.03', '07 January 2018')
    assert competition_series == 'Penny Dreadful Sundays'
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-01-07 18:30'

    dt, competition_series = gatherling.get_dt_and_series('Penny Dreadful Mondays 1.01', '08 January 2018')
    assert competition_series == 'Penny Dreadful Mondays'
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-01-09 00:00'

    dt, competition_series = gatherling.get_dt_and_series('Penny Dreadful Thursdays 9.01', '11 January 2018')
    assert competition_series == 'Penny Dreadful Thursdays'
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-01-12 00:00'

def test_rankings() -> None:
    soup = get_soup('gatherling.top4.html')
    rankings = gatherling.rankings(soup)
    assert len(rankings) == 13
    assert rankings[0] == 'Gleiciano'
    assert rankings[1] == 'bakert99'
    assert rankings[2] == 'BoozeMongoose'
    assert rankings[3] == 'mandrakata'
    assert rankings[4] == 'Sora_Aoi'
    assert rankings[5] == 'Rakura'
    assert rankings[6] == 'jackslagel'
    assert rankings[7] == 'Yuin'
    assert rankings[8] == 'Nangurus'
    assert rankings[9] == 'ViralExploit'
    assert rankings[10] == 'BigM'
    assert rankings[11] == 'j_meka'
    assert rankings[12] == 'MasterKulon'

    soup = get_soup('gatherling.top8.html')
    rankings = gatherling.rankings(soup)
    assert len(rankings) == 27
    assert rankings[0] == 'bakert99'
    assert rankings[1] == 'FSkura'
    assert rankings[2] == 'johnniebegoode'
    assert rankings[3] == 'ribbonsofnight'
    assert rankings[4] == 'Briar_moss'
    assert rankings[5] == 'NightHawk521'
    assert rankings[6] == 'pixywing'
    assert rankings[7] == 'DDCTyler'
    assert rankings[8] == 'BigM'
    assert rankings[9] == 'R1ncewind'
    assert rankings[10] == 'Landonpeanut'
    assert rankings[11] == 'zannzuchii'
    assert rankings[12] == 'j_meka'
    assert rankings[13] == 'BrunoDogma'
    assert rankings[14] == 'pumpkinwavy'
    assert rankings[15] == 'Yuin'
    assert rankings[16] == 'crazybaloth'
    assert rankings[17] == 'MrSad'
    assert rankings[18] == 'insan3_'
    assert rankings[19] == 'Renner'
    assert rankings[20] == 'Daesik'
    assert rankings[21] == 'MetalAtog'
    assert rankings[22] == 'murilobds'
    assert rankings[23] == 'Ingrid'
    assert rankings[24] == 'CrimsonMage'
    assert rankings[25] == 'MinnieThree'
    assert rankings[26] == 'HugoCalean'

    soup = get_soup('gatherling.drop.html')
    rankings = gatherling.rankings(soup)
    assert len(rankings) == 14
    assert rankings[0] == 'The_Wolf'
    assert rankings[1] == 'jackslagel'
    assert rankings[2] == 'jenkin5630'
    assert rankings[3] == 'Rooby_Roo'
    assert rankings[4] == 'yellowvanblake'
    assert rankings[5] == 'j_meka'
    assert rankings[6] == 'octopusjelly'
    assert rankings[7] == 'littanana'
    assert rankings[8] == 'Merawder'
    assert rankings[9] == 'SafetyDad'
    assert rankings[10] == 'Pseudomocha'
    assert rankings[11] == 'ThrivingTurtle'
    assert rankings[12] == 'silasary'
    assert rankings[13] == 'prestontiger3'

def test_medal_winners() -> None:
    html = get_html('gatherling.top4.html')
    winners = gatherling.medal_winners(html)
    assert winners['Gleiciano'] == 1
    assert winners['BoozeMongoose'] == 2
    assert winners['bakert99'] == 3
    assert winners['mandrakata'] == 3

    html = get_html('gatherling.top8.html')
    winners = gatherling.medal_winners(html)
    assert winners['FSkura'] == 1
    assert winners['ribbonsofnight'] == 2
    assert winners['bakert99'] == 3
    assert winners['johnniebegoode'] == 3
    assert winners['Briar_moss'] == 5
    assert winners['DDCTyler'] == 5
    assert winners['NightHawk521'] == 5
    assert winners['pixywing'] == 5

    html = get_html('gatherling.drop.html')
    winners = gatherling.medal_winners(html)
    assert winners['yellowvanblake'] == 1
    assert winners['Rooby_Roo'] == 2
    assert winners['jackslagel'] == 3
    assert winners['The_Wolf'] == 3

def test_finishes() -> None:
    fs = gatherling.finishes({'e': 1, 'b': 2, 'c': 3, 'd': 4}, ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'])
    assert fs['a'] == 5
    assert fs['b'] == 2
    assert fs['c'] == 3
    assert fs['d'] == 4
    assert fs['e'] == 1
    assert fs['f'] == 6
    assert fs['g'] == 7
    assert fs['h'] == 8

def get_html(filename: str) -> str:
    path = '{path}/{filename}'.format(path=os.path.dirname(__file__), filename=filename)
    with open(path, 'r') as f:
        return f.read()

def get_soup(filename: str) -> BeautifulSoup:
    page = get_html(filename)
    return BeautifulSoup(page, 'html.parser')
