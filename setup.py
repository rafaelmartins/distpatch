#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    setup.py
    ~~~~~~~~

    :copyright: (c) 2011 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

import os

from setuptools import setup, find_packages
from distpatch import __version__

cwd = os.path.dirname(os.path.abspath(__file__))


setup(
    name='distpatch',
    version=__version__,
    license='GPL-2',
    description='Distfile patching support for Gentoo Linux (tools)',
    long_description=open(os.path.join(cwd, 'README.rst')).read(),
    author='Rafael Goncalves Martins',
    author_email='rafaelmartins@gentoo.org',
    url='http://www.gentoo.org/proj/en/infrastructure/distpatch/',
    platforms='Gentoo Linux',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        # portage would be listed here, but it isn't installed by setuptools/distutils
        'snakeoil',
    ],
    scripts=['distdiffer', 'distpatcher', 'distpatchq'],
)
