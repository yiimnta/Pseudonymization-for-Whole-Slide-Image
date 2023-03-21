from PIL import Image
import pylibdmtx.pylibdmtx as pylib
import cv2
import numpy as np
import math


class BarCode(object):
    DEFAULT_SIZE = 100

    @staticmethod
    def create_data_matrix_barcode(data, size):
        encoded = pylib.encode(data.encode('utf8'))
        img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
        w, h = img.size

        # the output matrix code in default always has a border 7 pixel.
        # After removing the code can look better.
        img = img.crop((7, 7, w - 7, h - 7))  # (left, top, right, bottom)

        # (code has in default size 136x136)
        img = np.asarray(img)
        img = BarCode.resize_by_width(img, size)

        return img

    @staticmethod
    def create_pdf417_barcode(data, new_width):
        import pdf417
        codes = pdf417.encode(data, columns=5)

        img = pdf417.render_image(codes)
        img = np.asarray(img)
        img = BarCode.resize_by_width(img, new_width)

        # cv2.imshow("test", img)
        # cv2.waitKey()
        return img

    @staticmethod
    def create_code39_barcode(data, new_width):
        import barcode
        from barcode.writer import ImageWriter

        ITF = barcode.get_barcode_class('code39')
        itf = ITF(data, writer=ImageWriter())
        img = itf.render(writer_options={'write_text': False})
        img = np.asarray(img)
        img = BarCode.resize_by_width(img, new_width)

        # cv2.imshow("test", img)
        # cv2.waitKey()

        return img

    @staticmethod
    def resize_by_width(img, new_width):
        height, width = img.shape[0], img.shape[1]

        if new_width != width:
            ratio = new_width / width
            img = cv2.resize(img, (math.floor(width * ratio), math.floor(height * ratio)),
                             interpolation=cv2.INTER_LANCZOS4)

        return img
