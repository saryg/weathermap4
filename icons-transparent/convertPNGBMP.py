from PIL import Image

count = 1
while(count <13):

    im = Image.open("time-{}.png".format(count))
    im = im.resize((200,200))
    im.save("/home/pi/bmp/time-{}.bmp".format(count),"BMP")
    count = count+1

