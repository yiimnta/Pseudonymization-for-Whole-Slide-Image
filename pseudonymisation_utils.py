import imutils
from enum import IntEnum, Enum
from barcode_utils import BarCode
from PIL import ImageFont, ImageDraw, Image
import pylibdmtx.pylibdmtx as pylib
import cv2
import numpy as np
import math
import compression_utils as cu
from tifffile import TiffPage


class EFieldFont(Enum):
    """
        Font type of text
    """
    HMADURAI = "./font/HindMadurai-Bold.ttf"  # HindMadurai
    SEGOEBL = "./font/seguibl.ttf"  # Segoe Black


class EFieldType(IntEnum):
    """
        Data type of Field in Schema
    """
    TEXT = 0
    MATRIX = 1
    PDF417 = 2
    CODE39 = 3

    @staticmethod
    def barcodes():
        return [EFieldType.PDF417, EFieldType.CODE39, EFieldType.MATRIX]


class EFieldAlign(IntEnum):
    """
        Position of Data in a Field
    """
    LEFT = 0
    RIGHT = 1
    CENTER = 2


class ESchemaStretch(IntEnum):
    """ Flag,
        if the image created by Schema is smaller than the current label image,
        then with FILL, the new image will be resized to the same size as the current image.
    """
    NONE = 0
    FILL = 1


class BarCode(object):
    """
        Barcode class
        gives static-methods to create barcode
    """

    DEFAULT_SIZE = 100

    @staticmethod
    def create_data_matrix_barcode(data, size):
        encoded = pylib.encode(data.encode('utf8'), size="26x26")
        img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
        w, h = img.size

        # removing border
        img = img.crop((7, 7, w - 7, h - 7))  # (left, top, right, bottom)

        # img.save('test.png') 136x136
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


class Field:
    """
        A Field is a Cell of Schema(Table)
        contains the value of a Cell
    """
    def __init__(self, data,
                 col, row,
                 colspan=1,
                 rowspan=1,
                 type=EFieldType.TEXT,
                 align=EFieldAlign.LEFT,
                 padding=(0, 0, 0, 0),
                 font=EFieldFont.HMADURAI,
                 font_size=32,
                 code_size=BarCode.DEFAULT_SIZE):

        self.data = data
        self.col = col
        self.row = row
        self.colspan = colspan
        self.rowspan = rowspan
        self.font = font
        self.type = type
        self.font_size = font_size
        self.align = align
        self.padding = padding
        self.code_size = code_size
        self.barcode = None  # be used to save image data of barcode

        if self.type is EFieldType.MATRIX:
            self.barcode = BarCode.create_data_matrix_barcode(self.data, self.code_size)
        elif self.type is EFieldType.PDF417:
            self.barcode = BarCode.create_pdf417_barcode(self.data, self.code_size)
        elif self.type is EFieldType.CODE39:
            self.barcode = BarCode.create_code39_barcode(self.data, self.code_size)

    def __str__(self):
        return "Field([data={0}, type={1}, col={2}, row={3}," \
               " colspan={4}, rowspan={5} , font={6}, font_size={7}])" \
               "".format(self.data, self.type, self.col, self.row,
                         self.colspan, self.rowspan, self.font, self.font_size)

    def draw(self, image, position):
        """
            Write data on an image
            :param image: numpy array (be read by opencv2.imread)
            :param position (x,y) position on the image
            :return: written image
        """
        if self.type is EFieldType.TEXT:
            image_pil = Image.fromarray(image)
            image_draw = ImageDraw.Draw(image_pil)
            font = ImageFont.truetype(self.font.value, self.font_size)
            image_draw.text(position, self.data, font=font, fill=(0, 0, 0, 0))
            image = np.asarray(image_pil)

        elif self.type in [EFieldType.PDF417, EFieldType.MATRIX, EFieldType.CODE39]:
            if self.barcode is None:
                raise Exception("Barcode is none! Could not create barcode")

            barcode_height, barcode_width = self.barcode.shape[0], self.barcode.shape[1]
            x_offset, y_offset = position
            image[y_offset: y_offset + barcode_height, x_offset: x_offset + barcode_width] = self.barcode

        return image


