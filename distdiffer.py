#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distpatch.deltadb import DeltaDB
from distpatch.diff import DiffException
from distpatch.package import Package

import argparse
import os
import sys

parser = argparse.ArgumentParser(
    description='Creates binary deltas for distfiles of Gentoo Linux packages')

# positional arguments
parser.add_argument('packages', metavar='package-atom', nargs='*',
                    help='Package atoms')

# optional arguments
parser.add_argument('-d', '--db', dest='delta_db', metavar='FILE',
                    required=True, help='File to be used as delta database')
parser.add_argument('-o', '--output', dest='output_dir', metavar='DIR',
                    default=os.getcwd(), help='Output directory (default: ' \
                    'current directory)')
parser.add_argument('-f', '--file', dest='packages_file', metavar='FILE',
                    help='Read package atoms from a line-separated file. ' \
                    'This option will ignore `package-atom` arguments')
parser.add_argument('--stdin', dest='stdin', action='store_true', help='Read ' \
                    'line-separated package atoms from stdin. This option will ' \
                    'ignore `package-atom` arguments and `--file`')
parser.add_argument('-c', '--no-compress', dest='no_compress', action='store_true',
                    help='Disable the compression of generated deltas with xz(1)')
parser.add_argument('-p', '--preserve', dest='preserve', action='store_true',
                    help='Preserve the uncompressed sources in the output directory')
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                    help='Enable verbose mode')

def main():
    args = parser.parse_args()
    db = DeltaDB(args.delta_db)

    # get the list of packages to be processed
    packages = args.packages[:]
    if args.stdin:
        packages = []
        for line in sys.stdin:
            packages.append(line.strip())
    elif args.packages_file is not None:
        if not os.path.isfile(args.packages_file):
            parser.error('invalid file: %s' % args.packages_file)
        packages = []
        with open(args.packages_file) as fp:
            for line in fp:
                packages.append(line.strip())

    if len(packages) == 0:
        parser.print_help()
        return

    if args.verbose:
        print '>>> Starting distdiffer ...\n'

    for package in packages:
        if args.verbose:
            print '>>> Package: %s' %  package
        pkg = Package(db)
        pkg.diff(package)
        if args.verbose:
            print '    >>> Versions:'
            for cpv in pkg.ebuilds:
                print '        %s' % cpv
            print '    >>> Deltas:'
            if len(pkg.diffs) == 0:
                print '        None\n'
            else:
                for diff in pkg.diffs:
                    print '        %s -> %s' % (diff.src_distfile, diff.dest_distfile)
        if len(pkg.diffs) == 0:
            continue
        if args.verbose:
            print '    >>> Fetching distfiles:'
        for diff in pkg.diffs:
            diff.fetch_distfiles()
        if args.verbose:
            print '    >>> Generating deltas:'
        for diff in pkg.diffs:
            if args.verbose:
                sys.stdout.write('        %s -> %s ... ' % (diff.src_distfile,
                                                            diff.dest_distfile))
                sys.stdout.flush()
            try:
                diff.generate(args.output_dir, not args.preserve,
                              not args.no_compress)
            except DiffException, err:
                if args.verbose:
                    print 'failed!'
                    print '            %s' % str(err)
            else:
                if args.verbose:
                    print 'done!'
                    print '            %s' % os.path.basename(diff.diff_file)
                db.add(diff.dbrecord)
        if args.verbose:
            print

if __name__ == '__main__':
    main()
