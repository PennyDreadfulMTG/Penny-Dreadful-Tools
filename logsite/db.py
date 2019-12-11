from typing import Optional

import peewee
import peeweedbevolve # pylint: disable=unused-import
from flask import url_for
from playhouse import db_url

from . import APP

# pylint: disable=no-member

DB = db_url.connect(APP.config['DATABASE_URI'])

class BaseModel(peewee.Model):
    class Meta:
        database = DB

class User(BaseModel):
    id = peewee.AutoField()
    name = peewee.CharField(unique=True)
    discord_id = peewee.CharField(null=True)

    def url(self) -> str:
        return url_for('show_person', person=self.name)

class Format(BaseModel):
    id = peewee.AutoField()
    name = peewee.CharField(max_length=40, unique=True)
    friendly_name = peewee.CharField(max_length=40)

    def get_name(self) -> str:
        if self.friendly_name:
            return self.friendly_name
        return self.name

class Module(BaseModel):
    id = peewee.AutoField()
    name = peewee.CharField(max_length=50)

def get_format(name: str) -> Optional[Format]:
    return Format.get_or_none(Format.name == name)

def get_or_insert_format(name: str) -> Format:
    return Format.get_or_create(name=name)[0]

def get_or_insert_module(name: str) -> Module:
    return Module.get_or_create(name=name)[0]

def get_or_insert_user(name: str) -> User:
    return User.get_or_create(name=name)[0]
