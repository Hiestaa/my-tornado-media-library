import sys
import experiments
from experiments import *
# from experiments import facedetect_facelib

# print (dir(experiments.facedetect_facelib))

if __name__ == '__main__':
    if len(sys.argv) > 1:
        for name in sys.argv[1:]:
            getattr(experiments, name).run()
    else:
        print("No experiment specified.")