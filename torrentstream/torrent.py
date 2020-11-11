"""Simple wrapper over libtorrent"""
from urllib.parse import quote
import tempfile
import os
import asyncio
import logging
import mimetypes
from collections import namedtuple
from functools import cached_property
from random import randint

import libtorrent as lt

mimetypes.init()
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)
STATUSES = [
    'queued', 'checking', 'downloading_metadata', 'downloading', 'finished',
    'seeding', 'allocating', 'checking_fastresume'
]

TRACKERS = ("udp://tracker.openbittorrent.com:80/announce",
            "udp://tracker.publicbt.com:80/announce")

DHT = (("router.utorrent.com", 6881), ("router.bittorrent.com", 6881),
       ("dht.transmissionbt.com", 6881), ("router.bitcomet.com",
                                          6881), ("dht.aelitis.com", 6881))

EXTENSIONS = ('ut_pex', 'ut_metadata', 'smart_ban', 'metadata_transfoer')

PORTS = (randint(1024, 2000), randint(1024, 2000))


def get_indexed(func):
    """Return currently indedex torrent"""
    def inner(*args, **kwargs):
        """Executes a method, and returns result[class_instance.index]"""
        return list(func(*args, **kwargs)())[args[0].index]

    return inner


class TorrentSession:
    """Represent a torrent session. May handle multiple torrents"""
    def __init__(self, ports=PORTS, extensions=EXTENSIONS, dht_routers=DHT):
        self.session = lt.session()
        self.session.set_severity_level(lt.alert.severity_levels.critical)
        self.session.listen_on(*ports)
        for extension in extensions:
            self.session.add_extension(extension)
        self.session.start_dht()
        self.session.start_lsd()
        self.session.start_upnp()
        self.session.start_natpmp()
        for router in dht_routers:
            self.session.add_dht_router(*router)
        self.torrents = []

    @property
    async def alerts(self):
        if all(a.finished for a in self):
            raise StopIteration()
        for alert in self.session.pop_alerts():
            yield alert

    def remove_torrent(self, *args, **kwargs):
        """Remove torrent from session."""
        self.session.remove_torrent(*args, **kwargs)

    def add_torrent(self, **kwargs):
        """Add a torrent to this session

        For accepted parameters reference, see over `Torrent` definition.
        """
        torrent = Torrent(session=self, **kwargs)
        self.torrents.append(torrent)
        return torrent

    def __iter__(self):
        """Iterating trough a session will give you all the currently-downloading torrents"""
        return iter(self.torrents)


