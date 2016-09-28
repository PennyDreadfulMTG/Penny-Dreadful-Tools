stage('Clone') {
  checkout scm
}

stage("pip") {
  sh 'python3 -m pip install -U --user discord.py'
  sh 'python3 -m pip install -U --user pytest'
}

stage('Unit Tests') {
  sh 'PATH=$PATH:~/.local/bin/; pytest'
}