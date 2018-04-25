from typing import Any

import sqlalchemy as sa
from flask import url_for
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.exc import MultipleResultsFound

from shared import configuration

from . import APP

# pylint: disable=no-member

APP.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
APP.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://{user}:{password}@{host}:{port}/{db}'.format(
    user=configuration.get('mysql_user'),
    password=configuration.get('mysql_passwd'),
    host=configuration.get('mysql_host'),
    port=configuration.get('mysql_port'),
    db=configuration.get('logsite_database'))

DB = SQLAlchemy(APP) # type: ignore
MIGRATE = Migrate(APP, DB)

MATCH_PLAYERS = DB.Table('match_players',
                         DB.Column('match_id', DB.Integer, DB.ForeignKey('match.id'), primary_key=True),
                         DB.Column('user_id', DB.Integer, DB.ForeignKey('user.id'), primary_key=True)
                        )

MATCH_MODULES = DB.Table('match_modules',
                         DB.Column('match_id', DB.Integer, DB.ForeignKey('match.id'), primary_key=True),
                         DB.Column('module_id', DB.Integer, DB.ForeignKey('module.id'), primary_key=True)
                        )

class User(DB.Model): # type: ignore
    __tablename__ = 'user'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(60))
    discord_id = sa.Column(sa.String(200))

    def url(self):
        return url_for('show_person', person=self.name)

class Format(DB.Model): # type: ignore
    __tablename__ = 'format'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(40))
    friendly_name = sa.Column(sa.String(40))

    def get_name(self):
        if self.friendly_name:
            return self.friendly_name
        return self.name

class Module(DB.Model): # type: ignore
    __tablename__ = 'module'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(50))

# pylint: disable=invalid-name
def Commit() -> None:
    return DB.session.commit()

# pylint: disable=invalid-name
def Add(item: Any) -> None:
    return DB.session.add(item)

# pylint: disable=invalid-name
def Merge(item) -> None:
    return DB.session.merge(item)

# pylint: disable=invalid-name
def Delete(item) -> None:
    return DB.session.delete(item)

def get_or_insert_format(name: str) -> Format:
    local = Format.query.filter_by(name=name).one_or_none()
    if local is not None:
        return local
    local = Format(name=name)
    Add(local)
    Commit()
    return local

def get_or_insert_module(name: str) -> Module:
    local = Module.query.filter_by(name=name).one_or_none()
    if local is not None:
        return local
    local = Module(name=name)
    Add(local)
    Commit()
    return local

def get_or_insert_user(name: str) -> User:
    try:
        local = User.query.filter_by(name=name).one_or_none()
        if local is not None:
            return local
        local = User(name=name)
        Add(local)
        Commit()
        return local
    except MultipleResultsFound:
        query = User.query.filter_by(name=name)
        # todo: Merge errant entry
        return query.first()
