"""Make white pixels transparent in PNGs inside a folder."""
from PIL import Image
import numpy as np
import os

folder_dir = "icons-transparent"
for image in os.listdir(folder_dir):
    if image.endswith(".jpg") or image.endswith(".png"):
        fn = os.path.join(folder_dir, image)
        print(fn)
        img = Image.open(fn).convert("RGBA")
        imgnp = np.array(img)
        white = np.sum(imgnp[:, :, :3], axis=2)
        white_mask = np.where(white == 255 * 3, 1, 0)
        alpha = np.where(white_mask, 0, imgnp[:, :, -1])
        imgnp[:, :, -1] = alpha
        Image.fromarray(np.uint8(imgnp)).save(fn, "PNG")
