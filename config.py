import json

class Config:
  defaults = {
    "database": "./db"
    "image_dir": "."
  }

  def __init__(self):
    try:
      self.config = json.load(open("config.json"))
    except FileNotFoundError:
      self.config = {}

  def get(self, key):
    if key in self.config:
      return self.config[key]
    return Config.defaults[key]

