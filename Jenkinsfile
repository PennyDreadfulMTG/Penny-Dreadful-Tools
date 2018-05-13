node{
    def FailedTests = false
    env.mysql_user = 'jenkins'
    env.magic_database = 'jenkins_cards'
    env.decksite_database = 'jenkins_decksite'
    env.logsite_database = 'jenkins_logsite'

    stage('Clone') {
        sh 'git config user.email "jenkins@katelyngigante.com"'
        sh 'git config user.name "Vorpal Buildbot"'
        checkout scm
    }

    stage("pip") {
        sh 'python3 -m pip install -U --user -r requirements.txt'
    }

    stage('External Data Tests') {
        FailedTests = sh(returnStatus: true, script: 'python3 dev.py tests -m "external"')
        if (!FailedTests) {
            // Don't update the scraper recordings unless they failed.
            sh(returnStatus: true, script: 'git reset --hard HEAD')
        }
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
            sh(returnStatus: true, script: 'git branch -D jenkins_results')
            sh 'git checkout -b jenkins_results'
            sh 'git commit -am "Automated update"'
            withCredentials([usernamePassword(credentialsId: 'd61f34a1-4929-406d-b4c5-ec380d823780', passwordVariable: 'github_password', usernameVariable: 'github_user')]) {
                sh 'git push https://$github_user:$github_password@github.com/PennyDreadfulMTG/Penny-Dreadful-Tools.git jenkins_results --force'
            }
        }
    }
}
