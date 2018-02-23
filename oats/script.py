"""OATS

OATS is a commandline tool for easy transcoding of audio albums. It effectively
parallelizes transcodes, is cross-platform, and makes torrents if directed.

Usage:
  oats mkconfig [<file>]
  oats mktorrent [options] <target> ...
  oats [options] <target> ...
  oats (--help | --version | --show-formats)

Options:
  -c --config=<conf-file>  Specify a configuration file to use.
  -f --formats=<fmt-list>  A comma-separated list of formats to target for
                           transcoding, like "320,V0,V2".
  -o --output-dir=<dir>    A directory path where transcodes will be put.
  -p --processes=<count>   Set the number of processes to employ. A value of 0
                           will set equivalent to number of CPU cores. Useful
                           for throttling or if autodetection is incorrect.
  -l --list-file           Process targets as list files, each line of the file
                           containing a path to a directory to be transcoded.
  -F --show-formats        Print out the list of formats known to OATS.
  -h --help                Show this screen.
  -v --version             Show version.

Torrent Options:
  -T --torrent=<bool>      Set this option to toggle whether to torrents should
                           be created for transcode outputs. Ignored by
                           mktorrent subcommand. Boolean-ish values expected to
                           enable: one of {1. True, t}, others will disable.
  -a --announce-url=<url>  Set an announce url for torrent creation. This is
                           required for torrent creation.
  -t --torrent-dir=<dir>   A directory path where torrent files will be placed.
  -s --source=<str>        A special short identifier string used by some
                           trackers to help cross-seeding.
"""

#Non-Standard Libs
from docopt import docopt
from . import maketorrent, __version__
from . import codec

#Standard Libs
from collections import namedtuple
from configparser import ConfigParser, ExtendedInterpolation
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
import os
import platform
from pprint import pprint
import re
import shlex
import subprocess
import sys


class InvalidConfiguration(Exception):
    pass

class NotSupportedError(Exception):
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
            try:
                if shell:
                    command = ' '.join(shlex.quote(w) for w in command)
                subprocess.check_call(command,
                                      stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL,
                                      shell=shell)
            except subprocess.CalledProcessError as e:
                print('{} reports an error: code {}'.format(e.cmd, e.returncode))

    def __repr__(self):
        fmt = 'Task:\n'
        for command in self.commands:
            fmt+= ('     {}\n'.format(' '.join(command)))
        return fmt

if platform.system() == 'Windows':
    COPY = 'copy'
    RM = 'del'
else:
    COPY = 'cp'
    RM = 'rm'

AAC_ENCODER = 'aac'
#To use the Fraunhofer FDK AAC codec library, comment the line above and
#uncomment the one below. It is non-free software and not likely a part of your
#compiled ffmpeg unless you compiled yourself. --enable-libfdk-aac and
#--enable-nonfree during build configuration
#AAC_ENCODER = 'libfdk_aac'  # To use the Fraunhofer FDK AAC codec library


ext_codec_full_map = {'.mp3'   : [codec.LAME, codec.FFmpeg],
                      '.flac'  : [codec.FFmpegFLAC],
                      '.m4a'   : [codec.FFmpeg],
                      '.alac'  : [codec.FFmpeg],
                      '.aac'   : [codec.FFmpeg],
                      '.opus'  : [codec.FFmpeg],
                      '.ogg'   : [codec.FFmpeg],
                      '.vorbis': [codec.FFmpeg],}

ext_codec_map = {}
for key in ext_codec_full_map:
    ext_codec_map[key] = [codec for codec in ext_codec_full_map[key] if codec.on_system()]

format_codec_full_map = {
    'FLAC': [codec.FFmpegFLAC],
    'MP3' : [codec.LAME, codec.FFmpegMP3],
    }
format_codec_map = {}
for key in format_codec_full_map:
    format_codec_map[key] = [codec for codec in format_codec_full_map[key] if codec.on_system()]

