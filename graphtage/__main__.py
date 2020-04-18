import argparse
import json
import logging
import os
import sys
import tempfile as tf

from . import graphtage
from . import version
from .printer import DEFAULT_PRINTER, Printer


class Tempfile:
    def __init__(self, contents, prefix=None, suffix=None):
        self._temp = None
        self._data = contents
        self._prefix = prefix
        self._suffix = suffix

    def __enter__(self):
        self._temp = tf.NamedTemporaryFile(prefix=self._prefix, suffix=self._suffix, delete=False)
        self._temp.write(self._data)
        self._temp.flush()
        self._temp.close()
        return self._temp.name

    def __exit__(self, type, value, traceback):
        if self._temp is not None:
            os.unlink(self._temp.name)
            self._temp = None


class PathOrStdin:
    def __init__(self, path):
        self._path = path
        if self._path == '-':
            self._tempfile = Tempfile(sys.stdin.buffer.read())
        else:
            self._tempfile = None

    def __enter__(self):
        if self._tempfile is None:
            return self._path
        else:
            return self._tempfile.__enter__()

    def __exit__(self, *args, **kwargs):
        if self._tempfile is not None:
            return self._tempfile.__exit__(*args, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description='A diff utility for tree-like files such as JSON and XML.')
    parser.add_argument('FROM_PATH', type=str, nargs='?', default='-',
                        help='The source file to diff; pass \'-\' to read from STDIN')
    parser.add_argument('TO_PATH', type=str, nargs='?', default='-',
                        help='The file to diff against; pass \'-\' to read from STDIN')
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument(
        '--color', '-c',
        action='store_true',
        default=None,
        help='Force the ANSI color output; this is turned on by default only if run from a TTY'
    )
    color_group.add_argument(
        '--no-color',
        action='store_true',
        default=None,
        help='Do not use ANSI color in the output'
    )
    parser.add_argument('--join-lists', '-jl', action='store_true',
                            help='Do not print a newline after each list entry')
    parser.add_argument('--join-dict-items', '-jd', action='store_true',
                        help='Do not print a newline after each key/value pair in a dictionary')
    parser.add_argument('--condensed', '-j', action='store_true', help='Equivalent to `-jl -jd`')
    parser.add_argument(
        '--no-key-edits',
        '-k',
        action='store_true',
        help='Only match dictionary entries if they share the same key. This drastically reduces computation.'
    )
    parser.add_argument(
        '--no-status',
        action='store_true',
        help='Do not display progress bars and status messages'
    )
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument('--log-level', type=str, default='INFO', choices=list(
        logging.getLevelName(x)
        for x in range(1, 101)
        if not logging.getLevelName(x).startswith('Level')
    ), help='Sets the log level for Graphtage (default=INFO)')
    log_group.add_argument('--debug', action='store_true', help='Equivalent to `--log-level=DEBUG`')
    log_group.add_argument('--quiet', action='store_true', help='Equivalent to `--log-level=CRITICAL --no-status`')
    parser.add_argument('--version', '-v', action='store_true', help='Print Graphtage\'s version information to STDERR')
    parser.add_argument('-dumpversion', action='store_true',
                        help='Print Graphtage\'s raw version information to STDOUT and exit')

    if argv is None:
        argv = sys.argv

    args = parser.parse_args(argv[1:])

    if args.debug:
        numeric_log_level = logging.DEBUG
    elif args.quiet:
        numeric_log_level = logging.CRITICAL
    else:
        numeric_log_level = getattr(logging, args.log_level.upper(), None)
        if not isinstance(numeric_log_level, int):
            sys.stderr.write(f'Invalid log level: {args.log_level}')
            exit(1)

    if args.dumpversion:
        print(' '.join(map(str, version.__version__)))
        exit(0)

    if args.version:
        sys.stderr.write(f"Graphtage version {version.VERSION_STRING}\n")
        if args.FROM_PATH == '-' and args.TO_PATH == '-':
            exit(0)

    if args.no_color:
        ansi_color = False
    elif args.color:
        ansi_color = True
    else:
        ansi_color = None

    DEFAULT_PRINTER.out_stream = sys.stdout
    DEFAULT_PRINTER.ansi_color = ansi_color
    DEFAULT_PRINTER.quiet = args.no_status or args.quiet
    printer = Printer(
        sys.stdout,
        ansi_color=ansi_color,
        quiet=args.no_status or args.quiet,
        options={
            'join_lists': args.condensed or args.join_lists,
            'join_dict_items': args.condensed or args.join_dict_items
        }
    )

    logging.basicConfig(level=numeric_log_level, stream=printer)

    logging.getLogger(__name__).info("foo")

    with PathOrStdin(args.FROM_PATH) as from_path:
        with open(from_path, 'rb') as from_file:
            from_json = json.load(from_file)
            with PathOrStdin(args.TO_PATH) as to_path:
                with open(to_path, 'rb') as to_file:
                    to_json = json.load(to_file)
                    graphtage.build_tree(from_json, allow_key_edits=not args.no_key_edits).diff(
                        graphtage.build_tree(to_json, allow_key_edits=not args.no_key_edits)
                    ).print(printer)
    printer.flush()


if __name__ == '__main__':
    main()
