# -*- coding: utf-8 -*-
"""
    distpatch.patch
    ~~~~~~~~~~~~~~~

    Basic stuff to reconstruct files from deltas.

    :copyright: (c) 2011 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

import os
import portage
import posixpath
import re


from portage.package.ebuild.fetch import fetch
from shutil import move
from subprocess import call

from distpatch.chksums import Chksum
from distpatch.deltadb import DeltaDBFile, DeltaDBRecord
from distpatch.helpers import uncompressed_filename_and_compressor

re_diff_filename = re.compile(r'(?P<dest>.+)\.(?P<format>[^(\.xz)]+)(\.xz)?$')


class PatchException(Exception):
    pass


class Patch(object):

    def __init__(self, *dbrecords):

        # validate dbrecords
        if len(dbrecords) == 0:
            raise PatchException('%s requires 1 or more %s objects as ' \
                                 'arguments' % (self.__class__.__name__,
                                                DeltaDBRecord.__name__))
        for record in dbrecords:
            if not isinstance(record, DeltaDBRecord):
                raise PatchException('Invalid argument for %s: %r' % \
                                     (self.__class__.__name__, record))

        self.dbrecords = dbrecords
        self.src = self.dbrecords[0].src
        self.dest = self.dbrecords[-1].dest
        if not self._verify_deltas():
            raise PatchException('Invalid delta series: %s' % self.dbrecords)

    def fetch_deltas(self, root_url, output_dir=None):
        if output_dir is None:
            output_dir = os.path.join(portage.settings['DISTDIR'], 'patches')
        mysettings = portage.config(clone=portage.settings)
        mysettings['DISTDIR'] = output_dir
        urls = []
        for record in self.dbrecords:
            urls.append(posixpath.join(root_url, record.delta.fname))
        if 'distpatch' in mysettings.features:
            mysettings.features.remove('distpatch')
        if not fetch(urls, mysettings):
            raise PatchException('Failed to fetch deltas: %s' % urls)

    def _verify_deltas(self):
        self.patch_format = None
        for record in self.dbrecords:
            rv = re_diff_filename.match(record.delta.fname)
            if rv is None:
                return False
            patch_format = rv.groupdict().get('format')
            if self.patch_format is None:
                self.patch_format = patch_format
                continue
            if self.patch_format != patch_format:
                return False
        return True

    def reconstruct(self, input_dir=None, output_dir=None, compress=True):
        diffball_bindir = os.environ.get('DIFFBALL_BINDIR', '/usr/bin')
        patcher = os.path.join(diffball_bindir, 'patcher')
        distdir = portage.settings['DISTDIR']
        if input_dir is None:
            input_dir = os.path.join(distdir, 'patches')
        if output_dir is None:
            output_dir = distdir
        src = os.path.join(distdir, self.src.fname)
        dest, compressor = uncompressed_filename_and_compressor(
            self.dest.fname)
        dest = os.path.join(output_dir, dest)
        deltas = [os.path.join(input_dir, i.delta.fname) \
                  for i in self.dbrecords]

        # validate source and deltas before recompose
        if self.src != DeltaDBFile(src):
            raise PatchException('Bad checksum for source: %s' % \
                                 self.src.fname)
        for delta, delta_record in zip(deltas, self.dbrecords):
            if delta_record.delta != DeltaDBFile(delta):
                raise PatchException('Bad checksum for delta: %s' % \
                                     delta_record.delta.fname)

        # recompose :)
        cmd = [patcher, src, '--patch-format', self.patch_format]
        cmd.extend(deltas)
        cmd.append(dest)
        if call(cmd) != os.EX_OK:
            raise PatchException('Failed to reconstruct file: %s' % dest)

        # validate checksums for uncompressed destination
        if self.dest.uchksums != Chksum(dest):
            raise PatchException(
                'Bad checksum for uncompressed destination: %s' % \
                self.dest.fname)

        # compress the destination file, if needed.
        if compress and compressor is not None:
            if call([compressor, dest]) != os.EX_OK:
                raise PatchException(
                    'Failed to compress reconstructed file: %s' % dest)
            dest += os.path.splitext(self.dest.fname)[1]
            if self.dest.chksums != Chksum(dest):
                invalid_dir = os.path.join(output_dir, 'delta-reconstructed')
                if not os.path.exists(invalid_dir):
                    os.makedirs(invalid_dir)
                move(dest, invalid_dir)
        self.dest_distfile = dest

    def __str__(self):
        return ' -> '.join([i.delta.fname for i in self.dbrecords])

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.__str__())
