"""Torrentstream"""
from async_timeout import timeout
import sys
import logging
import asyncio
from .torrent import TorrentSession

logging.basicConfig(level=logging.INFO)


async def stream_torrent(hash_torrent):
    # Create a session, and add a torrent
    session = TorrentSession()
    torrent = session.add_torrent(magnet_link=hash_torrent)

    # Force sequential mode
    torrent.sequential(True)

    # Wait for torrent to be started
    await torrent.wait_for('started')

    # Get first match of a media file
    try:
        media = next(a for a in torrent
                     if a.is_media and not 'sample' in a.path.lower())
    except StopIteration:
        raise Exception('Could not find a playable source')

    with timeout(5 * 60):  # Abort if we can't fill 5% in 5 minutes
        await media.wait_for_completion(5)

    return await asyncio.gather(torrent.wait_for('finished'),
                                torrent.launch(torrent.launch()))



def main():
    asyncio.run(stream_torrent(sys.argv[1]))
