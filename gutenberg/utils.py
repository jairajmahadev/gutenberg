#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

from __future__ import (unicode_literals, absolute_import,
                        division, print_function)
import os
import re
import hashlib
import subprocess
from contextlib import contextmanager
import zipfile

import six
import chardet
from path import Path as path

from gutenberg.iso639 import language_name
from gutenberg.database import Book, BookFormat, Format


FORMAT_MATRIX = {
    'epub': 'application/epub+zip',
    'pdf': 'application/pdf',
    'html': 'text/html'
}

BAD_BOOKS_FORMATS = {
    39765: ['pdf'],
    40194: ['pdf'],
}


NB_MAIN_LANGS = 5


@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(newdir)
    try:
        yield
    finally:
        os.chdir(prevdir)


def exec_cmd(cmd):
    if isinstance(cmd, (tuple, list)):
        args = cmd
    else:
        args = cmd.split(' ')
    print("** {}".format(" ".join(args)))
    if six.PY3:
        return subprocess.run(args).returncode
    else:
        return subprocess.call(args)


def download_file(url, fname):
    cmd = ['curl', '--fail', '--insecure', '--location', '--silent',
           '--show-error', '-C', '-', '--url', url]
    if fname:
        cmd += ['--output', fname]
    else:
        cmd += ['--remote-name']
    cmdr = exec_cmd(cmd)
    return cmdr == 0


def main_formats_for(book):
    fmts = [fmt.format.mime
            for fmt in BookFormat.select(BookFormat, Book, Format)
                                 .join(Book).switch(BookFormat)
                                 .join(Format)
                                 .where(Book.id == book.id)]
    return [k for k, v in FORMAT_MATRIX.items() if v in fmts]


def get_list_of_filtered_books(languages, formats, only_books=[]):
    if len(formats):
        qs = Book.select().join(BookFormat) \
                 .join(Format) \
                 .where(Format.mime << [FORMAT_MATRIX.get(f)
                                        for f in formats]) \
                 .group_by(Book.id)
    else:
        qs = Book.select()

    if len(only_books):
        print(only_books)
        qs = qs.where(Book.id << only_books)

    if len(languages):
        qs = qs.where(Book.language << languages)

    return qs


def get_langs_with_count(books):
    lang_count = {}
    for book in books:
        if book.language not in lang_count:
            lang_count[book.language] = 0
        lang_count[book.language] += 1

    return [(language_name(l), l, nb)
            for l, nb in sorted(lang_count.items(),
                                key=lambda x: x[1],
                                reverse=True)]


def get_lang_groups(books):
    langs_wt_count = get_langs_with_count(books)
    if len(langs_wt_count) <= NB_MAIN_LANGS:
        return langs_wt_count, []
    else:
        return (langs_wt_count[:NB_MAIN_LANGS],
                sorted(langs_wt_count[NB_MAIN_LANGS:], key=lambda x: x[0]))


def md5sum(fpath):
    return hashlib.md5(read_file(fpath).encode('utf-8')).hexdigest()


def is_bad_cover(fpath):
    bad_sizes = [19263]
    bad_sums = ['a059007e7a2e86f2bf92e4070b3e5c73']

    if path(fpath).size not in bad_sizes:
        return False

    return md5sum(fpath) in bad_sums


def path_for_cmd(p):
    return re.sub(r'([\'\"\ ])', lambda m: r'\{}'.format(m.group()), p)


def read_file_as(fpath, encoding='utf-8'):
    # logger.debug("opening `{}` as `{}`".format(fpath, encoding))
    if six.PY2:
        with open(fpath, 'r') as f:
            return f.read().decode(encoding)
    else:
        with open(fpath, 'r', encoding=encoding) as f:
            return f.read()


def guess_file_encoding(fpath):
    with open(fpath, 'rb') as f:
        return chardet.detect(f.read()).get('encoding')


def read_file(fpath):
    for encoding in ['utf-8', 'iso-8859-1']:
        try:
            return read_file_as(fpath, encoding), encoding
        except UnicodeDecodeError:
            continue

    # common encoding failed. try with chardet
    encoding = guess_file_encoding(fpath)
    return read_file_as(fpath, encoding), encoding


def zip_epub(epub_fpath, root_folder, fpaths):
    # with cd(tmpd):
        # exec_cmd(['zip', '-q0X', dst, 'mimetype'])
        # exec_cmd(['zip', '-qXr9D', dst] + [czf for czf in zipped_files
        #                                    if not f == 'mimetype'])
    with zipfile.ZipFile(epub_fpath, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fpath in fpaths:
            zf.write(os.path.join(root_folder, fpath), fpath)