#pprint(ext_codec_map)
#pprint(format_codec_map)

# if AAC_ENCODER == 'aac':
    # #TODO: Discover what set of aac vbr quality values are actually desirous
    # transcode_commands['aac v0.1'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-q:a', '0.1', '{outpt}']
    # transcode_commands['aac v1.0'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-q:a', '1.0', '{outpt}']
    # transcode_commands['aac v2.0'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-g:a', '2.0', '{outpt}']
# elif AAC_ENCODER == 'libfdk_aac':
    # transcode_commands['aac v1'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '1', '{outpt}']
    # transcode_commands['aac v2'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '2', '{outpt}']
    # transcode_commands['aac v3'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '3', '{outpt}']
    # transcode_commands['aac v4'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '4', '{outpt}']
    # transcode_commands['aac v5'] = _ffmpeg = ['-i', '{inpt}', '-c:a', AAC_ENCODER, '-vbr', '5', '{outpt}']
# else:
    # raise InvalidConfiguration('Invalid encoder for AAC: {}'.format(AAC_ENCODER))

#File extension codec classification sets
#NB: .m4a may contain either lossless or lossy encoding, beware
LOSSLESS_EXT = {'.flac', '.wav', '.m4a', '.alac'}
LOSSY_EXT = {'.mp3', '.aac', '.opus', '.ogg', '.vorbis'}
AUDIO_EXTENSIONS = LOSSLESS_EXT.union(LOSSY_EXT)

format_codec_map_full = {
    'MP3':  [codec.LAME, codec.FFmpegMP3],
    'FLAC': [codec.FFmpegFLAC],
}
#Used for string matching, and should correspond to keys in transcode_commands
#CODECS = {
    #'wav',  # The almighty WAV
    #'flac', 'flac 24bit', 'flac 16-44', 'flac 16-48', 'flac 24-44', 'flac 24-48', 'flac 24-96', 'flac 24-196',  # FLACs
    #'16-44', '16-48', '24-44', '24-48', '24-96', '24-196',  # Also FLACs
    #'alac',  # ALAC
    #'aac 256', 'aac 192', 'aac 128',  # AACs with CBR mode
    #'aac v1', 'aac v2','aac v3', 'aac v4', 'aac v5',  # AACs with VBR mode (5 is best)
    #'aac v0.1', 'aac v1.0', 'aac v2.0',  # AACs with VBR for built-in aac encoder
    #'320', '256', '224', '192',  # MP3s with CBR mode
    #'v0', 'v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7',  'v8',  # MP3s with VBR mode (0 is best)
    #'256 abr', '224 abr', '192 abr'  # MP3s with ABR mode
#}

#CODEC_EXTENSIONS = {
    #'wav'    : '.wav',
    #'flac'   : '.flac',
    #'16-48'  : '.flac',
    #'16-44'  : '.flac',
    #'alac'   : '.m4a',
    #'aac 256': '.m4a',
    #'aac 192': '.m4a',
    #'aac 128': '.m4a',
    #'aac v1' : '.m4a',
    #'aac v2' : '.m4a',
    #'aac v3' : '.m4a',
    #'aac v4' : '.m4a',
    #'aac v5' : '.m4a',
    #'320'    : '.mp3',
    #'256'    : '.mp3',
    #'224'    : '.mp3',
    #'192'    : '.mp3',
    #'v0'     : '.mp3',
    #'v1'     : '.mp3',
    #'v2'     : '.mp3',
    #'v3'     : '.mp3',
    #'v4'     : '.mp3',
    #'v5'     : '.mp3',
    #'v6'     : '.mp3',
    #'v7'     : '.mp3',
    #'v8'     : '.mp3',
    #'v9'     : '.mp3',
#}


