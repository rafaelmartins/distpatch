# -*- coding: utf-8 -*-

import os
import portage

from shutil import copy2, rmtree
from subprocess import call

from distpatch.chksums import Chksum
from distpatch.deltadb import DeltaDBFile, DeltaDBRecord
from distpatch.ebuild import Distfile
from distpatch.helpers import uncompress, tempdir
from distpatch.patch import Patch, PatchException


class DiffException(Exception):
    pass


class DiffExists(Exception):
    pass


class DiffUnsupported(Exception):
    pass


_supported_formats = [
    u'.tar',
    u'.tar.gz', u'.tgz', u'.gz',
    u'.tar.bz2', u'.tbz2', u'.bz2',
    u'.tar.xz', u'.xz',
    u'.tar.lzma', u'.ĺzma',
]


class Diff:

    patch_format = 'switching'

    def __init__(self, src, dest):
        if not isinstance(src, Distfile):
            raise DiffException('Invalid src object: %r' % src)
        self.src = src
        if not isinstance(dest, Distfile):
            raise DiffException('Invalid dest object: %r' % dest)
        self.dest = dest

    def validate_distfiles(self):
        def validate(distfile):
            found = False
            for _format in _supported_formats:
                if distfile.endswith(_format):
                    found = True
            if not found:
                raise DiffUnsupported('Invalid distfile type: %s' % distfile)
        validate(self.src.fname)
        validate(self.dest.fname)

    def fetch_distfiles(self):
        # please fetch from distpatch.package to avoid dupes
        self.src.fetch()
        self.dest.fetch()

    def generate(self, output_dir, clean_sources=True, compress=True, force=False):
        # running diffball from a git repository, while a version with xz support
        # isn't released :)
        diffball_bindir = os.environ.get('DIFFBALL_BINDIR', '/usr/bin')
        differ = os.path.join(diffball_bindir, 'differ')

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        distdir = portage.settings['DISTDIR']

        # copy files to output dir and uncompress
        src = os.path.join(output_dir, self.src.fname)
        dest = os.path.join(output_dir, self.dest.fname)
        copy2(os.path.join(distdir, self.src.fname), src)
        copy2(os.path.join(distdir, self.dest.fname), dest)
        usrc = uncompress(src)
        udest = uncompress(dest)

        # building delta filename
        self.diff_file = os.path.join(output_dir,
                                      '%s-%s.%s' % (self.src.fname,
                                                    self.dest.fname,
                                                    self.patch_format))

        diff_indisk = self.diff_file[:]
        if compress:
            diff_indisk += '.xz'
        if os.path.exists(diff_indisk) and not force:
            if clean_sources:
                os.unlink(usrc)
                os.unlink(udest)
            raise DiffExists

        cmd = [differ, usrc, udest, '--patch-format', self.patch_format,
               self.diff_file]

        if call(cmd) != os.EX_OK:
            raise DiffException('Failed to generate diff: %s' % self.diff_file)

        # svalidation of delta
        tmp_dir = tempdir()
        copy2(usrc, tmp_dir)
        copy2(self.diff_file, tmp_dir)
        uchksums = Chksum(self.diff_file)

        # xz it
        if compress:
            if call(['xz', '-f', self.diff_file]) != os.EX_OK:
                raise DiffException('Failed to xz diff: %s' % self.diff_file)
            self.diff_file += '.xz'

        self.dbrecord = DeltaDBRecord(DeltaDBFile(src, usrc),
                                      DeltaDBFile(dest, udest),
                                      DeltaDBFile(self.diff_file,
                                                  chksums=Chksum(
                                                      self.diff_file),
                                                  uchksums=uchksums))

        # reconstruct dest file from src and delta
        try:
            patch = Patch(self.dbrecord)
            patch.reconstruct(output_dir, tmp_dir, False)
        except PatchException, err:
            if clean_sources:
                os.unlink(src)
                os.unlink(dest)
                os.unlink(usrc)
                os.unlink(udest)
                os.unlink(self.diff_file)
            raise DiffException('Delta reconstruction failed: %s' % str(err))

        # remove sources
        rmtree(tmp_dir)
        if clean_sources:
            os.unlink(src)
            os.unlink(dest)
            os.unlink(usrc)
            os.unlink(udest)

    def __repr__(self):
        return '<%s %s -> %s>' % (self.__class__.__name__, self.src.fname,
                                  self.dest.fname)
