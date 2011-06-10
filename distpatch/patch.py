# -*- coding: utf-8 -*-

from itertools import izip
from portage.package.ebuild.fetch import fetch
from shutil import move
from subprocess import call
from deltadb import DeltaDBFile
from helpers import uncompressed_filename_and_compressor

import os
import portage
import posixpath
import re

re_diff_filename = re.compile(r'(?P<dest>.+)\.(?P<format>[^(\.xz)]+)(\.xz)?$')

class PatchException(Exception):
    pass


class Patch:
    
    def __init__(self, *dbrecords):
        if len(dbrecords) == 0:
            raise PatchException('Patch requires an argument')
        self.dbrecords = dbrecords
        self.src = dbrecords[0].src
        self.dest = dbrecords[-1].dest
        self.udest = dbrecords[-1].udest
        if not self._verify_deltas():
            raise PatchException('Invalid delta sequence: %s' % self.dbrecords)

    def fetch_deltas(self, output_dir=None):
        # mirror://gentoo/ will fail for now... portage needs a patch
        root_url = os.environ.get('DELTAS_ROOT_URL', 'mirror://gentoo')
        if root_url == 'mirror://gentoo/':
            raise PatchException('You should set the environment variable DELTAS_ROOT_URL.')
        if output_dir is None:
            output_dir = os.path.join(portage.settings['DISTDIR'], 'patches')
        mysettings = portage.config(clone=portage.settings)
        mysettings['DISTDIR'] = output_dir
        urls = []
        for record in self.dbrecords:
            urls.append(posixpath.join(root_url, record.delta.fname))
        if not fetch(urls, mysettings):
            raise PatchException('Failed to fetch deltas: %s' % urls)

    def _verify_deltas(self):
        self.patch_format = None
        for record in self.dbrecords:
            rv = re_diff_filename.match(record.delta.fname)
            if rv is None:
                return False
            patch_format = rv.groupdict()['format']
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
        dest, compressor = uncompressed_filename_and_compressor(self.dest.fname)
        dest = os.path.join(output_dir, dest)
        deltas = [os.path.join(input_dir, i.delta.fname) for i in self.dbrecords]

        # validate source and deltas before recompose
        if self.src != DeltaDBFile(src):
            raise PatchException('Bad checksum for source: %s' % self.src.fname)
        for delta, delta_record in izip(deltas, self.dbrecords):
            if delta_record.delta != DeltaDBFile(delta):
                raise PatchException('Bad checksum for delta: %s' % \
                                     delta_record.delta.fname)
        
        cmd = [patcher, src, '--patch-format', self.patch_format] + deltas
        cmd.append(dest)

        if call(cmd) != os.EX_OK:
            raise PatchException('Failed to reconstruct file: %s' % dest)

        # validate checksums for uncompressed destination
        if self.udest != DeltaDBFile(dest):
            raise PatchException('Bad checksum for uncompressed destination: %s' % \
                                 self.dest.fname)

        if compress and compressor is not None:
            if call([compressor, dest]) != os.EX_OK:
                raise PatchException('Failed to compress reconstructed file: %s' % \
                                     dest)
            dest += os.path.splitext(self.dest.fname)[1]
            if self.dest != DeltaDBFile(dest):
                invalid_dir = os.path.join(output_dir, 'delta-reconstructed')
                if not os.path.exists(invalid_dir):
                    os.makedirs(invalid_dir)
                move(dest, os.path.join(invalid_dir, os.path.basename(dest)))
        self.dest_distfile = dest

    def __str__(self):
        return ' -> '.join([i.delta.fname for i in self.dbrecords])

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.__str__())
