#!/usr/bin/env python

"""OATS

OATS is a cross-platform commandline tool for the transcoding of audio albums.
Capable also of making torrent files for target albums and trancoded albums.

Usage:
  oats mkconfig [<file>]
  oats mktorrent [options] <target> ...
  oats [options] <target> ...
  oats (-h | --help)
  oats --version

Options:
  -p --processes=<count>   Set the number of processes to employ. A value of 0
                           will set equivalent to number of CPU cores. Useful
                           for throttling or if autodetection is incorrect.
  -f --formats=<fmt-list>  A comma-separated list of formats to target for
                           transcoding, like "320,V0,V2".
  -a --announce-url=<url>  Set an announce url for torrent creation.
  -o --output-dir=<dir>    A directory path where transcodes will be put.
  -t --torrent-dir=<dir>   A directory path where torrent files will be put.
  -T --torrent-enabled     Set this option to enable torrent creation.
  -c --config=<conf-file>  Specify a configuration file to use.
  -s --source=<str>        An identifier string used by some trackers. 
  -h --help                Show this screen.
  --version                Show version.

Arguments:
  <conf-file>

Examples:

Generate a baseline configuration file
  oats mkconfig
"""

#Non-Standard Libs
from docopt import docopt
from . import maketorrent, __version__
# import mutagen  # Looks like mutagen is not even needed for ffmpeg versions >= 3.2


#Standard Libs
from configparser import ConfigParser, ExtendedInterpolation
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
import multiprocessing
import os
import platform
import re
import subprocess
import sys


class InvalidPath(Exception):
    pass

class InvalidConfiguration(Exception):
    pass

class Task(object):
    def __init__(self, *commands):
        self.commands = commands
    def __call__(self):
        for command in self.commands:
            if platform.system() == 'Windows' and command[0] == COPY:
                shell = True
            else:
                shell = False
            _c = subprocess.run(command,
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
#                                timeout=300,  # No single transcode is likely to take more than 5 minutes
                                shell=shell)
    def __repr__(self):
        fmt = 'Task:\n'
        for command in self.commands:
            fmt+= ('     {}\n'.format(' '.join(command)))
        return fmt

if platform.system() == 'Windows':
    COPY = 'copy'
else:
    COPY = 'cp'

_ffmpeg = ['ffmpeg', '-threads', '1']
transcode_commands = {
    '16-48': _ffmpeg + [ '-i', '{inpt}', '-acodec', 'flac', '-sample_fmt', 's16', '-ar', '48000', '{outpt}'],
    '16-44': _ffmpeg + [ '-i', '{inpt}', '-acodec', 'flac', '-sample_fmt', 's16', '-ar', '44100', '{outpt}'],
    'alac' : _ffmpeg + [ '-i', '{inpt}', '-acodec', 'alac', '{outpt}'],
    '320'  : _ffmpeg + [ '-i', '{inpt}', '-acodec', 'libmp3lame', '-b:a', '320k', '{outpt}'],
    'v0'   : _ffmpeg + [ '-i', '{inpt}', '-acodec', 'libmp3lame', '-q:a', '0', '-compression_level', '0', '{outpt}'],
    'v1'   : _ffmpeg + [ '-i', '{inpt}', '-acodec', 'libmp3lame', '-q:a', '1', '-compression_level', '0', '{outpt}'],
    'v2'   : _ffmpeg + [ '-i', '{inpt}', '-acodec', 'libmp3lame', '-q:a', '2', '-compression_level', '0', '{outpt}'],
    'v8'   : _ffmpeg + [ '-i', '{inpt}', '-acodec', 'libmp3lame', '-q:a', '8', '-compression_level', '0', '{outpt}']

}

#File extension codec classification sets
#NB: .m4a may contain either lossless or lossy encoding, beware
LOSSLESS_EXT = {'.flac', '.wav', '.m4a'}
LOSSY_EXT = {'.mp3', '.aac', '.opus', '.ogg', '.vorbis'}

#Used for string matching, and should correspond to keys in transcode_commands
CODECS = {
    'wav',  # The almighty WAV
    'flac', 'flac 24bit', 'flac 16-44', 'flac 16-48', 'flac 24-44', 'flac 24-48', 'flac 24-96', 'flac 24-196',  # FLACs
    '16-44', '16-48', '24-44', '24-48', '24-96', '24-196',  # Also FLACs
    'alac',  # ALAC
    '320', '256', '224', '192',  # MP3s
    'v0', 'apx', '256 vbr', 'v1', '224 vbr', 'v2', 'aps', '192 vbr'  # Also MP3s
}

