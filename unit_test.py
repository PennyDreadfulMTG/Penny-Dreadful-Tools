import os
import bot

def test_imagedownload():
    filepath = bot.config.get("image_dir") + "/" + "island.jpg" 
    if (bot.acceptable_file(filepath)):
      os.remove(filepath)
    assert bot.download_image("Island", 0) != None

