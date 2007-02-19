from setuptools import setup, find_packages

from coherence import __version__

setup(
      name="Coherence",
      version=__version__,
      description="""Coherence - Python framework for the digital living""",
      author="Frank Scholz",
      author_email='coherence@beebits.net',
      license = "MIT",
      packages=find_packages(),
      scripts = ['bin/coherence'],
      url = "http://coherence.beebits.net",

    #package_dir = {'':'coherence'},   # tell distutils packages are under src

    package_data = {
        'coherence': ['upnp/core/xml-service-descriptions/*.xml',
		'web/static/*.css','web/static/*.js'],
    }
      )