class Schema:
    """
        Table of content of a label
    """
    def __init__(self, column_number: int, row_number: int, stretch=ESchemaStretch.FILL, border=(0, 0, 0, 0), rotation=0,
                 padding=(0, 0, 0, 0)):
        self.column_number = column_number
        self.row_number = row_number
        self.stretch = stretch
        self.border = border
        self.rotation = rotation
        self.padding = padding
        self.data = []  # list[Field]
        self.colspan_rows = np.zeros((row_number,), dtype=int)
        self.rowspan_rows = np.zeros((row_number,), dtype=int)

    def add_cell(self, field: Field):
        """
            Add a new cell for the table
            :param field:
            :return:
        """
        if field.colspan > 1:
            self.colspan_rows[field.row] = 1
        if field.rowspan > 1:
            self.rowspan_rows[field.row] = 1
        self.data.append(field)


def get_text_dimensions(field):
    """
        Get with and height of the field
        :param field
    """
    font = ImageFont.truetype(field.font.value, field.font_size)
    ascent, descent = font.getmetrics()
    text_width = font.getmask(field.data).getbbox()[2]
    text_height = font.getmask(field.data).getbbox()[3] + descent

    return text_width, text_height


def create_pseudo_label(img_width, img_height, schema: Schema):
    """
        create pseudonym image based on schema data
        :parameter
            img_width:
                width of image
            img_height:
                height of image
            schema:
                table of content
        :return
            image data: numpy array
    """

    """ calculate resolution of image """
    column_min_width = 140
    width_arr = np.zeros((schema.column_number,), dtype=int)    # to save width of each cell
    height_arr = np.zeros((schema.row_number,), dtype=int)      # to save height of each cell
    colspan_arr = []    # to save width of colspan cell
    rowspan_arr = []    # to save height of rowspan cell

    # list of available barcode types
    barcode_list = EFieldType.barcodes()

    # BEGIN: Calculation size of the pseudonym by calculating size of each field
    for field in schema.data:
        pad_top, pad_right, pad_bottom, pad_left = field.padding
        if field.type is EFieldType.TEXT:
            text_size = get_text_dimensions(field)
            text_size_w = text_size[0] + pad_left + pad_right
            text_size_h = text_size[1] + pad_top + pad_bottom

            if schema.colspan_rows[field.row] == 0:
                if width_arr[field.col] < text_size_w:
                    width_arr[field.col] = text_size_w
            else:
                colspan_arr.append((field.col, field.colspan, text_size_w))

            if schema.rowspan_rows[field.row] == 0:
                if height_arr[field.row] < text_size_h:
                    height_arr[field.row] = text_size_h
            else:
                rowspan_arr.append((field.row, field.rowspan, text_size_h))

        if field.type in barcode_list:
            barcode_width = field.barcode.shape[1] + pad_left + pad_right
            barcode_height = field.barcode.shape[0] + pad_top + pad_bottom

            if schema.colspan_rows[field.row] == 0:
                if width_arr[field.col] < barcode_width:
                    width_arr[field.col] = barcode_width
            else:
                colspan_arr.append((field.col, field.colspan, barcode_width))

            if schema.rowspan_rows[field.row] == 0:
                if height_arr[field.row] < barcode_height:
                    height_arr[field.row] = barcode_height
            else:
                rowspan_arr.append((field.row, field.rowspan, barcode_height))

    # calc size of colspan cell
    for colspan_e in colspan_arr:
        cols_width = colspan_e[2]
        w = sum(width_arr[colspan_e[0]: colspan_e[0] + colspan_e[1]])

        if w < cols_width:
            width_gap = math.ceil((cols_width - w) / colspan_e[1])
            width_arr[colspan_e[0]: colspan_e[0] + colspan_e[1]] = width_arr[colspan_e[0]: colspan_e[0] + colspan_e[
                1]] + width_gap

    # calc size of rowspan cell
    for rowspan_e in rowspan_arr:
        rows_height = rowspan_e[2]
        h = sum(height_arr[rowspan_e[0]: rowspan_e[0] + rowspan_e[1]])

        if h < rows_height:
            height_gap = math.ceil((rows_height - h) / rowspan_e[1])
            height_arr[rowspan_e[0]: rowspan_e[0] + rowspan_e[1]] = height_arr[rowspan_e[0]: rowspan_e[0] + rowspan_e[
                1]] + height_gap

    # END: Calculation size of the pseudonym by calculating size of each field

    width_arr[width_arr < column_min_width] = column_min_width

    # width of pseudonym
    pseudo_img_width = np.sum(width_arr)

    # height of pseudonym
    pseudo_img_height = np.sum(height_arr)

    # init pseudonym image
    pseudonym = np.ones((pseudo_img_height, pseudo_img_width, 3), dtype=np.uint8) * 255

    # draw data on pseudonym
    for field in schema.data:

        # offset left
        x_offset_param = 0 if field.col == 0 else np.sum(width_arr[0: field.col])

        # calc offset(x,y) based on align options
        if field.align is not EFieldAlign.LEFT or field.colspan > 1:
            text_size = 0
            if field.type is EFieldType.TEXT:
                text_size = get_text_dimensions(field)[0]
            elif field.type in barcode_list:
                text_size = field.code_size

            if field.colspan > 1:
                field_width = np.sum(width_arr[field.col: field.col + field.colspan])
            else:
                field_width = width_arr[field.col]

            textX = (field_width - text_size)

            if field.align is EFieldAlign.CENTER or field.colspan > 1:
                textX = textX // 2
            elif field.align is EFieldAlign.RIGHT:
                textX = textX

            x_offset_param = x_offset_param + textX

        y_offset_param = 0 if field.row == 0 else np.sum(height_arr[0:field.row])

        # adding padding
        pad_top, pad_right, pad_bottom, pad_left = field.padding
        if field.align is EFieldAlign.LEFT:
            x_offset_param = x_offset_param + pad_left
        elif field.align is EFieldAlign.RIGHT:
            x_offset_param = x_offset_param - pad_right

        y_offset_param = y_offset_param + pad_top

        # draw data on image
        pseudonym = field.draw(pseudonym, (x_offset_param, y_offset_param))

    # add padding to image
    if schema.padding != (0, 0, 0, 0):
        top, right, bottom, left = schema.padding
        new_width = pseudo_img_width + right + left
        new_height = pseudo_img_height + top + bottom
        pseudonym = Image.fromarray(pseudonym)
        padding_img = Image.new(pseudonym.mode, (new_width, new_height), (255, 255, 255))
        padding_img.paste(pseudonym, (left, top))
        pseudonym = np.asarray(padding_img)

    # rotation image
    if schema.rotation != 0:
        pseudonym = imutils.rotate_bound(pseudonym, schema.rotation)
        pseudo_img_height, pseudo_img_width = pseudonym.shape[0], pseudonym.shape[1]

    # cv2.imshow('pseudonym', pseudonym)
    ratio = img_height / pseudo_img_height
    pseudo_img_width, pseudo_img_height = (int(pseudo_img_width * ratio), int(pseudo_img_height * ratio))
    if pseudo_img_width > img_width:
        ratio = img_width / pseudo_img_width
        pseudo_img_width, pseudo_img_height = (int(pseudo_img_width * ratio), int(pseudo_img_height * ratio))

    # resize the pseudonym to the same size as original label
    pseudonym = cv2.resize(pseudonym, [pseudo_img_width, pseudo_img_height], interpolation=cv2.INTER_LANCZOS4)

    # result image
    img = np.ones((img_height, img_width, 3), dtype=np.uint8) * 0

    if schema.stretch is ESchemaStretch.FILL:
        # if the image created by Schema is smaller than the current label image,
        # then with FILL, the new image will be resized to the same size as the current image.
        img[img == 0] = 255
        offset_x = (img_width - pseudo_img_width) // 2
        offset_y = (img_height - pseudo_img_height) // 2
        img[offset_y: (offset_y + pseudo_img_height), offset_x: (offset_x + pseudo_img_width)] = pseudonym
    else:
        img[0: pseudo_img_height, 0:pseudo_img_width] = pseudonym

    # img = cv2.copyMakeBorder(
    #     img,
    #     top=schema.border[0],
    #     bottom=schema.border[2],
    #     left=schema.border[3],
    #     right=schema.border[1],
    #     borderType=cv2.BORDER_CONSTANT,
    #     value=[0, 0, 0]
    # )

    # cv2.imshow('img', img)
    # # user presses a key to out
    # cv2.waitKey(0)
    # # Destroying present windows on screen
    # cv2.destroyAllWindows()
    return img


