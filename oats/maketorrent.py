import os.path
import os
import hashlib
import sys

from . import bencode

from urllib.parse import urlparse


def validPath(path):
    """argparse path helper."""
    if os.path.exists(path):
        if os.path.isfile(path):
            return path

        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                if files:
                    return path

            raise argparse.ArgumentTypeError("Empty dir: '{}'".format(path))

    else:
        raise argparse.ArgumentTypeError("Invalid path: '{}'".format(path))


def trackerUrl(url):
    """argparse tracker URL helper."""
    parsed = urlparse(url)

    if parsed.scheme and parsed.netloc and parsed.path:
        if parsed.scheme in ('http', 'https', 'udp'):
            return url

    else:
        raise argparse.ArgumentTypeError("Invalid tracker: '{}'".format(url))


class fileListConcatenator(object):
    """Concatenate files, provides a context manager and a piece iterator"""

    def __init__(self, files, blocksize):
        self.files = list(files)
        self.files.reverse()
        self.currentFile = open(self.files.pop(), 'rb')
        self.blocksize = blocksize


    # Context manager
    def __enter__(self):
        return self


    def __exit__(self, type, value, traceback):
        self.currentFile.close()


    # Iterator
    def __iter__(self):
        return self

    def __next__(self):
        block = self.read(self.blocksize)

        if not block:
            raise StopIteration

        return block


    # The main (ugly)thing
    def read(self, size):
        if self.currentFile.closed:
            return b''

        ret = b''
        while len(ret) < size:
            chunk = self.currentFile.read(size - len(ret))

            if not chunk:
                if self.nextFile():
                    continue

                else:
                    break

            ret += chunk

        return ret

    # Consume a new file
    def nextFile(self):
        try:
            self.currentFile.close()
            self.currentFile = open(self.files.pop(), 'rb')

        except IndexError:
            return False

        else:
            return True


def makePieces(files, psize):
    """Concatenate file piece hashes"""
    pieces = b''

    with fileListConcatenator(files, psize) as f:
        for piece in f:
            pieces += hashlib.sha1(piece).digest()

    return pieces


def mktorrent(path, outfile, tracker=None, piecesize=2**18, private=True, magnet=False, source=None):
    """Main function, writes metainfo file, fixed piece size for now"""

    # Common dict items
    torrent = {}
    torrent['info'] = {}
    torrent['info']['piece length'] = piecesize
    torrent['info']['name'] = os.path.basename(path.rstrip(os.sep))

    if tracker:
        torrent['announce'] = tracker[0]

        if len(tracker) > 1:
            torrent['announce-list'] = [tracker]

        if private:
            torrent['info']['private'] = True

        if source is not None:
            torrent['info']['source'] = source

    # Single file case
    if os.path.isfile(path):

        torrent['info']['length'] = os.path.getsize(path)
        torrent['info']['pieces'] = makePieces([path], piecesize)

    # Multiple file case
    elif os.path.isdir(path):

        torrent['info']['files'] = []

        filelist = []
        for root, _, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                filelist.append(filepath)

                fileinfo = {'length': os.path.getsize(filepath),
                            'path': filepath.split(os.sep)[1:]} #Del root dir

                torrent['info']['files'].append(fileinfo)

        torrent['info']['pieces'] = makePieces(filelist, piecesize)

    # Write metainfo file
    with open(outfile,'wb') as outpt:
        outpt.write(bencode.Bencode(torrent))

    # Print minimal magnet link if requested
    if magnet:
        link = 'magnet:?xt=urn:btih:'
        infohash = hashlib.sha1(bencode.Bencode(torrent['info'])).hexdigest()
        print(link + infohash)

    return 0