class Torrent:
    """Wrapper over libtorrent"""
    def __init__(self,
                 magnet_link: str,
                 session: TorrentSession,
                 trackers: tuple = TRACKERS,
                 remove_after: bool = False,
                 **params):
        """Set default parameters to a magnet link, and add ourselves to a session


        Arguments:

            magnet_link: Magnet link. Currently torrent files are not supported
            session: TorrentSession instance
            trackers: Tracker list to add to magnet link. Defaults to TRACKERS
                      constant
            remove_after: Delete download dir upon __exit__. Only if params.save_path has not been specified
            save_path: Path to save the torrent into. A temporary directory
                       will be created if not specified
            storage_mode: Property of lt.storage_mode_t
        """
        self.session = session
        self.temp_dir = None
        self.remove_after = remove_after
        self.params = {
            'save_path': None,
            'storage_mode': lt.storage_mode_t.storage_mode_sparse,
            **params
        }

        #: Force trackers into magnet link. Not the best coding practice.
        trackers = (quote(t, safe='') for t in trackers)
        self.magnet_link = f'{magnet_link}&tr={"&tr=".join(trackers)}'
        self.handle = None

    def __enter__(self):
        if not self.params.get('save_path'):
            self.temp_dir = tempfile.TemporaryDirectory()
            self.params['save_path'] = self.temp_dir.name
        self.handle = lt.add_magnet_uri(self.session.session, self.magnet_link,
                                        self.params)
        return self

    def __exit__(self, *args, **kwargs):
        if self.temp_dir and self.remove_after:
            self.temp_dir.cleanup()
        self.session.remove_torrent(self.handle)

    def sequential(self, value: bool):
        """Set sequential download"""
        self.handle.set_sequential_download(value)

    @property
    def queue(self):
        """ Download queue """
        return self.handle.get_download_queue()

    @property
    def queue_status(self):
        """ Returns a represented queue status """
        state_char = [' ', '-', '=', '#']

        def repr_piece(piece):
            """ Represents a piece """
            return {
                piece['piece_index']:
                [state_char[block['state']] for block in piece['blocks']]
            }

        return [repr_piece(piece) for piece in self.queue]

    @property
    def name(self):
        """ Torrent name """
        if not self.handle.has_metadata():
            return "N/A"
        return self.torrent_info.name()

    @property
    def status(self):
        """
            Return a status dict.
        """
        status = self.handle.status()
        result = {
            'name': self.name,
            'download': status.download_rate,
            'total_download': status.total_download,
            'upload': status.upload_rate,
            'total_upload': status.total_upload
        }

        if not self.finished:
            result.update({
                'state': STATUSES[status.state],
                'total_downloaded': status.total_done,
                'peers': status.num_peers,
                'seeds': status.num_seeds,
                'progress': '%5.4f%%' % (status.progress * 100),
            })

        return result

    @property
    def finished(self):
        """Checks if torrent is finished."""
        return self.handle.is_finished()

    @property
    def started(self):
        """ Checks if handle has metadata"""
        return self.handle.has_metadata()

    @property
    def torrent_info(self):
        """Return handle.torrent_info"""
        return self.handle.get_torrent_info()

    @cached_property
    def files(self):
        """Returns a `TorrentFile` object for each file"""
        fnum = range(len(self.torrent_info.files()))
        return [TorrentFile(self, i) for i in fnum]

    def update_priorities(self):
        """Update file priorities with self.files."""
        self.handle.prioritize_files([a.priority for a in self.files])

    def download_only(self, file):
        """ Filter out priorities for every file except this one"""
        if file not in self.files:
            return None
        for file_ in self.files:
            file.priority = 7 if file == file_ else 0
        return file

    async def wait_for(self, status):
        """Wait for a specific status

        Example:
            >>> # This will wait for a torrent to start, and return the torrent
            >>> torrent = await Torrent("magnet:...").wait_for('started')

            >>> # This will wait for a torrent to finish, and return the torrent
            >>> torrent = await Torrent("magnet:...").wait_for('finished')
        """
        while not getattr(self, status):
            await asyncio.sleep(1)

    def __iter__(self):
        """Iterating trough a Torrent instance will return each TorrentFile"""
        return iter(self.files)


class TorrentFile:
    """ Wrapper over libtorrent.file """
    def __init__(self, parent: Torrent, index: int):
        self.root = parent.params.get('save_path')
        self.index = index
        self.handle = parent.handle
        self.torrent = parent

    async def wait_for_completion(self, percent):
        while self.completed_percent < percent:
            await asyncio.sleep(5)

    async def launch(self):
        """Launch file with PLAYER envvar or xdg-open"""
        process = await asyncio.create_subprocess_exec(
            os.getenv('PLAYER', 'xdg-open'),
            f'{self.root}/{self.path}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        await process.wait()

    @cached_property
    def mime_type(self):
        """Return file mimetype"""
        return mimetypes.guess_type(self.path)[0] or ''

    @cached_property
    def is_media(self):
        """Return true if file is a media type"""
        return any(
            self.mime_type.startswith(f) for f in ('audio', 'video', 'image'))

    @cached_property
    def path(self):
        """Return torrent path on filesystem"""
        return self.hfile.path

    @cached_property
    def file(self):
        """Return a file object with this file's path open in rb mode """
        return open(self.path, 'rb')

    @property
    def filehash(self):
        """File hash"""
        return self.hfile.filehash

    @property
    def size(self):
        """File size"""
        return self.hfile.size

    @property
    @get_indexed
    def hfile(self):
        """ Return file from libtorrent """
        return self.handle.get_torrent_info().files

    @property
    @get_indexed
    def priority(self):
        """ Readonly file priority from libtorrent """
        return self.handle.file_priorities

    @priority.setter
    def priority(self, value):
        self._priority = value
        self.parent.update_priorities()

    @property
    @get_indexed
    def file_progress(self):
        """ Returns file progress """
        return self.handle.file_progress

    @property
    def completed_percent(self):
        """ Returns this file completed percentage """
        return (self.file_progress / self.size) * 100
