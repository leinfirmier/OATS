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
  -T --torrent=<bool>      Set this option to toggle whether to automatically
                           create torrents of transcodes. Expects values to be
                           in {1, 0, True, False, t, f} case insensitive,
  -c --config=<conf-file>  Specify a configuration file to use.
  -s --source=<str>        An identifier string used by some trackers.
  -h --help                Show this screen.
  -v --version             Show version.

Arguments:
  <conf-file>

Examples:

Generate a baseline configuration file
  oats mkconfig
"""

#Non-Standard Libs
from docopt import docopt
from . import maketorrent, __version__

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

AAC_ENCODER = 'aac'
#To use the Fraunhofer FDK AAC codec library, comment the line above and
#uncomment the one below. It is non-free software and not likely a part of your
#compiled ffmpeg unless you compiled yourself. --enable-libfdk-aac and
#--enable-nonfree during build configuration
#AAC_ENCODER = 'libfdk_aac'  # To use the Fraunhofer FDK AAC codec library

_ffmpeg = ['ffmpeg', '-threads', '1']
transcode_commands = {
    '16-48'  : _ffmpeg + ['-i', '{inpt}', '-c:a', 'flac', '-sample_fmt', 's16', '-ar', '48000', '{outpt}'],
    '16-44'  : _ffmpeg + ['-i', '{inpt}', '-c:a', 'flac', '-sample_fmt', 's16', '-ar', '44100', '{outpt}'],
    'alac'   : _ffmpeg + ['-i', '{inpt}', '-c:a', 'alac', '{outpt}'],  # TODO: research  ALAC encoder for options
    'aac 256': _ffmpeg + ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-b:a', '256k', '{outpt}'],
    'aac 128': _ffmpeg + ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-b:a', '128k', '{outpt}'],
    '320'    : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-b:a', '320k', '-compression_level', '0' ,'{outpt}'],
    '256'    : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-b:a', '256k', '-compression_level', '0' ,'{outpt}'],
    '224'    : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-b:a', '224k', '-compression_level', '0' ,'{outpt}'],
    '192'    : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-b:a', '192k', '-compression_level', '0' ,'{outpt}'],
    'v0'     : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-q:a', '0', '-compression_level', '0', '{outpt}'],
    'v1'     : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-q:a', '1', '-compression_level', '0', '{outpt}'],
    'v2'     : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-q:a', '2', '-compression_level', '0', '{outpt}'],
    'v3'     : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-q:a', '3', '-compression_level', '0', '{outpt}'],
    'v4'     : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-q:a', '4', '-compression_level', '0', '{outpt}'],
    'v5'     : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-q:a', '5', '-compression_level', '0', '{outpt}'],
    'v6'     : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-q:a', '6', '-compression_level', '0', '{outpt}'],
    'v7'     : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-q:a', '7', '-compression_level', '0', '{outpt}'],
    'v8'     : _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-q:a', '8', '-compression_level', '0', '{outpt}'],
    '256 abr': _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-b:a', '256k', '--abr', '1', '-compression_level', '0', '{outpt}'],
    '224 abr': _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-b:a', '224k', '--abr', '1', '-compression_level', '0', '{outpt}'],
    '192 abr': _ffmpeg + ['-i', '{inpt}', '-c:a', 'libmp3lame', '-b:a', '192k', '--abr', '1', '-compression_level', '0', '{outpt}'],
}

if AAC_ENCODER == 'aac':
    transcode_commands['aac v0.1'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-q:a', '0.1', '{outpt}']
    transcode_commands['aac v1.0'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-q:a', '1.0', '{outpt}']
    transcode_commands['aac v2.0'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-g:a', '2.0', '{outpt}']
elif AAC_ENCODER == 'libfdk_aac':
    transcode_commands['aac v1'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '1', '{outpt}']
    transcode_commands['aac v2'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '2', '{outpt}']
    transcode_commands['aac v3'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '3', '{outpt}']
    transcode_commands['aac v4'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '4', '{outpt}']
    transcode_commands['aac v5'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '5', '{outpt}']
else:
    raise InvalidConfiguration('Invalid encoder for AAC set: {}'.format(AAC_ENCODER))

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
    'aac 256', 'aac 128',  # AACs with CBR mode
    'aac v1', 'aac v2','aac v3', 'aac v4', 'aac v5',  # AACs with VBR mode (5 is best)
    '320', '256', '224', '192',  # MP3s with CBR mode
    'v0', 'v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7',  'v8',  # MP3s with VBR mode (0 is best)
    '256 abr', '224 abr', '192 abr'  # MP3s with ABR mode
}

CODEC_EXTENSIONS = {
    'wav'    : '.wav',
    'flac'   : '.flac',
    '16-48'  : '.flac',
    '16-44'  : '.flac',
    'alac'   : '.m4a',
    'aac 256': '.m4a',
    'aac 128': '.m4a',
    'aac v1' : '.m4a',
    'aac v2' : '.m4a',
    'aac v3' : '.m4a',
    'aac v4' : '.m4a',
    'aac v5' : '.m4a',
    '320'    : '.mp3',
    '256'    : '.mp3',
    '224'    : '.mp3',
    '192'    : '.mp3',
    'v0'     : '.mp3',
    'v1'     : '.mp3',
    'v2'     : '.mp3',
    'v3'     : '.mp3',
    'v4'     : '.mp3',
    'v5'     : '.mp3',
    'v6'     : '.mp3',
    'v7'     : '.mp3',
    'v8'     : '.mp3',
}


def resolve_configuration(arg_config_file, config):
    """Implementation for the location of configuration files."""
    #Use the config file path given
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
        raise InvalidConfiguration("No configuration file was located or supplied")


def initialize_configuration(config):
    """Provides the baseline of configurable options"""
    config['OATS'] = {'--processes': '0',
                      '--transcode-enabled' : 'True',
                      '--output-dir': '.',
                      '--formats': '320,V0',
                      '--torrent': 'False',
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
            for fmt in config['--formats']:
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
    output_dir = os.path.abspath(config['--output-dir'])
    mapping = {}
    source_name = os.path.basename(os.path.abspath(source))
    fmt_re = re.compile(r'\[(' + '|'.join([codec for codec in CODECS]) + r')\](?!.*\/.*)', flags=re.IGNORECASE)
    for fmt in config['--formats']:
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

    #Argument normalization
    bconf['--processes'] = None if bconf['--processes'] == '0' else int(bconf['processes'])
    bconf['--source'] = None if bconf['--source'] == 'None' else bconf['--source']
    bconf['--torrent'] = True if bconf['--torrent'].lower() in ['1','t','true'] else False
    bconf['--formats'] = [fmt.lower() for fmt in bconf['--formats'].split(',')]

    #Apply a check for format existence in transcode_commands. If it does not
    #exist there, then OATS does not know how to transcode to it
    for fmt in bconf['--formats']:
        if fmt not in transcode_commands:
            raise InvalidConfiguration('The format "{}" is not known to OATS'.format(fmt))

    #Make torrent output directory if necessary
    if not os.path.isdir(bconf['--torrent-dir']):
        os.makedirs(bconf['--torrent-dir'])

    #If mktorrent command in use, then make torrent files for the targets and quit
    if args['mktorrent']:
        if bconf['--announce-url'] in ['', 'None']:  # Error if announce url is missing
            raise InvalidConfiguration('Torrent creation enabled but no announce url provided!')
        for t in bconf['<target>']:
            t = os.path.abspath(t)
            make_torrent(t, bconf['--announce-url'], bconf['--source'], bconf['--torrent-dir'])
        sys.exit(0)

    #Make torrent output directory if necessary
    if not os.path.isdir(bconf['--output-dir']):
        os.makedirs(bconf['--output-dir'])

    #Process the source targets for transcodes
    with ThreadPool(bconf['--processes']) as p:
        print('Transcoding!')
        p.map(task_caller, iter_targets(bconf))
    print('Transcoding done!')

    #Make torrents if enabled
    if bconf['--torrent']:
        if bconf['--announce-url'] in ['', 'None']:  # Error if announce url is missing
            raise InvalidConfiguration('Torrent creation enabled but no announce url provided!')
        with Pool(bconf['--processes']) as p:
            print('Making Torrents!')
            p.starmap(make_torrent, [(t,
                                      bconf['--announce-url'],
                                      bconf['--source'],
                                      bconf['--torrent-dir']) for t in iter_destinations(bconf)])