def replace_label_with_pseudonym_svs(wsi_path, pseudo_label, ifd: TiffPage):
    """ Replace the current label image with another label in an Aperio WSI
        by deleting all the image data of the current label, then adding the new label's image data
        at the end of the file (this helps to avoid memory conflicts in the file, but it makes the file size a
        bit larger compared to the original file).

        Parameters:
            wsi_path:
                path of SLIDE file
            pseudo_label:
                image will be replaced with the current label of the slide
            ifd:
                image file directory of label
    """
    try:
        with open(wsi_path, "r+b") as f:

            # get endian order of bytes
            big_endian = True if f.read(2) == b"MM" else False  # b"II" is litle-endian

            # get compression of current label
            compression = ifd.compression

            # if the compression is still not supported, uses Adobe deflate instead
            if compression not in cu.COMPRESSION.values():
                compression = cu.COMPRESSION.ADOBE_DEFLATE

            # perform compression
            img_data = cu.compression_image(pseudo_label, ifd.rowsperstrip, predictor=ifd.predictor,
                                            compression=compression)

            # Inject the new image to current image data place

            """ wipe data of old img """
            old_img_data_byte_count = sum(ifd.databytecounts)
            old_img_data_first_offset = ifd.dataoffsets[0]
            f.seek(old_img_data_first_offset)
            f.write(b'\x00' * old_img_data_byte_count)

            """ write data of new img """
            # write compression value
            if compression.value != ifd.compression:
                comp = ifd.tags.get(259)
                f.seek(comp.valueoffset)

                # ADOBE_DEFLATE
                f.write(cu.int_to_bytes(compression.value, length=4, is_big_endian=big_endian))

            # write new strip byte count
            new_strip_byte_counts = [strip.count for strip in img_data]
            f.seek(ifd.tags.get(279).valueoffset)
            for strip_count in new_strip_byte_counts:
                f.write(cu.int_to_bytes(strip_count, length=4, is_big_endian=big_endian))

            new_strip_offsets = []      # to save trip offset values

            # write img data
            f.seek(0, 2)  # go to eof to avoid conflict
            for idx, strip_byte in enumerate(img_data):
                new_strip_offsets.append(f.tell())
                f.write(bytes(strip_byte.data))

            # write trip offsets
            f.seek(ifd.tags.get(273).valueoffset)
            for strip_offset in new_strip_offsets:
                f.write(cu.int_to_bytes(strip_offset, length=4, is_big_endian=big_endian))

            f.flush()
            f.close()

    except Exception as e:
        print("Can not replace label with pseudonym:", str(e))
        return False

    return True


