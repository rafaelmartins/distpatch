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

from itertools import izip, izip_longest
from snakeoil.chksum import get_chksums, get_handler
from snakeoil.fileutils import AtomicWriteFile

import codecs
import os


class DeltaDBException(Exception):
    pass


class DeltaDBFile:
    
    chksum_types = ['md5', 'sha1', 'sha256', 'rmd160', 'size']
    
    def __init__(self, fname, ufname=None, chksums=None):
        self.fname = fname
        self.ufname = ufname
        self.chksums = chksums
        self.compressed = True
        if ufname is not None and \
           (os.path.basename(self.fname) == os.path.basename(self.ufname)):
            self.compressed = False
        if self.chksums is None:
            chksums = get_chksums(self.fname, *self.chksum_types)
            uchksums = []
            if self.compressed and self.ufname is not None:
                uchksums = get_chksums(self.ufname, *self.chksum_types)
            self.chksums = []
            for chksum_type, chksum, uchksum in izip_longest(self.chksum_types,
                                                             chksums, uchksums,
                                                             fillvalue=None):
                if chksum_type != 'size':
                    handler = get_handler(chksum_type)
                    self.chksums.append((chksum_type, handler.long2str(chksum)))
                    if self.compressed and uchksum is not None:
                        self.chksums.append(('u'+ chksum_type,
                                            handler.long2str(uchksum)))
                else:
                    self.chksums.append(('size', chksum))
                    if self.compressed and uchksum is not None:
                        self.chksums.append(('usize', uchksum))
    
    def __eq__(self, other):
        for i in range(len(self.chksum_types)):
            try:
                if self.chksums[i] != other.chksums[i]:
                    return False
                try:
                    if self.compressed and (self.uchksums[i] != other.uchksums[i]):
                        return False
                except AttributeError:
                    pass
            except IndexError:
                pass
        return True
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.fname)


class DeltaDBRecord:
    
    def __init__(self, delta, src, dest):
        self.delta = delta
        self.src = src
        self.dest = dest
    
    def _format_checksum(self, chksum_list):
        rv = []
        for chksum_type, chksum in chksum_list:
            rv.append('%s %s' % (chksum_type.upper(), chksum))
        return ' '.join(rv)
        
    def __str__(self):
        rv = [
            os.path.basename(self.delta.fname),
            os.path.basename(self.src.fname) + '\t' + os.path.basename(self.dest.fname),
            self._format_checksum(self.src.chksums),
            self._format_checksum(self.dest.chksums),
            self._format_checksum(self.delta.chksums),
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
        chksum = []
        for key, value in izip(pieces[::2], pieces[1::2]):
            chksum.append((key.lower(), value.strip()))
        return chksum
    
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
            chksum_src = self._parse_checksum_line(record[2])
            chksum_dest = self._parse_checksum_line(record[3])
            chksum_delta = self._parse_checksum_line(record[4])
            
            # building DeltaDBFile objects
            delta = DeltaDBFile(delta_name, chksums=chksum_delta)
            src = DeltaDBFile(src_name, chksums=chksum_src)
            dest = DeltaDBFile(dest_name, chksums=chksum_dest)
            
            self.append(DeltaDBRecord(delta, src, dest))
    
    def __contains__(self, key):
        for i in self:
            if key == i.delta.fname:
                return True
        return False
        
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
    