from typing import Optional

import peewee
from flask import url_for
from playhouse import db_url
import peeweedbevolve

from . import APP

# pylint: disable=no-member

DB = db_url.connect(APP.config['DATABASE_URI'])

class BaseModel(peewee.Model):
    class Meta:
        database = DB

class MatchPlayers(BaseModel):
    match_id = peewee.DeferredForeignKey('Match')
    user_id = peewee.DeferredForeignKey('User')


class MatchModules(BaseModel):
    match_id = peewee.DeferredForeignKey('Match')
    user_id = peewee.DeferredForeignKey('Module')

class User(BaseModel): # type: ignore
    id = peewee.AutoField()
    name = peewee.CharField(max_length=60, unique=True)
    discord_id = peewee.CharField(max_length=200)

    def url(self) -> str:
        return url_for('show_person', person=self.name)

class Format(BaseModel): # type: ignore
    id = peewee.AutoField()
    name = peewee.CharField(max_length=40, unique=True)
    friendly_name = peewee.CharField(max_length=40)

    def get_name(self) -> str:
        if self.friendly_name:
            return self.friendly_name
        return self.name

class Module(BaseModel): # type: ignore
    id = peewee.AutoField()
    name = peewee.CharField(max_length=50)

# def commit() -> None:
#     return DB.session.commit()

# def add(item: Any) -> None:
#     return DB.session.add(item)

# def merge(item: Any) -> None:
#     return DB.session.merge(item)

# def delete(item: Any) -> None:
#     return DB.session.delete(item)

def get_format(name: str) -> Optional[Format]:
    return Format.get_or_none(Format.name == name)

def get_or_insert_format(name: str) -> Format:
    return Format.get_or_create(name=name)[0]

def get_or_insert_module(name: str) -> Module:
    return Module.get_or_create(name=name)[0]

def get_or_insert_user(name: str) -> User:
    return User.get_or_create(name=name)[0]
