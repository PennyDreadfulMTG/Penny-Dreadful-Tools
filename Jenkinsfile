node{
    stage('Clone') {
        checkout scm
    }

    stage("pip") {
        sh 'python3 -m pip install -U --user -r requirements.txt'
    }

    stage('Unit Tests') {
        sh 'PATH=$PATH:~/.local/bin/; pytest --junitxml=test_results.xml || exit 0'
        junit 'test_results.xml'
    }

    stage('Pylint') {
        sh 'PATH=$PATH:~/.local/bin/; pylint -f parseable --rcfile=pylintrc $(find . -name "*.py" -print) | tee pylint.log'
        step([$class: 'WarningsPublisher', canComputeNew: false, canResolveRelativePaths: false, canRunOnFailed: true, excludePattern: '', failedTotalHigh: '0', unstableTotalAll: '0', healthy: '0', includePattern: '', messagesPattern: '', parserConfigurations: [[parserName: 'PyLint', pattern: 'pylint.log']], unHealthy: '10'])
    }
}