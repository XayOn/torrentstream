#!/usr/bin/env python3.5
"""
    Simple wrapper over libtorrent
"""
import logging
import asyncio
from collections import namedtuple
import libtorrent as lt

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)
STATUSES = ['queued', 'checking', 'downloading metadata',
            'downloading', 'finished', 'seeding', 'allocating',
            'checking fastresume']


def get_indexed(func):
    """ Black magic """
    def inner(*args, **kwargs):
        """ Dragons """
        return func(*args, **kwargs)()[args[0].index]
    return inner


class TorrentFile:
    """ Wrapper over libtorrent.file """
    def __init__(self, handle, index):
        self.index = index
        self.handle = handle
        self.path = self.hfile.path
        self.filehash = self.hfile.filehash.to_bytes
        self.size = self.hfile.size
        self.priority = self.file_priority

    def path(self):
        return self.hfile.path

    @property
    def file(self):
        """ Return a file object with this file's path open in rb mode """
        return open(self.path, 'rb')

    @property
    @get_indexed
    def hfile(self):
        """ Return file from libtorrent """
        return self.handle.get_torrent_info().files

    @property
    @get_indexed
    def file_priority(self):
        """ Readonly file priority from libtorrent """
        return self.handle.file_priorities

    @property
    @get_indexed
    def file_progress(self):
        """ Returns file progress """
        return self.handle.file_progress

    @property
    def completed_percent(self):
        """ Returns this file completed percentage """
        return (self.file_progress / self.size) * 100


class Torrent:
    """ Wrapper over libtorrent """
    _files = []

    def __init__(self, magnet_link, params, ports):
        params_ = {
            'save_path': '.',
            'auto_managed': True,
            'paused': False,
            'port': 6881,
            'ratio': 0,
            'max_download_rate': -1,
            'max_upload_rate': -1,
            'storage_mode': lt.storage_mode_t.storage_mode_sparse
        }
        trackers = [
            "http://9.rarbg.com:2710/announce",
            "http://explodie.org:6969/announce",
            "http://mgtracker.org:2710/announce",
            "http://tracker.tfile.me/announce",
            "http://tracker.torrenty.org:6969/announce",
            "http://tracker.trackerfix.com/announce",
            "http://www.mvgroup.org:2710/announce",
            "udp://9.rarbg.com:2710/announce",
            "udp://9.rarbg.me:2710/announce",
            "udp://9.rarbg.to:2710/announce",
            "udp://coppersurfer.tk:6969/announce",
            "udp://exodus.desync.com:6969/announce",
            "udp://glotorrents.pw:6969/announce",
            "udp://open.demonii.com:1337/announce",
            "udp://tracker.coppersurfer.tk:6969/announce",
            "udp://tracker.glotorrents.com:6969/announce",
            "udp://tracker.leechers-paradise.org:6969/announce",
            "udp://tracker.openbittorrent.com:80/announce",
            "udp://tracker.opentrackr.org:1337/announce",
            "udp://tracker.publicbt.com:80/announce",
            "udp://tracker4.piratux.com:6969/announce"
        ]

        #: I know it's not nice to add trackers like this...
        magnet_link += '&tr='.join(trackers)
        params_.update(params)
        self.session = lt.session()
        self.session.set_severity_level(lt.alert.severity_levels.critical)
        self.session.listen_on(*ports)
        self.session.add_extension('ut_pex')
        self.session.add_extension('ut_metadata')
        self.session.add_extension('smart_ban')
        self.session.add_extension('metadata_transfer')

        self.session.start_dht()
        self.session.start_lsd()
        self.session.start_upnp()
        self.session.start_natpmp()

        self.session.add_dht_router("router.utorrent.com", 6881)
        self.session.add_dht_router("router.bittorrent.com", 6881)
        self.session.add_dht_router("dht.transmissionbt.com", 6881)
        self.session.add_dht_router("router.bitcomet.com", 6881)
        self.session.add_dht_router("dht.aelitis.com", 6881)

        self.handle = lt.add_magnet_uri(self.session, magnet_link, params_)

    def sequential(self, value):
        """ Set sequential download """
        self.handle.set_sequential_download(value)

    @property
    def queue(self):
        """ Download queue """
        return self.handle.get_download_queue()

    def queue_status(self):
        """ Returns a represented queue status """
        state_char = [' ', '-', '=', '#']

        def repr_piece(piece):
            """ Represents a piece """
            return {piece['piece_index']: [state_char[block['state']] for
                                           block in piece['blocks']]}

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
        """
            Checks if torrent is finished
            I was previously checking status against ""seeding"" state,
            but this one is able to discern if prioriticed files are in order
        """
        return self.handle.is_finished()

    @property
    def started(self):
        """ Checks if handle has metadata"""
        return self.handle.has_metadata()

    @property
    def torrent_info(self):
        """ Return handle.torrent_info """
        return self.handle.get_torrent_info()

    @property
    def files(self):
        """ Returns a TorrentFile object for each file """
        if not self._files:
            files_ = range(len(self.torrent_info.files()))
            self._files = [TorrentFile(self.handle, index) for index in files_]
        return self._files

    def update_priorities(self):
        """
            Update file priorities with self.files'
        """
        self.handle.prioritize_files([a.priority for a in self.files])

    def download_only(self, file):
        """ Filter out priorities for every file except this one"""
        result = False
        for file_ in self.files:
            file_.priority = 0
            if file == file_:
                LOG.debug("File found: %s", file_.path)
                file_.priority = 7
                result = file_
        self.update_priorities()
        return result


async def wait_for_completion(torrent):
    """ Wait for a torrent to finish (coroutine)"""
    while not torrent.finished:
        await asyncio.sleep(5)
