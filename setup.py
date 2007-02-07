from setuptools import setup, find_packages

setup(
      name="Coherence",
      version="0.1",
      description="""Coherence - Python framework for the digital living""",
      author="Frank Scholz",
      author_email='coherence@beebits.net',
      license = "MIT",
      packages=find_packages(),
      scripts = ['bin/coherence'],
      url = "http://coherence.beebits.net",
      )
