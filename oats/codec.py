import os
import platform
import subprocess
import shlex

def sane_int(valstr, valname, minval=None, maxval=None, permitted=None):
    try:
        valint = int(valstr)
    except ValueError:
        raise ValueError("invalid value for {}, must be integer: '{}'".format(valname, valstr))
    if minval is not None:
        if valint < minval:
            raise ValueError("invalid value for {}: {} is less than minimum {}".format(valname, valint, minval))
    if maxval is not None:
        if valint > maxval:
            raise ValueError("invalid value for {}: {} is more than maximum {}".format(valname, valint, maxval))
    if permitted is not None:
        if valint not in permitted:
            raise ValueError("invalid value for {}: {} is not one of {}".format(valname, valint, permitted))
    return valint

def sane_float(valstr, valname, minval=None, maxval=None):
    try:
        valflt = float(valstr)
    except ValueError:
        raise ValueError("invalid value for {}, must be float: '{}'".format(valname, valstr))
    if minval is not None:
        if valflt < minval:
            raise ValueError("invalid value for {}: {} is less than minimum {}".format(valname, valflt, minval))
    if maxval is not None:
        if valflt > maxval:
            raise ValueError("invalid value for {}: {} is more than maximum {}".format(valname, valflt, maxval))
    return valflt


class Codec(object):
    """
    Codec is the base class for the Coder/Decoder tools for OATS.
    """
    depends = '<tool>'  # This should correspond to the command invocation for the underlying tool.
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
        return cls._encode(wavfile, outfile, [w.upper() for w in fmt.split(' ')])

    @classmethod
    def _encode(cls, wavfile, outfile, fmt):
        raise NotImplementedError

    @classmethod
    def decode(cls, inputfile, wavfile, bit_depth=None, sample_rate=None):
        raise NotImplementedError

    @classmethod
    def encode_requires(cls, fmt):
        """
        Passing a format to this method will return a dictionary of parameters
        that must be set for a wavfile in order for successful encoding. Valid
        keys in this dictionary are 'bit_depth' and 'sample_rate'. If there are
        no requirements, returns an empty dictionary.
        """
        return cls._encode_requires([w.upper() for w in fmt.split(' ')])

    @classmethod
    def _encode_requires(cls, fmt):
        return {}


class FFmpeg(Codec):
    """
    The FFmpeg class provides a basic decoder implementation.
    """
    depends = 'ffmpeg'
    template = ''

    @classmethod
    def decode(cls, inputfile, wavfile, bit_depth=None, sample_rate=None):
        command = ['ffmpeg', '-threads', '1', '-i', inputfile]
        if bit_depth is not None:
            bitdepthmap = {8: 'pcm_s8le', 16: 'pcm_s16le', 24: 'pcm_s24le', 32: 'pcm_s32le'}
            command += ['-c:a', bitdepthmap[bit_depth]]
        if sample_rate is not None:
            command += ['-ar', str(sample_rate),
                        '-af', 'aresample=resampler=soxr']
        command += [wavfile]
        return command


class LAME(Codec):
    depends = 'lame'
    formats = ['CBR \d+',
               'ABR \d+',
               'VBR \d']
    templates = ['CBR {bitrate;kbps:8-320}',
                 'ABR {bitrate;kbps:8-320}',
                 'VBR {quality:0-9}']
    extension = '.mp3'

    @classmethod
    def _encode(cls, wavfile, outfile, fmt):
        constants = ['-q', '0', '--noreplaygain']
        #Valid format checks
        if fmt[0] not in ['VBR', 'CBR', 'ABR']:
            raise ValueError("LAME expects a format type of CBR, ABR, or VBR: '{}'".format(fmt[0]))
        if len(fmt) != 2:
            raise ValueError("LAME expects a bitrate for CBR|ABR, or a quality for VBR: '{}'".format(' '.join(fmt)))
        #If checks passed, continue to return command lists
        if fmt[0] == 'CBR':
            bitrate = sane_int(fmt[1], 'LAME CBR bitrate',
                               minval=8, maxval=320)
            return ['lame', '--cbr', '-b', str(bitrate)] + constants + [wavfile, outfile]
        elif fmt[0] == 'ABR':
            bitrate = sane_int(fmt[1], 'LAME ABR bitrate',
                               minval=8, maxval=320)
            return ['lame', '--abr', str(bitrate)] + constants + [wavfile, outfile]
        elif fmt[0] == 'VBR':
            quality = sane_int(fmt[1], 'LAME VBR quality',
                               minval=0, maxval=9)
            return ['lame', '-V'+str(quality), '--vbr-new', '-T'] + constants + [wavfile, outfile]

    @classmethod
    def decode(cls, inputfile, wavfile, bit_depth=None, sample_rate=None):
        if bit_depth is not None:
            raise ValueError('bit depth decode control not supported by LAME')
        if sample_rate is not None:
            raise ValueError('sample rate decode control not supported by LAME')
        command = ['lame', '--decode', inputfile, wavfile]
        return command


