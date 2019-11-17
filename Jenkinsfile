node{
    def FailedTests = false
    def DoNotMerge = false
    def POUpdated = false
    env.mysql_user = 'jenkins'
    env.magic_database = 'jenkins_cards'
    env.decksite_database = 'jenkins_decksite'
    env.logsite_database = 'jenkins_logsite'
    env.redis_db = '9'
    // env.save_historic_legal_lists = 'True'

    stage('Clone') {
        sh 'git config user.email "jenkins@katelyngigante.com"'
        sh 'git config user.name "Vorpal Buildbot"'
        checkout scm
    }

    stage("pip") {
        sh 'python3 -m pip install -U --user -r requirements.txt'
    }

    stage('reset_db') {
        sh 'python3 dev.py reset_db'
    }

    stage('External Data Tests') {
        // sh 'rm decksite/scrapers/test_*.yaml'
        // FailedTests = sh(returnStatus: true, script: 'python3 dev.py tests -m "external"')
        // if (FailedTests) {
        //     // Check if files are still there
        //     sh(returnStatus: true, script: 'git reset --hard HEAD')
        // }
        // else {
        //     // Don't update the scraper recordings unless they failed.
        //     sh(returnStatus: true, script: 'git reset --hard HEAD')
        //     // DoNotMerge = true
        // }
    }

    // stage('Pylint') {
    //     sh 'PATH=$PATH:~/.local/bin/; make lint | tee pylint.log'
    //     step([$class: 'WarningsPublisher', canComputeNew: false, canResolveRelativePaths: false, canRunOnFailed: true, excludePattern: '', failedTotalHigh: '0', unstableTotalAll: '0', healthy: '0', includePattern: '', messagesPattern: '', parserConfigurations: [[parserName: 'PyLint', pattern: 'pylint.log']], unHealthy: '10'])
    // }

    stage('Update Readme') {
        readme = sh(returnStatus: true, script: 'python3 generate_readme.py')
        if (readme) {
            FailedTests = true
        }
    }

    stage('Translations') {
        withCredentials([string(credentialsId: 'poeditor_api_key', variable: 'poeditor_api_key')]) {
            po_updated = sh(returnStatus: true, script: 'python3 run.py maintenance generate_translations')
        }
        if (po_updated) {
            POUpdated = true
        }
    }

    stage('JS deps') {
        sh(returnStatus: true, script: 'python3 run.py maintenance client_dependencies')
    }


    stage('Fix') {
        if (FailedTests || POUpdated) {
            sh(returnStatus: true, script: 'git branch -D jenkins_results')
            sh 'git checkout -b jenkins_results'
            if (!FailedTests) {
                sh 'git commit -am "Update POFile"'
            }
            else {
                sh 'git commit -am "Automated update"'
            }
            withCredentials([usernamePassword(credentialsId: 'd61f34a1-4929-406d-b4c5-ec380d823780', passwordVariable: 'github_password', usernameVariable: 'github_user')]) {
                sh 'git push https://$github_user:$github_password@github.com/PennyDreadfulMTG/Penny-Dreadful-Tools.git jenkins_results --force'
            }
            sleep(30) // Lovely race condition where we make a PR before the push has propogated.
            cmd = 'hub pull-request -b master -h jenkins_results -f'
            if (!FailedTests && POUpdated) {
                cmd = cmd + ' -m "Update POFile"'
            }
            else {
                cmd = cmd + ' -m "Automated PR from Jenkins"'
            }
            if (DoNotMerge) {
                cmd = cmd + ' -l "do not merge"'
            }
            sh(returnStatus: true, script: cmd)
        }
    }
}
