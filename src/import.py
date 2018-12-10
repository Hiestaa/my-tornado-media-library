#!/usr/bin/python
import MySQLdb
from server import model

def sqlId2objId(_id):
    _id = str(int(_id))
    _id = '0' * (24 - len(_id)) + _id
    return _id;

def getAutoTag(tagname, tagval):
    if tagname == 'studio':
        if tagval == '18 only girls':
            return r"18.?only.?girls"
        elif tagval == "babes.com":
           return r"babes"
        elif tagval == 'digital desire':
            return r'digital.?desire|[/\\]dd|[/\\]d_20'
        elif tagval == 'sex art':
            return r'sex.?art|[/\\]sa'
        elif tagval == 'Watch 4 Beauty':
            return r'w4b'
        elif tagval == 'wow girls':
            return r'wow.?girls|[/\\]wg'
        elif tagval == 'x-art':
            return r'[/\\]x.?art|[/\\]xa|[\//]x_20'
    elif tagname == 'girl name':
            return '.?'.join(tagval.split(' '))
    return ''

db = MySQLdb.connect(host="localhost", # your host, usually localhost
                     user="root", # your username
                      passwd="root", # your password
                      db="vicedb") # name of the data base

# you must create a Cursor object. It will let
#  you execute all the queries you need
cur = db.cursor()

# import labels
cur.execute("SELECT * FROM labels")
model.getService('tag').deleteAll()
for row in cur.fetchall() :
    _id = sqlId2objId(row[0])
    print ("Adding tag: [%s] %s - %s" % (_id, str(row[1]), str(row[2])))
    model.getService('tag').insert(row[1], row[2], _id=_id, relation=row[3], autotag=getAutoTag(row[1], row[2]))

import time
import os
import cv2
def toTimeStamp(string):
    if string is None:
        return 0
    string = str(string)
    t = time.strptime(string, "%Y-%m-%d %H:%M:%S")
    return time.mktime(t)

def getNbSnapshots(path):
    ssfold = '.'.join(path.split('.')[:-1])
    try:
        return len([
            name for name in os.listdir(ssfold)
            if os.path.isfile(os.path.join(ssfold, name))])
    except:
        return 0;

def analyze(vid):
    cap = cv2.VideoCapture(vid)
    if not cap.isOpened():
        print(">>>>>>>>> Vid %s could not be opened" % vid)
        return 600, (1920, 1080), 30
    length = float(int(cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)))
    w = int(cap.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.cv.CV_CAP_PROP_FPS))
    if length == 0 or w == 0 or h == 0 or fps == 0:
        print(">>>>>>>>> VId %s could not be opened" % vid)
        return 600, (1920, 1080), 30
    return length / fps, (w, h), fps

cur.execute("SELECT * FROM vids")
colid = 0
name = 1
path = 3
added = 5
watched = 6  # format: YYYY-MM-DD HH:MM:DD, may be none if never watched
liked = 7  # number of times
seen = 9  # last time seen
disp_first_frame = 11
model.getService('video').deleteAll()
for row in cur.fetchall():
    _id = sqlId2objId(row[colid])
    print ("Adding video: [%s] %s - path: %s, added: %s, watched: %s, liked: %s, seen: %s, disp_first_frame: %s" \
            % (_id, row[name], row[path], row[added], row[watched], row[liked], row[seen], row[disp_first_frame]))
    duration, resolution, fps = analyze(row[path].replace('/', '\\'))
    model.getService('video').insert(
        filename=row[name], path=row[path].replace('/', '\\'),
        seen=row[liked], duration=duration,
        resolution=resolution, fps=fps,
        creation=toTimeStamp(row[added]),
        lastDisplay=toTimeStamp(row[seen]),
        lastSeen=toTimeStamp(row[watched]),
        thumbnail=0 if row[disp_first_frame] else None,
        nbSnapshots=getNbSnapshots(row[path]),
        _id=_id)

from bson.objectid import ObjectId
cur.execute("SELECT * FROM vids_labels")
c = 0
for row in cur.fetchall():
    label_id = sqlId2objId(row[2])
    vid_id = sqlId2objId(row[1])
    vid = model.getService('video').getById(vid_id)
    tag = model.getService('tag').getById(label_id)
    if tag is None:
        print ("tag %s does not exist!" % label_id)
        continue
    if vid is None:
        print ("vid %s does not exist!" % vid_id)
        continue
    print ("Adding tag: %s - %s to video: %s" % (tag['name'], tag['value'], vid['name']))
    model.getService('video').addTag(vid_id, label_id)
    c += 1

print ("Imported %d tags" % c)