def resolve_configuration(arg_config_file, config):
    """Implementation for the location of configuration files."""
    #Use the config file path given
    if arg_config_file is not None:
        conf_filepath = os.path.abspath(os.path.expanduser(arg_config_file))
        if os.path.isfile(conf_filepath):
            with open(conf_filepath, 'r') as conf_file:
                config.read_file(conf_file)
            return
        else:
            raise ValueError('The file specified for config does not exist: {}'.format(arg_config_file))

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
                      '--output-dir': '.',
                      '--formats': 'MP3 CBR 320,MP3 VBR 0',
                      '--list-file': 'False',
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

            for fmt in config['--formats']:
                dest_dir = os.path.join(transcode_dirs[fmt], reldir)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                if ext not in AUDIO_EXTENSIONS:
                    dest = os.path.abspath(os.path.join(dest_dir, filename))
                    command = [COPY, source_file, dest]
                    yield Task(command)
                else:
                    decoder = ext_codec_map[ext][0]
                    encoder = format_codec_map[fmt.type][0]
                    wav_name = name + '.wav'
                    wav_dest = os.path.abspath(os.path.join(dest_dir, wav_name))
                    dest_name = name + encoder.extension
                    dest = os.path.abspath(os.path.join(dest_dir, dest_name))
                    decode_command = decoder.decode(source_file,
                                                    wav_dest,
                                                    **encoder.encode_requires())
                    encode_command = encoder.encode(wav_dest,
                                                    dest,
                                                    fmt.subtype)
                    rm_command = [RM, wav_dest]
                    metacopy_command = ['metacopy', source_file, dest]
                    yield Task(decode_command,
                               encode_command,
                               rm_command,
                               metacopy_command
                               )

            #A file extension for a lossy format is to be ignored with a warning
            #if ext in LOSSY_EXT:
                #print('WARNING: {} is a lossy file and was skipped during transcoding'.format(os.path.join(dirpath, filename)))
                #continue
            #for fmt in config['--formats']:
                #dest_dir = os.path.join(transcode_dirs[fmt], reldir)
                #if not os.path.exists(dest_dir):
                    #os.makedirs(dest_dir)
                #A file extension not recognized as lossy or lossless will be copied
                #if ext not in LOSSLESS_EXT:
                    #dest = os.path.abspath(os.path.join(dest_dir, filename))
                    #command = [COPY, source_file, dest]
                    #yield Task(command)
                #else:  # This file will be transcoded
                    #dest_name = name + CODEC_EXTENSIONS[fmt]
                    #dest = os.path.abspath(os.path.join(dest_dir, dest_name))
                    #command = transcode_commands[fmt]
                    #xcode_command = command_substitute(command, inpt=source_file, outpt=dest)
                    #yield Task(xcode_command)


def iter_targets(config):
    """Iterating over targets"""
    if config['--list-file']:
        for listfile in config['<target>']:
            print('Processing listfile: {}'.format(listfile))
            with open(listfile, 'r') as lf:
                for target_line in lf:
                    if target_line.startswith('#'):  # Allows comment lines starting with "#"
                        continue
                    target = target_line.rstrip()
                    if target == '':
                        continue
                    print('Processing {} for transcoding'.format(target))
                    for task in traverse_target(os.path.abspath(target), config):
                        yield task
    else:
        for target in config['<target>']:
            print('Processing {} for transcoding'.format(target))
            for task in traverse_target(os.path.abspath(target), config):
                yield task


def task_caller(task):
    task()
    #try:
        #task()
    #except Exception as e:
        #print('ERROR: {}'.format(e))