class FFmpegMP3(FFmpeg):
    formats = ['CBR \d+',
               'ABR \d+',
               'VBR \d']
    templates = ['CBR {bitrate;kbps:8-320}',
                 'ABR {bitrate;kbps:8-320}',
                 'VBR {quality:0-9}']
    extension='.mp3'

    @classmethod
    def _encode(cls, wavfile, outfile, fmt):
        head = ['ffmpeg', '-threads', '1', '-i', wavfile]
        #0 is the slowest, highest quality compression for libmp3lame
        tail = ['-compression_level', '0', outfile]
        #Valid format checks
        if fmt[0] not in ['VBR', 'CBR', 'ABR']:
            raise ValueError("FFmpegMP3 expects a format type of CBR, ABR, or VBR: '{}'".format(fmt[0]))
        if len(fmt) != 2:
            raise ValueError("FFmpegMP3 expects a bitrate for CBR|ABR, or a quality for VBR: '{}'".format(' '.join(fmt)))

        #If checks passed, continue to return command lists
        if fmt[0] == 'CBR':
            bitrate = sane_int(fmt[1], 'FFmpegMP3 CBR bitrate',
                               minval=8, maxval=320)
            return head + ['-b:a', '{}k'.format(bitrate)] + tail
        elif fmt[0] == 'ABR':
            bitrate = sane_int(fmt[1], 'FFmpegMP3 ABR bitrate',
                               minval=8, maxval=320)
            return head + ['-c:a', 'libmp3lame', '-b:a', '{}k'.format(bitrate), '--abr', '1'] + tail
        elif fmt[0] == 'VBR':
            quality = sane_int(fmt[1], 'FFmpegMP3 VBR quality',
                               minval=0, maxval=9)
            return head + ['-c:a', 'libmp3lame', '-q:a', str(quality)] + tail


class FFmpegFLAC(FFmpeg):
    formats = ['\d+[ \-]\d+']
    templates = ['',
                 '{bit_depth:8,16,24,32,*} {sample_rate;Hz}']
    #Common sample rates: 44100, 44000, 88000, 96000
    #bit depths: 8, 16, 24, 32
    extension='.flac'
    #http://ffmpeg.org/ffmpeg-resampler.html

    @classmethod
    def _encode(cls, wavfile, outfile, fmt):
        #12 is the slowest, highest quality compression for flac
        return ['ffmpeg', '-threads', '1', '-i', wavfile,
                '-c:a', 'flac', '-compression_level', '12', outfile]

    @classmethod
    def _encode_requires(cls, fmt):
        retdict = {}
        if len(fmt) == 0:
            return retdict
        if len(fmt) != 2:
            raise ValueError('FFmpegFLAC expects a bit_depth and a sample_rate: {}'.format(fmt))
        if fmt[0] != '*':
            retdict['bit_depth'] = sane_int(fmt[0], 'FFmpegFLAC bit_depth',
                                            permitted=[8,16,24,32])
        if fmt[1] != '*':
            retdict['sample_rate'] = sane_int(fmt[1], 'FFmpegFLAC sample_rate')
        return retdict


class FFmpegOpus(FFmpeg):
    formats = ['CBR \d+',
               'VBR \d+',
               'CVBR \d+',
               ]
    templates = ['CBR {bitrate;kbps:8-512}',
                 'VBR {bitrate;kbps:8-512}',
                 'CVBR {bitrate;kbps:8-512}',
                 ]
    extension = '.opus'

    @classmethod
    def _encode(cls, wavfile, outfile, fmt):
        head = ['ffmpeg', '-threads', '1', '-i', wavfile, '-c:a', 'libopus']
        br_types = {'CBR' : ['-vbr', 'off', '-b:a'],
                    'VBR' : ['-vbr', 'on', '-b:a'],
                    'CVBR': ['-vbr', 'constrained', '-b:a']
                    }
        #Valid format checks
        if fmt[0] not in br_types:
            raise ValueError("FFmpegOpus expects a format type of {}: '{}'".format(', '.join(br_types), fmt[0]))
        if len(fmt) != 2:
            raise ValueError("FFmpegOpus expects a bitrate for {}: '{}'".format(fmt[0], ' '.join(fmt)))
        #If checks passed, continue to return command lists
        bitrate = sane_int(fmt[1], 'FFmpegOpus bitrate', minval=8, maxval=512)
        br_type = br_types[fmt[0]]
        #10 is the slowest, highest quality compression for opusenc
        return head + br_type + ['{}k'.format(bitrate), '-compresson_level', '10', outfile]


