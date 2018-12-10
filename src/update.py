"""
Performs update of some field of the database
"""

import os
import argparse
from server import model

def parse_args():
    parser = argparse.ArgumentParser(
        description="Performs update / clean up of some fields of the database",
        prog="update.py")
    parser.add_argument('--actions', nargs="+", help="\
The actions to perform, in the given order. Available values are:\n\
* `filesize`: Update the value of the entry `fileSize` of each video according\
  to the size (in bytes) of the file stored on hard drive.\
* `clean`: Clean up the database by removing video documents whose actual file\
  has been deleted from hard drive")
    return parser.parse_args()


def genVids():
    c =0
    for vid in model.getService('video').getAll():
        c += 1
        yield vid
    print ("Processed %d videos." % c)

def updateSize(vid):
    try:
        model.getService('video').set(vid['_id'], 'fileSize', os.path.getsize(vid['path']))
    except Exception as e:
        print ("ERROR: file `%s': %s" % (vid['path'], repr(e)))

def cleanUp(vid):
    try:
        with open(vid['path']) as f:
            pass
    except IOError:
        print ("File `%s' doesn't exist. Deleting document." % vid['path'])
        model.getService('video').deleteById(vid['_id'])

def main():
    ns = parse_args()
    for vid in genVids():
        for action in ns.actions:
            if action == 'clean':
                cleanUp(vid)
            if action == 'filesize':
                updateSize(vid)

if __name__ == '__main__':
    main()
