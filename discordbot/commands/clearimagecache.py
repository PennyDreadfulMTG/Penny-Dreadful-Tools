import glob
import os

from interactions import check, is_owner
from interactions.models import slash_command

from discordbot.command import MtgContext
from shared import configuration


@slash_command('clearimagecache')  # type: ignore
@check(is_owner())
async def clearimagecache(ctx: MtgContext) -> None:
    """Deletes all the cached images.  Use sparingly"""
    image_dir = configuration.get('image_dir')
    if not image_dir:
        await ctx.send('Cowardly refusing to delete from unknown image_dir.')
        return
    files = glob.glob('{dir}/*.jpg'.format(dir=image_dir))
    for file in files:
        os.remove(file)
    await ctx.send('{n} cleared.'.format(n=len(files)))
