import sys
import random
whoareyou = sys.stdin.readline()
sys.stdout.write("crayfish\n")
sys.stdout.flush( )
number = 0
s = sys.stdin.readline( )
words = s.split( )
SizeX = int(words[0])
SizeY = int(words[1])
nPlayers = int(words[2])
iPlayer = int(words[3])

d = iPlayer == 0
while True:
    try:
        s = sys.stdin.readline( )
        while s != "end\n":
            words = s.split( )
            if words[3] == "W":
                if (d and words[2] == "0") or (not d and words[2] == "1"):
                    direction = random.choice(['E','W','N','S']) 
                    myposx = int(words[0])
                    myposy = int(words[1])
                    sys.stdout.write("move %d %d %s\n" % (myposx, myposy, direction))
            s = sys.stdin.readline( )
        sys.stdout.write("end\n")
        sys.stdout.flush( )
    except:
        break
