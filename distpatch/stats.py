# -*- coding: utf-8 -*-
"""
    distpatch.stats
    ~~~~~~~~~~~~~~~

    Module to generate plots for basic stats. Unused for now.

    :copyright: (c) 2011 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

from matplotlib import pyplot

from distpatch.deltadb import DeltaDB
from distpatch.helpers import format_size


class Stats(object):

    def __init__(self, deltadb_file):
        self.deltadb = sorted(DeltaDB(deltadb_file), self._cmp)

    def _cmp(self, x, y):
            x_ = int(x.dest.chksums['size'])
            y_ = int(y.dest.chksums['size'])
            if x_ < y_:
                return -1
            elif x_ > y_:
                return 1
            return 0

    def downloaded_size(self):
        rd = {}
        for record in self.deltadb:
            dest = int(record.dest.chksums['size'])
            delta = int(record.delta.chksums['size'])
            ratio = float(delta) / dest
            rd[record.delta.fname] = {
                'dest': format_size(dest),
                'delta': format_size(delta),
                'ratio': ratio,
            }
        return rd

    def average_economy_graph(self):
        ratio = []
        for record in self.deltadb:
            delta = float(record.delta.chksums['size'])
            dest = float(record.dest.chksums['size'])
            ratio.append(100 - ((delta / dest) * 100))
        pyplot.plot(range(1, len(ratio) + 1), sorted(ratio))
        pyplot.axes()
        pyplot.xlabel('Deltas (total: %i)' % len(ratio))
        pyplot.ylabel('Percentage of savings (for compressed files)')
        pyplot.show()

    def downloaded_size_graph(self):
        dest = []
        delta = []
        for record in self.deltadb:
            dest.append(int(record.dest.chksums['size']))
            delta.append(int(record.delta.chksums['size']))
        pyplot.plot(range(len(dest)), dest)
        pyplot.plot(range(len(delta)), delta)
        pyplot.show()