class OpusTools(Codec):
    depends = 'opusenc'
    formats = ['CBR \d+',
               'VBR \d+',
               'CVBR \d+',
               ]
    templates = ['CBR {bitrate;kbps:8-512}',
                 'VBR {bitrate;kbps:8-512}',
                 'CVBR {bitrate;kbps:8-512}',
                 ]
    extension = '.opus'

    @classmethod
    def _encode(cls, wavfile, outfile, fmt):
        br_types = {'CBR': '--hard-cbr', 'VBR': '--vbr', 'CVBR': '--cvbr'}
        #Valid format checks
        if fmt[0] not in br_types:
            raise ValueError("OpusTools expects a format type of {}: '{}'".format(', '.join(br_types), fmt[0]))
        if len(fmt) != 2:
            raise ValueError("OpusTools expects a bitrate for {}: '{}'".format(fmt[0], ' '.join(fmt)))
        #If checks passed, continue to return command lists
        bitrate = sane_int(fmt[1], 'OpusTools bitrate', minval=8, maxval=512)
        br_type = br_types[fmt[0]]
        #10 is the slowest, highest quality compression for opusenc
        return ['opusenc', '--bitrate', str(bitrate), '--comp', '10', br_type, wavfile, outfile]

    @classmethod
    def decode(cls, inputfile, wavfile, bit_depth=None, sample_rate=None):
        command = ['opusdec']
        if sample_rate is not None:
            command += ['--rate', str(sample_rate)]
        if bit_depth is not None:
            raise ValueError('bit depth decode control not supported by opusdec')
        command += [inputfile, wavfile]
        return command


class FFmpegVorbis(FFmpeg):
    depends = 'ffmpeg'
    formats = ['VBR -?[0-9]+(\.[0-9]{1,2})?',
               'ABR \d+',
               'MANAGED (((MAX\d+)|(MIN\d+)|(B\d+))+ ?)+']
    templates = ['VBR {quality:\-1.0-10.0}',
                 'ABR {bitrate;kbps:45-500}',
                 'MANAGED [MAX{max-bitrate;kbps:>=1}] [MIN{min-bitrate;kbps:>=1}] [B{bitrate;kbps:45-500}]']
    extension = '.vorbis'

    @classmethod
    def _encode(cls, wavfile, outfile, fmt):
        br_types = {'ABR', 'VBR', 'MANAGED'}
        head = ['ffmpeg', '-threads', '1', '-i', wavfile, '-vn', '-c:a', 'libvorbis', '-f', 'ogg']
        if fmt[0] not in br_types:
            raise ValueError("FFmpegVorbis expects a format type of {}: '{}'".format(', '.join(br_types), fmt[0]))
        if fmt[0] == 'VBR':
            if len(fmt) != 2:
                raise ValueError("FFmpegVorbis expects a quality value for VBR: '{}'".format(' '.join(fmt)))
            quality = sane_float(fmt[1], 'FFmpegVorbis quality', minval=-1.0, maxval=10)
            return head + ['-q', str(quality), outfile]
        elif fmt[0] == 'ABR':
            if len(fmt) != 2:
                raise ValueError("FFmpegVorbis expects a bitrate value for ABR: '{}'".format(' '.join(fmt)))
            bitrate = sane_int(fmt[1], 'FFmpegVorbis average bitrate', minval=45, maxval=500)
            return head + ['-b', str(bitrate), outfile]
        elif fmt[0] == 'MANAGED':
            command = head
            maxbitrate, minbitrate, bitrate = None, None, None
            for word in fmt[1:]:
                if word.startswith('MAX'):
                    if maxbitrate is None:
                        maxbitrate = sane_int(word[3:], 'FFmpegVorbis Managed Max Bitrate', minval=1)
                    else:
                        raise ValueError('Duplicate Max Bitrate: {}'.format(' '.join(fmt)))
                elif word.startswith('MIN'):
                    if minbitrate is None:
                        minbitrate = sane_int(word[3:], 'FFmpegVorbis Managed Min Bitrate', minval=1)
                    else:
                        raise ValueError('Duplicate Min Bitrate: {}'.format(' '.join(fmt)))
                elif word.startswith('B'):
                    if bitrate is None:
                        bitrate = sane_int(word[1:], 'FFmpegVorbis Managed Target Bitrate', minval=1)
                    else:
                        raise ValueError('Duplicate Target Bitrate: {}'.format(' '.join(fmt)))
                else:
                    raise ValueError('Unable to parse FFmpegVorbis Managed format: {}'.format(' '.join(fmt)))
            if maxbitrate is None and minbitrate is None and bitrate is None:
                print('WARNING: Vorbis Managed Mode with no options: equivalent to VBR 3')
            if maxbitrate is not None:
                command += ['-maxrate', str(maxbitrate)]
            if minbitrate is not None:
                command += ['-minrate', str(minbitrate)]
            if bitrate is not None:
                command += ['-b:a', str(bitrate)]
            return command + [wavfile]


