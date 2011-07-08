# -*- coding: utf-8 -*-

import atexit
import os
import portage

from shutil import copy2, rmtree
from subprocess import call
from tempfile import mkdtemp

from distpatch.deltadb import DeltaDBFile, DeltaDBRecord
from distpatch.helpers import uncompressed_filename_and_compressor
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


def remove_tmpdir(tmpdir):
    if os.path.isdir(tmpdir):
        rmtree(tmpdir)


class Diff:

    patch_format = 'switching'

    def __init__(self, src_distfile, src_ebuild, dest_distfile, dest_ebuild):
        self.src_distfile = src_distfile
        self.src_ebuild = src_ebuild
        self.dest_distfile = dest_distfile
        self.dest_ebuild = dest_ebuild

    def _validate_distfile(self, distfile):
        found = False
        for _format in _supported_formats:
            if distfile.endswith(_format):
                found = True
        if not found:
            raise DiffUnsupported('Invalid distfile type: %s' % distfile)

    def validate_distfiles(self):
        self._validate_distfile(self.src_distfile)
        self._validate_distfile(self.dest_distfile)

    def fetch_distfiles(self):
        # TODO: fetch from distpatch.package, avoinding dupes
        self.src_ebuild.fetch(self.src_distfile)
        self.dest_ebuild.fetch(self.dest_distfile)

    def _copy_and_unpack(self, myfile, output_dir):
        distdir = portage.settings['DISTDIR']
        dest = os.path.join(distdir, myfile)
        copy2(dest, output_dir)
        tarball = os.path.join(output_dir, myfile)
        udest, program = uncompressed_filename_and_compressor(tarball)
        if program is not None and call([program, '-fd', tarball]) != os.EX_OK:
            raise DiffException('Failed to unpack file: %s' % tarball)
        return udest, dest

    def generate(self, output_dir, clean_sources=True, compress=True, force=False):
        # running diffball from a git repository, while a version with xz support
        # isn't released :)
        diffball_bindir = os.environ.get('DIFFBALL_BINDIR', '/usr/bin')
        differ = os.path.join(diffball_bindir, 'differ')

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # getting uncompressed/compressed paths for distfiles
        usrc, src = self._copy_and_unpack(self.src_distfile, output_dir)
        udest, dest = self._copy_and_unpack(self.dest_distfile, output_dir)

        # building delta filename
        self.diff_file = os.path.join(output_dir,
                                      '%s-%s.%s' % (self.src_distfile,
                                                    self.dest_distfile,
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

        # starting the validation of delta

        # temporary dir
        tmpdir = mkdtemp()
        atexit.register(remove_tmpdir, tmpdir)

        # copy files to temporary dir
        copy2(usrc, tmpdir)
        copy2(self.diff_file, tmpdir)

        # get delta info before compress
        udelta_db = DeltaDBFile(self.diff_file)

        # xz it
        if compress:
            if call(['xz', '-f', self.diff_file]) != os.EX_OK:
                raise DiffException('Failed to xz diff: %s' % self.diff_file)
            self.diff_file += '.xz'

        self.dbrecord = DeltaDBRecord(DeltaDBFile(src),
                                      DeltaDBFile(usrc),
                                      DeltaDBFile(dest),
                                      DeltaDBFile(udest),
                                      DeltaDBFile(self.diff_file),
                                      udelta_db)

        # reconstruct dest file from src and delta
        try:
            patch = Patch(self.dbrecord)
            patch.reconstruct(output_dir, tmpdir, False)
        except PatchException, err:
            if clean_sources:
                os.unlink(usrc)
                os.unlink(udest)
                os.unlink(self.diff_file)
            raise DiffException('Delta reconstruction failed: %s' % str(err))

        # remove sources
        rmtree(tmpdir)
        if clean_sources:
            os.unlink(usrc)
            os.unlink(udest)

    def __repr__(self):
        return '<%s %s -> %s>' % (self.__class__.__name__, self.src_distfile,
                                  self.dest_distfile)
