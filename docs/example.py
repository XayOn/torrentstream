"""
    Example use of torrentstream and pychapter combined
"""
from contextlib import suppress
import mimetypes
import asyncio
import sys
import os
from torrentstream import stream_torrent, LOG
from pychapter import Chapter


async def play_file(*args):
    """
        Launch player against file
        player is adquired from the PLAYER environment variable
    """
    file = args[1]
    LOG.info(file.__dict__)
    await asyncio.sleep(5)
    player = os.getenv('PLAYER')
    process = await asyncio.create_subprocess_exec(player, file.path)
    await process.wait()


def filter_files(chapter):
    """ Filter files for a chapter"""
    def filter_(files):
        """
            Gets a list of files and returns the first one matching
            the chapter
        """
        reserved_ = ['sample']
        for file in files:
            if any([res in file.path.lower() for res in reserved_]):
                continue
            if Chapter(filename=file.path) == chapter:
                if 'video' in mimetypes.guess_type(file.path)[0]:
                    with suppress(OSError):
                        os.makedirs(os.path.dirname(file.path))
                    spath = '.'.join(file.path.split('.')[:-1])
                    with open("{}.srt".format(spath), 'wb') as subs:
                        subs.write(chapter.subtitle.file)
                    return file
    return filter_

CHAPTER = Chapter(title=sys.argv[1], season=int(sys.argv[2]),
                  episode=int(sys.argv[3]))
CHAPTER.subtitle

if len(sys.argv) > 4:
    CHAPTER.magnet = sys.argv[4]

stream_torrent(CHAPTER.magnet['link'], stream_func=play_file,
               filter_func=filter_files(CHAPTER))