CODEC_EXTENSIONS = {
    '16-48': '.flac',
    '16-44': '.flac',
    'alac' : '.m4a',
    '320'  : '.mp3',
    'v0'   : '.mp3',
    'v2'   : '.mp3'
}

def resolve_configuration(arg_config_file, config):
    """Implementation for the location of configuration files."""
    #If a config file was supplied, use that
    if arg_config_file is not None:
        if os.path.isfile(arg_config_file):
            with open(arg_config_file, 'r') as conf_file:
                config.read_file(conf_file)
            return
        else:
            raise ValueError('{} does not exist or is a directory'.format(arg_config_file))

    #If a config file was not supplied, check for it in the following locations:
    #  ./oats.conf
    #  ~/.config/oats.conf (in Linux, does it work in mac?)
    #  %APPDATA%\\Roaming\\oats.conf (in Windows)
    #  /etc/oats.conf
    else:
        paths = [os.path.join(os.getcwd(), 'oats.conf'),
                 ]
        if platform.system() == 'Windows':
            paths.append(os.path.join(os.getenv('APPDATA'), 'Roaming', 'oats.conf'))
        else:
            paths.append(os.path.join(os.path.expanduser('~'), '.config', 'oats.conf'))
            paths.append(os.path.join(os.path.sep, 'etc', 'oats.conf'))

        #search for the config file is sequential but not cascading. Only one
        #config file will be loaded
        for path in paths:
            if os.path.isfile(path):
                with open(path, 'r') as conf_file:
                    config.read_file(conf_file)
                return
        #Should we throw error if no config file
        raise InvalidConfigurationError("No configuration file was located or supplied")


def initialize_configuration(config):
    """Provides the baseline of configurable options"""
    config['OATS'] = {'--processes': '0',
                      '--transcode-enabled' : 'True',
                      '--output-dir': '.',
                      '--formats': '320,V0',
                      '--torrent-enabled': 'False',
                      '--torrent-dir': '.',
                      '--announce-url': 'None',
                      '--source': 'None'}

def merge_conf(conf1, conf2):
    """
    Merge two config dictionaries, with truthy values overriding falsy values.
    `conf1` takes priority over `conf2`.
    """
    return dict((str(key), conf1.get(key) or conf2.get(key))
                for key in set(conf2) | set(conf1))


def make_torrent(target, announce_url, source, torrent_dir):
    base = os.path.basename(target)
    torrent_output = os.path.abspath(os.path.join(torrent_dir, base + '.torrent'))
    if os.path.isfile(torrent_output):
        raise FileExistsError('File already exists, unable to create torrent: {}'.format(torrent_output))
    cwd = os.getcwd()
    rebase = os.chdir(os.path.split(target)[0])
    target = os.path.split(target)[1]
    maketorrent.mktorrent(target, torrent_output, tracker=announce_url, source=source)
    os.chdir(cwd)

def command_substitute(command, **kwargs):
    """
    Similar to string formatting with dictionaries and named fields.
    command_substitute(['foo', '-i', '{bar}'], {'bar': 'baz'}) will return
    ['foo', '-i', 'baz']
    """
    myre = re.compile('\A{(.*)}\B')
    new_command = []
    for item in command:
        try:
            match = myre.match(item).group(1)
        except AttributeError:
            new_command.append(item)
        else:
            if match in kwargs:
                new_command.append(kwargs[match])
    return new_command

def traverse_target(target, config):
    """
    The job of traverse_target is to recursively walk through all of the
    files in the target directory and yield commands for each of them.
    Each file will be the subject of either a copy or transcode command.
    """
    formats = [fmt.lower() for fmt in config['--formats'].split(',')]
    transcode_dirs = format_destinations(target, config)

    for dirpath, _dirs, filenames in os.walk(target):
        for filename in filenames:
            name, ext = os.path.splitext(filename)
            source_file = os.path.join(target, dirpath, filename)
            reldir = os.path.relpath(dirpath, target)

            #A file extension for a lossy format is to be ignored with a warning
            if ext in LOSSY_EXT:
                print('WARNING: {} is a lossy file and was skipped during transcoding'.format(os.path.join(dirpath, filename)))
                continue
            for fmt in formats:
                dest_dir = os.path.join(transcode_dirs[fmt], reldir)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                #A file extension not recognized as lossy or lossless will be copied
                if ext not in LOSSLESS_EXT:
                    dest = os.path.abspath(os.path.join(dest_dir, filename))
                    command = [COPY, source_file, dest]
                    yield Task(command)
                else:  # This file will be transcoded
                    dest_name = name + CODEC_EXTENSIONS[fmt]
                    dest = os.path.abspath(os.path.join(dest_dir, dest_name))
                    command = transcode_commands[fmt]
                    xcode_command = command_substitute(command, inpt=source_file, outpt=dest)
                    #ffmpeg versions >= 3.2 automatically copy metadata, so this is commented out for now
                    #Tested for mp3 and m4a, mutagen might be used to fill gaps later...
                    # meta_command = ['mutagen-copy', source_file, dest]
                    # yield Task(xcode_command, meta_command)
                    yield Task(xcode_command)

