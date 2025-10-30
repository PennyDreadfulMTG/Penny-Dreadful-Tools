FROM python:3.10-bookworm
RUN pip install pipenv

RUN apt-get update && \
    apt-get install -y git-lfs

WORKDIR /pdm

COPY Pipfile Pipfile.lock ./
RUN pipenv sync --dev

COPY . .

ENTRYPOINT ["pipenv", "run", "python", "run.py", "--wait-for-db"]
