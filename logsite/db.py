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

db = SQLAlchemy(APP) # type: ignore
migrate = Migrate(APP, db)

match_players = db.Table('match_players',
                         db.Column('match_id', db.Integer, db.ForeignKey('match.id'), primary_key=True),
                         db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
                        )

match_modules = db.Table('match_modules',
                         db.Column('match_id', db.Integer, db.ForeignKey('match.id'), primary_key=True),
                         db.Column('module_id', db.Integer, db.ForeignKey('module.id'), primary_key=True)
                        )

class User(db.Model): # type: ignore
    __tablename__ = 'user'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(60))
    discord_id = sa.Column(sa.String(200))

    def url(self):
        return url_for('show_person', person=self.name)

class Format(db.Model): # type: ignore
    __tablename__ = 'format'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(40))
    friendly_name = sa.Column(sa.String(40))

    def get_name(self):
        if self.friendly_name:
            return self.friendly_name
        return self.name

class Module(db.Model):
    __tablename__ = 'module'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(50))

def Commit() -> None:
    return db.session.commit()

def Add(item: Any) -> None:
    return db.session.add(item)

def Merge(item):
    return db.session.merge(item)

def Delete(item):
    return db.session.delete(item)

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