def iter_targets(config):
    """Simple iterating over targets"""
    for target in config['<target>']:
        print('Processing {} for transcoding'.format(target))
        for task in traverse_target(os.path.abspath(target), config):
            yield task

def task_caller(task):
    try:
        task()
    except Exception as e:
        print('ERROR: {}'.format(e))

def format_destinations(source, config):
    """
    Produce a mapping of format to transcode destination.
    Utilizes the path information of the source and the output directory.
    """
    formats = [fmt.lower() for fmt in config['--formats'].split(',')]
    output_dir = os.path.abspath(config['--output-dir'])
    mapping = {}
    source_name = os.path.basename(os.path.abspath(source))
    fmt_re = re.compile(r'\[(' + '|'.join([codec for codec in CODECS]) + r')\](?!.*\/.*)', flags=re.IGNORECASE)
    for fmt in formats:
        dir_has_codec = fmt_re.search(source_name) is not None
        if dir_has_codec:
            transcode_name = fmt_re.sub('[{}]'.format(fmt.upper()), source_name)
        else:
            transcode_name = source_name.rstrip() + ' [{}]'.format(fmt.upper())
        dest = os.path.join(output_dir, transcode_name)
        mapping[fmt] = dest
    return mapping

def iter_destinations(config):
    """
    Iterate over all of the transcode destinations, for all targets and formats.
    """
    for target in config['<target>']:
        mapping = format_destinations(target, config)
        for v in mapping.values():
            yield v

#if __name__ == '__main__':
def main():
    args = docopt(__doc__, version=__version__)

    #Set up a ConfigParser object
    config = ConfigParser(interpolation=ExtendedInterpolation())
    initialize_configuration(config)  # baseline configuration load

    #If mkconfig command in use, then just make the config file and quit
    if args['mkconfig']:
        if args['<file>'] is None:
            args['<file>'] = 'oats.conf'
        if not os.path.exists(args['<file>']):
            with open(args['<file>'], 'w') as conf_file:
                config.write(conf_file)
            sys.exit(0)
        else:
            raise FileExistsError('{} already exists!'.format(args['<file>']))

    #Check for configuration files
    if args['--config'] is not None and not os.path.isfile(args['--config']):
        print('WARNING: The supplied value for --config is not valid')
    resolve_configuration(args['--config'], config)

    #Apply any arg options as overrides of the loaded config file
    bconf = merge_conf(args, config['OATS'])

    bconf['--processes'] = None if bconf['--processes'] == '0' else int(bconf['processes'])
    bconf['--source'] = None if bconf['--source'] == 'None' else bconf['--source']

    #Make torrent output directory if necessary
    if not os.path.isdir(bconf['--torrent-dir']):
        os.makedirs(bconf['--torrent-dir'])

    #If mktorrent command in use, then make torrent files for the targets and quit
    if args['mktorrent']:
        for t in bconf['<target>']:
            t = os.path.abspath(t)
            make_torrent(t, bconf['--announce-url'], bconf['--source'], bconf['--torrent-dir'])
        sys.exit(0)

    #Make torrent output directory if necessary
    if not os.path.isdir(bconf['--output-dir']):
        os.makedirs(bconf['--output-dir'])

    #transcode_enabled = True if bconf['--transcode-enabled'].lower() in ['true', '1'] else False
    torrent_enabled = True if bconf['--torrent-enabled'].lower() in ['true', '1'] else False

    #Process the source targets for transcodes
    with ThreadPool(bconf['--processes']) as p:
        print('Transcoding!')
        p.map(task_caller, iter_targets(bconf))
    print('Transcoding done!')

    #Make torrents if enabled and there is an announce announce_url
    if torrent_enabled and bconf['--announce-url'] not in ['', 'None']:
        with Pool(bconf['--processes']) as p:
            print('Making Torrents!')
            p.starmap(make_torrent, [(t,
                                      bconf['--announce-url'],
                                      bconf['--source'],
                                      bconf['--torrent-dir']) for t in iter_destinations(bconf)])
