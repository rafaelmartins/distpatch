# -*- coding: utf-8 -*-

'''
    distpatch.deltadb
    ~~~~~~~~~~~~~~~~~

    The DeltaDB is a file with records for binary deltas.

    Simple example::

        gunicorn-0.12.0.tar.gz-gunicorn-0.12.1.tar.gz.switching.xz
        gunicorn-0.12.0.tar.gz	gunicorn-0.12.1.tar.gz
        MD5 8f8dd16676a911ce00e738fc42ea02f3 UMD5 3cf47af966464279203cc574789d67a0
        MD5 6540ec02de8e00b6b60c28a26a019662 UMD5 4d36382319de6a870cbc7c949b3eb364
        MD5 106ee745b0931ea53aacf7ea1ac043ff UMD5 a87501c0b1012deb4990b54b63b80d7b

'''

from collections import OrderedDict
from itertools import izip
from snakeoil.chksum import get_chksums, get_handler
from snakeoil.fileutils import AtomicWriteFile

import codecs
import os


class DeltaDBException(Exception):
    pass


class DeltaDBFile:

    chksum_types = ['md5', 'sha1', 'sha256', 'rmd160', 'size']

    def __init__(self, fname, chksums=None):
        self.fname = fname
        self.chksums = chksums
        if self.chksums is None:
            chksums = get_chksums(self.fname, *self.chksum_types)
            self.chksums = OrderedDict()
            for chksum_type, chksum in zip(self.chksum_types, chksums):
                self.chksums[chksum_type] = chksum

    def __eq__(self, other):
        for checksum_type in self.chksum_types:
            try:
                if self.chksums[checksum_type] != other.chksums[checksum_type]:
                    return False
            except KeyError:
                pass
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.fname)


class DeltaDBRecord:

    def __init__(self, src, usrc, dest, udest, delta, udelta):
        self.src = src
        self.usrc = usrc
        self.dest = dest
        self.udest = udest
        self.delta = delta
        self.udelta = udelta

    def _format_checksum(self, chksum_dict, uchksum_dict):
        rv = []
        for chksum_type in chksum_dict:
            handler = get_handler(chksum_type)
            rv.append('%s %s U%s %s' % (chksum_type.upper(),
                                        handler.long2str(chksum_dict[chksum_type]),
                                        chksum_type.upper(),
                                        handler.long2str(uchksum_dict[chksum_type])))
        return ' '.join(rv)

    def __str__(self):
        rv = [
            os.path.basename(self.delta.fname),
            os.path.basename(self.src.fname) + '\t' + os.path.basename(self.dest.fname),
            self._format_checksum(self.src.chksums, self.usrc.chksums),
            self._format_checksum(self.dest.chksums, self.udest.chksums),
            self._format_checksum(self.delta.chksums, self.udelta.chksums),
        ]
        return os.linesep.join(rv)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.delta.fname)


class DeltaDB(list):

    def __init__(self, filename):
        self.filename = filename
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

        if not os.path.exists(self.filename):
            return

        # doing this without memory usage in mind, should fix
        records = []
        with codecs.open(self.filename, encoding='utf-8') as fp:
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

            self.append(DeltaDBRecord(DeltaDBFile(src_name, chksum_src),
                                      DeltaDBFile(None, uchksum_src),
                                      DeltaDBFile(dest_name, chksum_dest),
                                      DeltaDBFile(None, uchksum_dest),
                                      DeltaDBFile(delta_name, chksum_delta),
                                      DeltaDBFile(None, uchksum_delta)))

    def __contains__(self, key):
        for dbfile in self:
            if key == dbfile.delta.fname:
                return True
        return False

    def get(self, delta):
        for dbfile in self:
            if dbfile.delta.fname == delta:
                return dbfile

    def get_by_dest(self, dest):
        rv = []
        for dbfile in self:
            if dbfile.dest.fname == dest:
                rv.append(dbfile)
        return rv
    
    def add(self, record):
        taken = []
        for i in range(len(self)):
            if os.path.basename(record.delta.fname) == self[i].delta.fname:
                taken.append(i)
        for i in taken:
            del self[i]
        self.append(record)
        fp = AtomicWriteFile(self.filename)
        fp.write('\n--\n'.join([str(i) for i in self]))
        fp.close()
