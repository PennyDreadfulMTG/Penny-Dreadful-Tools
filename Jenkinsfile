node{
    stage('Clone') {
        checkout scm
    }

    stage("pip") {
        sh 'python3 -m pip install -U --user discord.py'
        sh 'python3 -m pip install -U --user pytest'
        sh 'python3 -m pip install -U --user pylint'
    }

    stage('Unit Tests') {
        sh 'PATH=$PATH:~/.local/bin/; pytest --junitxml=test_results.xml'
        junit 'test_results.xml'
    }

    stage('Pylint') {
        sh 'PATH=$PATH:~/.local/bin/; pylint --rcfile=pylintrc $(find . -name "*.py" -print) | tee pylint.log'
        step([$class: 'WarningsPublisher', canComputeNew: false, canResolveRelativePaths: false, canRunOnFailed: true, defaultEncoding: '', excludePattern: '', failedTotalAll: '0', failedTotalHigh: '0', failedTotalLow: '0', failedTotalNormal: '0', healthy: '0', includePattern: '', messagesPattern: '', parserConfigurations: [[parserName: 'PyLint', pattern: 'pylint.log']], unHealthy: '10'])
    }
}