class OggVorbis(Codec):
    depends = 'oggenc'
    formats = ['VBR -?[0-9]+(\.[0-9]{1,2})?',
               'ABR \d+',
               'MANAGED (((MAX\d+)|(MIN\d+)|(B\d+))+ ?)+']
    templates = ['VBR {quality:\-1.0-10.0}',
                 'ABR {bitrate;kbps:45-500}',
                 'MANAGED [MAX{max-bitrate;kbps:>=1}] [MIN{min-bitrate;kbps:>=1}] [B{bitrate;kbps:45-500}]']
    extension = '.vorbis'

    @classmethod
    def _encode(cls, wavfile, outfile, fmt):
        br_types = {'ABR', 'VBR', 'MANAGED'}
        if fmt[0] not in br_types:
            raise ValueError("OggVorbis expects a format type of {}: '{}'".format(', '.join(br_types), fmt[0]))
        if fmt[0] == 'VBR':
            if len(fmt) != 2:
                raise ValueError("OggVorbis expects a quality value for VBR: '{}'".format(' '.join(fmt)))
            quality = sane_float(fmt[1], 'OggVorbis quality', minval=-1.0, maxval=10)
            return ['oggenc', '-q', str(quality), '-o', outfile, wavfile]
        elif fmt[0] == 'ABR':
            if len(fmt) != 2:
                raise ValueError("OggVorbis expects a bitrate value for ABR: '{}'".format(' '.join(fmt)))
            bitrate = sane_int(fmt[1], 'OggVorbis average bitrate', minval=45, maxval=500)
            return ['oggenc', '-b', str(bitrate), '-o', outfile, wavfile]
        elif fmt[0] == 'MANAGED':
            command = ['oggenc', '--managed', '-o', outfile]
            maxbitrate, minbitrate, bitrate = None, None, None
            for word in fmt[1:]:
                if word.startswith('MAX'):
                    if maxbitrate is None:
                        maxbitrate = sane_int(word[3:], 'OggVorbis Managed Max Bitrate', minval=1)
                    else:
                        raise ValueError('Duplicate Max Bitrate: {}'.format(' '.join(fmt)))
                elif word.startswith('MIN'):
                    if minbitrate is None:
                        minbitrate = sane_int(word[3:], 'OggVorbis Managed Min Bitrate', minval=1)
                    else:
                        raise ValueError('Duplicate Min Bitrate: {}'.format(' '.join(fmt)))
                elif word.startswith('B'):
                    if bitrate is None:
                        bitrate = sane_int(word[1:], 'OggVorbis Managed Target Bitrate', minval=1)
                    else:
                        raise ValueError('Duplicate Target Bitrate: {}'.format(' '.join(fmt)))
                else:
                    raise ValueError('Unable to parse OggVorbis Managed format: {}'.format(' '.join(fmt)))
            if maxbitrate is None and minbitrate is None and bitrate is None:
                print('WARNING: Vorbis Managed Mode with no options: equivalent to VBR 3')
            if maxbitrate is not None:
                command += ['--max-bitrate', str(maxbitrate)]
            if minbitrate is not None:
                command += ['--min-bitrate', str(minbitrate)]
            if bitrate is not None:
                command += ['-b', str(bitrate)]
            return command + [wavfile]

    @classmethod
    def decode(cls, inputfile, wavfile, bit_depth=None, sample_rate=None):
        command = ['oggdec']
        if sample_rate is not None:
            ValueError('sample rate decode control not supported by oggdec')
        if bit_depth is not None:
            if bit_depth not in [8, 16]:
                raise ValueError('oggdec bit depth decode control only supports 8 or 16 bit')
            else:
                command += ['-b', str(bit_depth)]
        command += ['-o', wavfile, inputfile]
        return command
