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
    sh 'PATH=$PATH:~/.local/bin/; pylint --rcfile=pylintrc $(find . -maxdepth 1 -name "*.py" -print) || exit 0'
    step([$class: 'WarningsPublisher', canResolveRelativePaths: false, consoleParsers: [[parserName: 'PyLint']], defaultEncoding: '', excludePattern: '', failedTotalAll: '0', healthy: '', includePattern: '', messagesPattern: '', unHealthy: '', useStableBuildAsReference: true])

    }
}