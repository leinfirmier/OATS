"""
This is the setup file for OATS
"""

from distutils.core import setup

from oats import __version__

def long_description():
    with open('README.md', 'r') as readme:
        readme_text = readme.read()
    return(readme_text)

setup(name='OATS',
      version=__version__,
      description='A tool for the transcoding of audio from lossless sources',
      long_description=long_description(),
      url='https://github.com/leinfirmier/OATS',
      download_url='https://github.com/leinfirmier/OATS/archive/{}.tar.gz'.format(__version__),
      packages=['oats',],
      entry_points = {'console_scripts': ['oats = oats.script:main',
                                          'metacopy = oats.metacopy:main']},
      data_files=[('', ['README.md'])],
      classifiers=['Intended Audience :: End Users/Desktop',
                   'Environment :: Console',
                   'License :: Public Domain',
                   'Topic :: Multimedia :: Sound/Audio :: Conversion',
                   'Topic :: Utilities',
                   'Programming Language :: Python :: 3',
                   'Operating System :: OS Independent',
                   ],
      install_requires=['docopt',
                        'mutagen'],
      )

