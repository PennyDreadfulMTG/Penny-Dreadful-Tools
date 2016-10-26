node{
    def FailedTests = false
    
    stage('Clone') {
        checkout scm
    }

    stage("pip") {
        sh 'python3 -m pip install -U --user -r requirements.txt'
    }

    stage("Spellfix1") {
        if (!fileExists('spellfix.so')) {
            sh 'pip install --user https://github.com/rogerbinns/apsw/releases/download/3.14.1-r1/apsw-3.14.1-r1.zip --global-option=fetch --global-option=--version --global-option=3.14.1 --global-option=--all --global-option=build --global-option=--enable-all-extensions'
            sh 'curl http://sqlite.org/cgi/src/raw/ext/misc/spellfix.c?name=a4723b6aff748a417b5091b68a46443265c40f0d -o spellfix.c'
            sh 'curl http://sqlite.org/cgi/src/raw/src/sqlite3ext.h?name=8648034aa702469afb553231677306cc6492a1ae -o sqlite3ext.h'
            sh 'curl http://sqlite.org/cgi/src/raw/src/sqlite.h.in?name=2683a291ed8db5228024267be6421f0de507b80e -o sqlite3.h'
            sh 'gcc -fPIC -shared spellfix.c -o spellfix.so'
        }
    }
    
    stage('Unit Tests') {
        FailedTests = sh(returnStatus: true, script: 'PATH=$PATH:~/.local/bin/; pytest --junitxml=test_results.xml')
        junit 'test_results.xml'
    }

    stage('Pylint') {
        sh 'PATH=$PATH:~/.local/bin/; pylint -f parseable --rcfile=pylintrc $(find . -name "*.py" -print) | tee pylint.log'
        step([$class: 'WarningsPublisher', canComputeNew: false, canResolveRelativePaths: false, canRunOnFailed: true, excludePattern: '', failedTotalHigh: '0', unstableTotalAll: '0', healthy: '0', includePattern: '', messagesPattern: '', parserConfigurations: [[parserName: 'PyLint', pattern: 'pylint.log']], unHealthy: '10'])
    }

    if (FailedTests) {
        error 'Failed a test'
    }

    stage('Update Readme') {
        readme = sh(returnStatus: true, script: 'python3 generate_readme.py')
        if (readme) {
            error "The readme is out of date."
        }
    }
}