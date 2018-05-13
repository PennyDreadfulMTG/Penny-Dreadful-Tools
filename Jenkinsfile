node{
    def FailedTests = false

    stage('Clone') {
        sh 'git config user.email "jenkins@katelyngigante.com"'
        sh 'git config user.name "Vorpal Buildbot"'
        checkout scm
    }

    stage("pip") {
        sh 'python3 -m pip install -U --user -r requirements.txt'
    }

    stage('Integration Tests') {
        env.test_vcr_record_mode = 'all'
        env.mysql_user = 'jenkins'
        env.magic_database = 'jenkins_cards'
        env.decksite_database = 'jenkins_decksite'
        FailedTests = sh(returnStatus: true, script: 'python3 dev.py tests -m "functional"')
    }

    stage('Pylint') {
        // sh 'PATH=$PATH:~/.local/bin/; make lint | tee pylint.log'
        // step([$class: 'WarningsPublisher', canComputeNew: false, canResolveRelativePaths: false, canRunOnFailed: true, excludePattern: '', failedTotalHigh: '0', unstableTotalAll: '0', healthy: '0', includePattern: '', messagesPattern: '', parserConfigurations: [[parserName: 'PyLint', pattern: 'pylint.log']], unHealthy: '10'])
    }

    stage('Update Readme') {
        readme = sh(returnStatus: true, script: 'python3 generate_readme.py')
        if (readme) {
            FailedTests = true
        }
    }

    stage('Fix') {
        if (FailedTests) {
            sh(returnStatus: true, script: 'git branch -d jenkins_results')
            sh 'git checkout -b jenkins_results'
            sh 'git commit -am "Automated update"'
            sh 'git push'
        }
    }
}
