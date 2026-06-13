from PIL import Image


# im = Image.open("time-{}.png".format(count))
# im = im.resize((200,200))
im = Image.open("icons/gollum.jpg")
# im.save("/home/pi/bmp/time-{}.bmp".format(count),"BMP")
im.save("icons/gollum.bmp", "BMP")
