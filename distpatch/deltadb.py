# -*- coding: utf-8 -*-
"""
    distpatch.deltadb
    ~~~~~~~~~~~~~~~~~

    The DeltaDB is a file with records for binary deltas.


    Specifications
    --------------

    - Each delta a record in the database.
    - Each database record have information about the delta, the source file and
      the destination file, compressed and uncompressed.
    - Each checksum line have text-formated checksums for the file, in the
      format: algorithm name (uppercase) + SPACE + checksum. For checksums of
      uncompressed sources, prepend an uppercase 'U' to the algorithm name.
    - All the filenames are stored with compressor names, without file paths.
    - Records are separated by a line with '--'.
    - 1st line is the delta file name.
    - 2nd line is the source file name + TAB + destination file name.
    - 3rd line is the text-formated checksums for the source file.
    - 4th line is the text-formated checksums for the destination file.
    - 5th line is the text-formated checksums for the delta file.

    Simple example (Most of the checksums were ommited)::

        gunicorn-0.12.0.tar.gz-gunicorn-0.12.1.tar.gz.switching.xz
        gunicorn-0.12.0.tar.gz	gunicorn-0.12.1.tar.gz
        MD5 8f8dd16676a911ce00e738fc42ea02f3 UMD5 3cf47af966464279203cc574789d67a0
        MD5 6540ec02de8e00b6b60c28a26a019662 UMD5 4d36382319de6a870cbc7c949b3eb364
        MD5 106ee745b0931ea53aacf7ea1ac043ff UMD5 a87501c0b1012deb4990b54b63b80d7b

    :copyright: (c) 2011 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

import codecs
import os

from itertools import izip
from snakeoil.chksum import get_handler
from snakeoil.fileutils import AtomicWriteFile
from snakeoil.mappings import OrderedDict

from distpatch.chksums import Chksum
from distpatch.helpers import uncompress, uncompressed_filename_and_compressor


class DeltaDBException(Exception):
    pass


class UncompressedOk(Exception):
    pass


class DeltaDBFile:

    def __init__(self, fname, ufname=None, chksums=None, uchksums=None):

        # just calculate checksums if they weren't provided manually
        if chksums is None and uchksums is None:
            self.chksums = Chksum(fname)

            # calculate decompressed checksums
            remove_uncompressed = False
            if ufname is None:
                ufname = uncompress(fname)
                remove_uncompressed = True
            self.uchksums = Chksum(ufname)
            if remove_uncompressed:
                os.unlink(ufname)

        # manual
        elif chksums is not None and uchksums is not None:
            if isinstance(chksums, Chksum):
                self.chksums = chksums
            else:
                self.chksums = Chksum(**chksums)
            if isinstance(uchksums, Chksum):
                self.uchksums = uchksums
            else:
                self.uchksums = Chksum(**uchksums)

        else:
            raise DeltaDBException('You need to provide both dictionaries ' \
                                   'or none of them: chksums and uchksums.')

        # we just want the basename stored
        self.fname = os.path.basename(fname)
        if ufname is None:
            ufname = uncompressed_filename_and_compressor(fname)[0]
        self.ufname = os.path.basename(ufname)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise DeltaDBException('Invalid operand for %s: %r' % \
                                   (self.__class__.__name__, other))
        if self.uchksums != other.uchksums:
            return False
        if self.chksums != other.chksums:
            raise UncompressedOk
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "<%s %s -> %s>" % (self.__class__.__name__, self.fname,
                                  self.ufname)


class DeltaDBRecord:

    def __init__(self, src, dest, delta):
        if not isinstance(src, DeltaDBFile):
            raise DeltaDBException('Invalid source object: %r' % src)
        self.src = src
        if not isinstance(dest, DeltaDBFile):
            raise DeltaDBException('Invalid destination object: %r' % dest)
        self.dest = dest
        if not isinstance(delta, DeltaDBFile):
            raise DeltaDBException('Invalid delta object: %r' % delta)
        self.delta = delta

    def _format_checksum(self, obj):
        rv = []
        for algorithm in Chksum.algorithms:
            value = getattr(obj.chksums, algorithm)
            if value is None:
                raise DeltaDBException('Invalid checksum for %s' % algorithm)
            uvalue = getattr(obj.uchksums, algorithm)
            if uvalue is None:
                raise DeltaDBException('Invalid uncompressed checksum for %s' \
                                       % algorithm)
            rv.append('%s %s U%s %s' % (algorithm.upper(), value.to_str(),
                                        algorithm.upper(), uvalue.to_str()))
        return ' '.join(rv)

    def __str__(self):
        rv = [
            os.path.basename(self.delta.fname),
            os.path.basename(self.src.fname) + '\t' + os.path.basename(
                self.dest.fname),
            self._format_checksum(self.src),
            self._format_checksum(self.dest),
            self._format_checksum(self.delta),
        ]
        return os.linesep.join(rv)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.delta.fname)


class DeltaDB(list):

    def __init__(self, fname):
        self.fname = fname
        list.__init__(self)
        self._parse_db()

    def _parse_checksum_line(self, line):
        pieces = line.split()
        chksums = OrderedDict()
        uchksums = OrderedDict()
        for key, value in izip(pieces[::2], pieces[1::2]):
            key = key.lower()[:]
            mykey = key[0] == 'u' and key[1:] or key
            myvalue = get_handler(mykey).str2long(value.strip())
            if key[0] == 'u':
                uchksums[mykey] = myvalue
            else:
                chksums[mykey] = myvalue
        return chksums, uchksums

    def _parse_db(self):

        if not os.path.exists(self.fname):
            return

        # doing this without memory usage in mind, should fix
        records = []
        with codecs.open(self.fname, encoding='utf-8') as fp:
            records = [i.strip() for i in fp.read().split('--')]

        for record in records:
            record = record.split(os.linesep)

            # first line is just the diff filename
            delta_name = record[0]

            # second line is the src filename and the dest filename, separed by tab
            src_name, dest_name = tuple(record[1].split('\t'))

            # lines 3,4 and 5 are checksums
            chksum_src, uchksum_src = self._parse_checksum_line(record[2])
            chksum_dest, uchksum_dest = self._parse_checksum_line(record[3])
            chksum_delta, uchksum_delta = self._parse_checksum_line(record[4])

            self.append(DeltaDBRecord(DeltaDBFile(src_name,
                                                  chksums=chksum_src,
                                                  uchksums=uchksum_src),
                                      DeltaDBFile(dest_name,
                                                  chksums=chksum_dest,
                                                  uchksums=uchksum_dest),
                                      DeltaDBFile(delta_name,
                                                  chksums=chksum_delta,
                                                  uchksums=uchksum_delta)))

    def __contains__(self, key):
        for dbrecord in self:
            if key == dbrecord.delta.fname:
                return True
        return False

    def get(self, delta):
        for dbrecord in self:
            if dbrecord.delta.fname == delta:
                return dbrecord

    def get_by_dest(self, dest):
        rv = []
        for dbrecord in self:
            if dbrecord.dest.fname == dest:
                rv.append(dbrecord)
        return rv

    def add(self, record):
        taken = []
        for i in range(len(self)):
            if os.path.basename(record.delta.fname) == self[i].delta.fname:
                taken.append(i)
        for i in taken:
            del self[i]
        self.append(record)
        fp = AtomicWriteFile(self.fname)
        fp.write('\n--\n'.join(map(str, self)))
        fp.close()
