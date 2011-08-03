# -*- coding: utf-8 -*-
"""
    distpatch.chksums
    ~~~~~~~~~~~~~~~~~

    Module to deal with file checksums.

    :copyright: (c) 2011 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

import os

from snakeoil.chksum import get_chksums, get_handler


class ChksumException(Exception):
    pass


class ChksumValue(object):

    def __init__(self, algorithm, value):
        self.algorithm = algorithm
        self.value = value
        self._handler = get_handler(algorithm)

    def to_str(self):
        if isinstance(self.value, basestring):
            return self.value
        elif isinstance(self.value, long):
            return self._handler.long2str(self.value)
        raise ChksumException('Invalid value: %s' % self.value)

    def to_long(self):
        if isinstance(self.value, long):
            return self.value
        elif isinstance(self.value, basestring):
            return self._handler.str2long(self.value)
        raise ChksumException('Invalid value: %s' % self.value)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise ChksumException('Invalid operand for %s: %r' % \
                              (self.__class__.__name__, other))
        return self.to_long() == other.to_long()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return '<%s %s:%s>' % (self.__class__.__name__, self.algorithm,
                               self.to_str())


class Chksum(object):

    algorithms = frozenset(['md5', 'sha1', 'sha256', 'rmd160', 'size'])

    def __init__(self, fname=None, **chksums):

        # if provided fname, calculate checksums from the given file.
        if fname is not None:

            if not os.path.exists(fname):
                raise ChksumException('File not found: %s' % fname)

            values = get_chksums(fname, *self.algorithms)
            chksums = zip(self.algorithms, values)

        # if provided checksums, use them
        else:
            chksums = chksums.items()

        # validate checksums, and set attributes
        tmp_algorithms = list(self.algorithms)
        for algorithm, chksum in chksums:
            if algorithm not in tmp_algorithms:
                raise ChksumException('Invalid checksum algorithm: %s' % \
                                      algorithm)
            setattr(self, algorithm, ChksumValue(algorithm, chksum))
            tmp_algorithms.remove(algorithm)
        if len(tmp_algorithms) > 0:
            raise ChksumException('Missing checksums: %s' % \
                              ', '.join(tmp_algorithms))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise ChksumException('Invalid operand for %s: %r' % \
                              (self.__class__.__name__, other))
        for algorithm in self.algorithms:
            a = getattr(self, algorithm)
            b = getattr(other, algorithm)
            if a != b:
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)
