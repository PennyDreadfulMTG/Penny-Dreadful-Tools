from flask import url_for

from decksite import APP

def menu():
    m = []
    urls = sorted([url_for(rule.endpoint) for rule in APP.url_map.iter_rules() if 'GET' in rule.methods and rule.rule.startswith('/admin')])
    for url in urls:
        name = url.replace('/admin/', '').strip('/')
        name = name if name else 'Admin Home'
        m.append({'name': name, 'url': url})
    return m
