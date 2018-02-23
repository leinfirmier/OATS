import os
import platform
import subprocess
import shlex

class Codec(object):
    """
    Codec is the base class for the Coder/Decoder tools for OATS.
    """
    depends = '<tool>'  # This should correspond to the command invocation for the underlying tool.
    formats = {}        # A dictionary mapping format strings to encoding options.
    extension = ''      # The file extension associated with the codec type.

    @classmethod
    def on_system(cls):
        if platform.system() == 'Windows':
            command = 'where.exe {}'.format(shlex.quote(cls.depends))
        else:  # unix
            command = 'command -v {}'.format(shlex.quote(cls.depends))
        try:
            subprocess.check_call(command,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                  shell=True)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

    @classmethod
    def encode(cls, wavfile, outfile, fmt):
        """
        The encode method expects a filepath to a wavfile, a format string to
        determine encoding options, and a filepath for the encoded output.

        The format string will be used in most but not all cases.
        """
        raise NotImplementedError

    @classmethod
    def decode(cls, inputfile, wavfile, bit_depth=None, sample_rate=None):
        raise NotImplementedError

    @classmethod
    def encode_requires(cls):
        """
        Passing a format to this method will return a dictionary of parameters
        that must be set for a wavfile in order for successful encoding. Valid
        keys in this dictionary are 'bit_depth' and 'sample_rate'. If there are
        no requirements, returns an empty dictionary.
        """
        return {}


class LAME(Codec):
    depends = 'lame'
    _const = ['-q', '0', '--noreplaygain']
    formats = {'CBR 320': ['--cbr', '-b', '320', *_const],
               'CBR 256': ['--cbr', '-b', '256', *_const],
               'CBR 224': ['--cbr', '-b', '224', *_const],
               'CBR 192': ['--cbr', '-b', '192', *_const],
               'VBR 0'  : ['-V0', '--vbr-new', '-T', *_const],
               'VBR 1'  : ['-V1', '--vbr-new', '-T', *_const],
               'VBR 2'  : ['-V2', '--vbr-new', '-T', *_const],
               'VBR 3'  : ['-V3', '--vbr-new', '-T', *_const],
               'VBR 4'  : ['-V4', '--vbr-new', '-T', *_const],
               'VBR 5'  : ['-V5', '--vbr-new', '-T', *_const],
               'VBR 6'  : ['-V6', '--vbr-new', '-T', *_const],
               'VBR 7'  : ['-V7', '--vbr-new', '-T', *_const],
               'VBR 8'  : ['-V8', '--vbr-new', '-T', *_const],
               'VBR 9'  : ['-V9', '--vbr-new', '-T', *_const],
               'ABR 256': ['--abr', '256', *_const],
               'ABR 224': ['--abr', '224', *_const],
               'ABR 192': ['--abr', '192', *_const],
               'ABR 128': ['--abr', '128', *_const],
               }
    extension = '.mp3'

    @classmethod
    def encode(cls, wavfile, outfile, fmt):
        command = ['lame', *cls.formats[fmt], wavfile, outfile]
        return command

    @classmethod
    def decode(cls, inputfile, wavfile, bit_depth=None, sample_rate=None):
        if bit_depth is not None:
            raise ValueError('bit_depth set on LAME codec which is not supported')
        if sample_rate is not None:
            raise ValueError('sample_rate set on LAME codec which is not supported')
        command = ['lame', '--decode', inputfile, wavfile]
        return command


class FFmpeg(Codec):
    """
    The FFmpeg class provides a basic decoder implementation.
    """
    depends = 'ffmpeg'
    decode_opts = {''     : {},
                   '16'   : {'bit_depth': 16},
                   '24'   : {'bit_depth': 24},
                   '16-44': {'bit_depth': 16, 'sample_rate': 44100},
                   '16-48': {'bit_depth': 16, 'sample_rate': 48000},
                   '24-48': {'bit_depth': 24, 'sample_rate': 48000},
                   '24-44': {'bit_depth': 24, 'sample_rate': 44100},
                   }

    @classmethod
    def decode(cls, inputfile, wavfile, bit_depth=None, sample_rate=None):
        command = ['ffmpeg', '-threads', '1', '-i', inputfile]
        if bit_depth is not None:
            bitdepthmap = {16: 'pcm_s16le', 24: 'pcm_s24le', 32: 'pcm_s32le'}
            command += ['-c:a', bitdepthmap[decode_opts['bit_depth']]]
        if sample_rate is not None:
            command += ['-ar', str(decode_opts['sample_rate']),
                        '-af', 'aresample=resampler=soxr']
        command += [wavfile]
        return command


class FFmpegMP3(FFmpeg):
    _const = ['-compression_level', '0']
    formats = {'CBR 320': ['-b:a', '320k', *_const],
               'CBR 256': ['-b:a', '256k', *_const],
               'CBR 224': ['-b:a', '224k', *_const],
               'CBR 192': ['-b:a', '192k', *_const],
               'VBR 0'  : ['-q:a', '0', *_const],
               'VBR 1'  : ['-q:a', '1', *_const],
               'VBR 2'  : ['-q:a', '2', *_const],
               'VBR 3'  : ['-q:a', '3', *_const],
               'VBR 4'  : ['-q:a', '4', *_const],
               'VBR 5'  : ['-q:a', '5', *_const],
               'VBR 6'  : ['-q:a', '6', *_const],
               'VBR 7'  : ['-q:a', '7', *_const],
               'VBR 8'  : ['-q:a', '8', *_const],
               'VBR 9'  : ['-q:a', '9', *_const],
               'ABR 256': ['-b:a', '256k', '--abr', '1', *_const],
               'ABR 224': ['-b:a', '224k', '--abr', '1', *_const],
               'ABR 192': ['-b:a', '192k', '--abr', '1', *_const],
               'ABR 128': ['-b:a', '128k', '--abr', '1', *_const],
               }
    extension='.mp3'

    @classmethod
    def encode(cls, wavfile, outfile, fmt):
        head = ['ffmpeg', '-threads', '1', '-i']
        command = [*head , wavfile, '-c:a', 'libmp3lame', *cls.formats[fmt], outfile]
        return command


class FFmpegFLAC(FFmpeg):
    formats = {''     : [],
               '16'   : [],
               '24'   : [],
               '16-44': [],
               '16-48': [],
               '24-44': [],
               '24-48': [],
               }
    extension='.flac'
    #http://ffmpeg.org/ffmpeg-resampler.html

    @classmethod
    def encode(cls, wavfile, outfile, fmt):
        command = ['ffmpeg', '-threads', '1', '-i', wavfile,
                   '-compression_level', '0',
                   outfile]
        return command

    @classmethod
    def encode_requires(cls, fmt):
        if fmt in cls.decode_opts:
            return cls.decode_opts[fmt]
        else:
            return {}

