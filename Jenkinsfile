node {
    stage('Clone') {
      checkout scm
    }

    stage("pip") {
    sh 'python3 -m pip install -U --user discord.py'
    sh 'python3 -m pip install -U --user mtgsdk'
    sh 'python3 -m pip install -U --user pytest'
    }

    stage('Unit Tests') {
      sh '~/.local/bin/pytest'
    }
}
