#!.env/bin/python
import cv2

def run():
    print ("OpenCV v%s" % cv2.__version__)

    cap = cv2.VideoCapture('E:\\dev\\perso\\python\\tornado-vice\\data\\videos\\Au dela - ascii.mp4')
    print ("Is opened", cap.isOpened())

