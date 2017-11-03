node{
    def FailedTests = false
    
    stage('Clone') {
        checkout scm
    }

    stage("pip") {
        sh 'python3 -m pip install -U --user -r requirements.txt'
        sh 'python3 -m pip install -U --user codacy-coverage'
    }

    stage('Unit Tests') {
        echo 'Unit tests run on travis now.'
    }

    stage('Pylint') {
        sh 'PATH=$PATH:~/.local/bin/; make lint | tee pylint.log'
        step([$class: 'WarningsPublisher', canComputeNew: false, canResolveRelativePaths: false, canRunOnFailed: true, excludePattern: '', failedTotalHigh: '0', unstableTotalAll: '0', healthy: '0', includePattern: '', messagesPattern: '', parserConfigurations: [[parserName: 'PyLint', pattern: 'pylint.log']], unHealthy: '10'])
    }

    // stage('Update Readme') {
    //     readme = sh(returnStatus: true, script: 'python3 generate_readme.py')
    //     if (readme) {
    //         echo 'The readme files are out of date.  Run generate_readme.py'
    //         error 'The readme is out of date.'
    //     }
    // }
}