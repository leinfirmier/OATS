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
      author='leinfirmier',
      url='https://github.com/leinfirmier/OATS',
      packages=['oats',],
      entry_points = {'console_scripts': ['oats = oats.script:main']},
      data_files=[('', ['README.md'])],
      classifiers=[''],
      install_requires=['docopt'],
      )

