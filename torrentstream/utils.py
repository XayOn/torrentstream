from random import randint
import asyncio
import os
from torrentstream import stream_torrent
from torrentstream.torrent import Torrent


async def play_file(loop, file):
    """
        Launch player against file
        player is adquired from the PLAYER environment variable
    """
    player = os.getenv('PLAYER')
    if player:
        process = await asyncio.create_subprocess_exec(
            player, file.path)
        await process.wait()


def await_stream(magnet):
    """ Stream torrent"""

    def first_file(files):
        """ Get first file"""
        def is_media(file_):
            e = [".webm", ".mkv", ".flv", ".vob", ".ogv,", ".ogg",
                 ".drc", ".gif", ".gifv", ".mng", ".avi", ".mov,", ".qt",
                 ".wmv", ".yuv", ".rm", ".rmvb", ".asf", ".amv", ".mp4,",
                 ".m4p", "(with", "DRM),", ".m4v", ".mpg,", ".mp2,",
                 ".mpeg,", ".mpe,", ".mpv", ".mpg,", ".mpeg,", ".m2v", ".m4v",
                 ".svi", ".3gp", ".3g2", ".mxf", ".roq", ".nsv", ".flv",
                 ".f4v", ".f4p", ".f4a", ".f4b"]

            if "sample" in file_:
                return False

            return any([file_.endswith(ext) for ext in e])

        for file_ in files:
            if is_media(file_):
                return file_

    torrent = Torrent(magnet, {}, (randint(1024, 2000), randint(1024, 2000)))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(stream_torrent(
        loop, torrent, play_file, first_file))
    loop.close()
