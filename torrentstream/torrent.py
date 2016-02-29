#!/usr/bin/env python3.5
"""
    Simple wrapper over libtorrent
"""
import libtorrent as lt

STATUSES = ['queued', 'checking', 'downloading metadata',
            'downloading', 'finished', 'seeding', 'allocating',
            'checking fastresume']


class Torrent:
    """ Wrapper over libtorrent """
    _files = []

    def __init__(self, magnet_link, params, ports):
        params_ = {
            'save_path': '.',
            'auto_managed': False,
            'storage_mode': lt.storage_mode_t.storage_mode_sparse
        }
        params_.update(params)
        self.session = lt.session()
        self.session.listen_on(*ports)
        self.handle = lt.add_magnet_uri(self.session, magnet_link, params_)

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
        return self.handle.get_torrent_info().name()

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
    def files(self):
        """ TODO
            {
                'file': filelike,
                'name': name,
                'completed_percent': completed,
                'chunks': chunks
             }
        """
        if not self._files:
            priorities = self.handle.file_priorities()
            files = self.handle.files()
            self._files = files
            print(priorities, files)
        return self._files

    def update_priorities(self):
        """
            Update file priorities with self.files'
        """
        self.handle.prioritize_files([a['priority'] for a in self.files])

    def download_only(self, file):
        """ Filter out priorities for every file except this one"""
        for file in self.files:
            file['priority'] = 0
        self.files[file]['priority'] = 7  #: Max priority
