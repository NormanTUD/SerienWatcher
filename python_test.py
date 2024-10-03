#!/usr/bin/python3

import vlc
import argparse
import os
import sys

def error(message, exit_code=1):
    print(f"Error: {message}")
    sys.exit(exit_code)

def main():
    parser = argparse.ArgumentParser(description='Process some options.')

    parser.add_argument('--debug', action='store_true', default=False, help='Enable debug mode.')
    parser.add_argument('--debuglevel', type=int, default=None, help='Set debug level.')
    parser.add_argument('--noplay', action='store_true', default=False, help='Disable play mode.')
    parser.add_argument('--maindir', type=str, required=True, help='Set main directory.')
    parser.add_argument('--serie', type=str, default=None, help='Set serie.')
    parser.add_argument('--zufall', action='store_true', default=False, help='Enable random mode.')
    parser.add_argument('--staffel', type=int, default=None, help='Set staffel.')
    parser.add_argument('--min_staffel', type=int, default=None, help='Set minimum staffel.')
    parser.add_argument('--max_staffel', type=int, default=None, help='Set maximum staffel.')
    parser.add_argument('--min_percentage_runtime_to_count', type=float, default=None, help='Set minimum percentage runtime to count.')

    args = parser.parse_args()

    # Check if the maindir exists
    if not os.path.isdir(args.maindir):
        error(f"--maindir {args.maindir} not found")

    # Create the options dictionary with defaults from argparse
    options = vars(args)

    # Set the dbfile path based on maindir
    options['dbfile'] = os.path.join(options['maindir'], ".db.txt")

    # You can now use the 'options' dictionary as needed in the rest of your program.
    print(options)

if __name__ == '__main__':
    main()