def back_up_image_svs(wsi_path, image_data, ifd: TiffPage):
    """ Replace the pseudonym with original label in an Aperio WSI

        Parameters:
            wsi_path:
                path of SLIDE file
            image_data:
                image data is a dict and contains data_byte_counts, data_offsets, compression and image data(bytes)
            ifd:
                image file directory of label
    """
    # validate of image_data
    keys = ["data_byte_counts", "data_offsets", "compression", "data"]
    for key in keys:
        if key not in image_data:
            print(f"{key} not found in image data")
            return False

    try:
        with open(wsi_path, "r+b") as f:

            # get endian order of bytes
            big_endian = True if f.read(2) == b"MM" else False  # b"II" is litle-endian

            # Inject the new image to current image data place

            """ wipe pseudonym data """
            old_img_data_byte_count = sum(ifd.databytecounts)
            old_img_data_first_offset = ifd.dataoffsets[0]
            f.seek(old_img_data_first_offset)
            f.write(b'\x00' * old_img_data_byte_count)

            """ write data of origin img """
            # write compression value
            comp = ifd.tags.get(259)
            f.seek(comp.valueoffset)
            f.write(cu.int_to_bytes(image_data["compression"], length=4, is_big_endian=big_endian))

            # write new strip byte count
            f.seek(ifd.tags.get(279).valueoffset)
            for strip_count in image_data["data_byte_counts"]:
                f.write(cu.int_to_bytes(strip_count, length=4, is_big_endian=big_endian))

            # write trip offsets
            f.seek(ifd.tags.get(273).valueoffset)
            for strip_offset in image_data["data_offsets"]:
                f.write(cu.int_to_bytes(strip_offset, length=4, is_big_endian=big_endian))

            # write img data
            f.seek(image_data["data_offsets"][0])
            f.write(image_data["data"])
            f.flush()

    except Exception as e:
        print("Can not replace label with pseudonym:", str(e))
        return False

    return True