def format_destinations(source, config):
    """
    Produce a mapping of format to transcode destination.
    Utilizes the path information of the source and the output directory.
    """
    output_dir = os.path.abspath(config['--output-dir'])
    mapping = {}
    source_name = os.path.basename(os.path.abspath(source))
    for fmt in config['--formats']:
        transcode_name = source_name.rstrip() + ' [{} {}]'.format(fmt.type, fmt.subtype)
        dest = os.path.join(output_dir, transcode_name)
        mapping[fmt] = dest
    #fmt_re = re.compile(r'\[(' + '|'.join([codec for codec in CODECS]) + r')\](?!.*\/.*)', flags=re.IGNORECASE)
    #for fmt in config['--formats']:
        #dir_has_codec = fmt_re.search(source_name) is not None
        #if dir_has_codec:
            #transcode_name = fmt_re.sub('[{}]'.format(fmt.upper()), source_name)
        #else:
            #transcode_name = source_name.rstrip() + ' [{}]'.format(fmt.upper())
        #dest = os.path.join(output_dir, transcode_name)
        #mapping[fmt] = dest
    return mapping


def iter_destinations(config):
    """
    Iterate over all of the transcode destinations, for all targets and formats.
    """
    for target in config['<target>']:
        mapping = format_destinations(target, config)
        for v in mapping.values():
            yield v


def scan_filetypes(config):
    """
    Traverse targets and compose the set of all input audio filetypes.
    """
    filetypes = set()
    for target in config['<target>']:
        for _dirpath, _dirs, filenames in os.walk(target):
            for filename in filenames:
                _name, ext = os.path.splitext(filename)
                if ext in LOSSLESS_EXT or ext in LOSSY_EXT:
                    filetypes.add(ext)
    return filetypes

def main():
    args = docopt(__doc__, version=__version__)

    if args['--show-formats']:
        print('The following format strings are available on your system:')
        formats = set()
        for key in format_codec_map:
            for cdc in format_codec_map[key]:
                for fmt in cdc.formats:
                    if fmt == '':
                        formats.add(key)
                    else:
                        formats.add(' '.join([key, fmt]))
        for fmt in sorted(formats):
            print(' ' + fmt)
        sys.exit(0)

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

    resolve_configuration(args['--config'], config)

    #Apply any arg options as overrides of the loaded config file
    bconf = merge_conf(args, config['OATS'])

    #Argument normalization
    bconf['--processes'] = None if bconf['--processes'] == '0' else int(bconf['processes'])
    bconf['--source'] = None if bconf['--source'] == 'None' else bconf['--source']
    bconf['--torrent'] = True if bconf['--torrent'].lower() in ['1','t','true'] else False
    bconf['--list-file'] = True if bconf['--list-file'] in [True, 'true', 'True'] else False
    #Normalization of formats into list of namedtuple('Format', ['type', 'subtype'])
    format_tuple = namedtuple('Format', ['type', 'subtype'])
    raw_formats = bconf['--formats']
    bconf['--formats'] = []
    for raw_format in raw_formats.upper().split(','):
        if raw_format == '':  # Ignore empty format fields
            continue
        try:
            typ, subtype = raw_format.split(' ', 1)
        except ValueError:
            typ, subtype = raw_format, ''
        bconf['--formats'].append(format_tuple(typ, subtype))

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

    #Acquire a complete set of all input audio filetypes
    input_filetypes = scan_filetypes(bconf)
    #Check to see if there are any input audio filetypes not currently supported
    for input_filetype in input_filetypes:
        if input_filetype not in ext_codec_map:
            raise NotSupportedError('OATS found an audio filetype it does not (yet) support as input: {}'.format(input_filetype))

    #Determine if any requested formats have no codec tools
    for fmt in bconf['--formats']:
        if fmt.type not in format_codec_map:
            raise InvalidConfiguration('The format of type "{}" is not known to OATS'.format(fmt.type))
        if not format_codec_map[fmt.type]:  #The list of available codec tools is empty
            raise InvalidConfiguration('No valid tools for "{}" on the system'.format(fmt.type))
        else:
            if fmt.subtype not in format_codec_map[fmt.type][0].formats:
                print(format_codec_map[fmt.type][0].formats)
                raise InvalidConfiguration('Codec tool for type "{}" does not recognize subtype "{}"'.format(fmt.type, fmt.subtype))

    #Make output directory if necessary
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
