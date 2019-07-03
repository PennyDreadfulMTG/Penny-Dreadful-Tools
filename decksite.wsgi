try:
    from decksite import main, api, APP as application
except Exception as e:
    from shared import repo
    repo.create_issue(f'Error starting decksite', 'decksite', 'decksite', 'PennyDreadfulMTG/perf-reports', exception=e)

if __name__ == '__main__':
    print('Running manually.  Is something wrong?')
    application.run(host='0.0.0.0', debug=False)
