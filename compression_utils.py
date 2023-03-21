import numpy as np
import zlib
from tifffile import PREDICTOR
import imagecodecs
from enum import IntEnum


class COMPRESSION(IntEnum):
    """
        Values of Compression tag.
    """
    NONE = 1
    LZW = 5
    # OJPEG = 6  # old-style JPEG
    # JPEG = 7
    ADOBE_DEFLATE = 8

    # the other compressions below will come soon!!
    # CCITT_T4 = 3
    # CCITT_T6 = 4
    # NEXT = 32766
    # CCITTRLEW = 32771
    # PACKBITS = 32773
    # THUNDERSCAN = 32809
    # IT8CTPAD = 32895
    # IT8LW = 32896
    # IT8MP = 32897
    # IT8BL = 32898
    # PIXARFILM = 32908
    # PIXARLOG = 32909
    # DEFLATE = 32946
    # DCS = 32947
    # JBIG = 34661
    # SGILOG = 34676
    # SGILOG24 = 34677
    # JP2000 = 34712

    @staticmethod
    def values():
        return list(map(int, COMPRESSION))


    @staticmethod
    def keys():
        return [e.name for e in COMPRESSION]


class IMGTile:
    """
        Object contains the data of an image strip
    """

    def __init__(self, index, data):
        self.index = index
        self.data = data
        self.count = len(data)


def lzw_encode(seq: bytes) -> bytes:
    """ Compressing LZW from a bytes

    Parameters:
        seq:
            bytes to compress
    """

    return imagecodecs._imcd.lzw_encode(seq)


def int_to_bytes(number: int, length=-1, is_big_endian=True) -> bytes:
    """ Convert an integer number to bytes

       Parameters:
            number:
                number to convert
            length:
                size of output bytes
            is_big_endian:
                endian byte order (True: big, False: little)
    """

    byteorder = 'big' if is_big_endian is True else 'little'
    if length == -1:
        length = (8 + (number + (number < 0)).bit_length()) // 8
    return number.to_bytes(length=length, byteorder=byteorder, signed=True)


def int_from_bytes(bytes_data: bytes, is_big_endian=True):
    """ Convert bytes to an integer number

       Parameters:
            bytes_data:
                bytes value
            is_big_endian:
                endian byte order (True: big, False: little)
    """
    byteorder = 'big' if is_big_endian is True else 'little'
    return int.from_bytes(bytes_data, byteorder=byteorder, signed=True)


def compression_image(img, rows_per_strip, predictor=PREDICTOR.NONE,
                      compression=COMPRESSION.NONE):
    """ Perform compression for an image

        Parameters:
            img:
                image data: numpy.array
            rows_per_strip:
                the number of rows per strip.
                StripsPerImage = floor ((ImageLength + RowsPerStrip - 1) / RowsPerStrip).
    """
    if predictor != 1:
        predictor_codec = predictor_encode_codec(predictor)
        img = predictor_codec(img, axis=-2, out=img)

    rs = []  # result

    height, width, samples_per_pixel = img.shape

    # number of strips(tiles) in the entire image
    strip_num = height // rows_per_strip

    # number of strips have enough {rows_per_strip}
    full_row_strip_num = strip_num

    # number of strips do not have enough {rows_per_strip}
    remainder = height % rows_per_strip

    if remainder > 0:
        strip_num += 1

    for i in range(strip_num):

        # start offset
        start = i * rows_per_strip

        if i == full_row_strip_num:
            tile = np.array(img[start: start + remainder, :width])
        else:
            tile = np.array(img[start: start + rows_per_strip, :width])

        size = tile.shape[0] * tile.shape[1] * samples_per_pixel
        tile = tile.reshape(size)

        # perform compression
        match compression:
            case COMPRESSION.ADOBE_DEFLATE:
                tile = zlib.compress(tile)
            case COMPRESSION.LZW:
                tile = lzw_encode(tile)

        # add the strip into result
        rs.append(IMGTile(i, tile))

    return rs


def predictor_encode_codec(key):
    try:
        match key:
            case PREDICTOR.NONE:
                return None
            case PREDICTOR.HORIZONTAL:
                codec = imagecodecs.delta_encode
            case PREDICTOR.FLOATINGPOINT:
                codec = imagecodecs.floatpred_encode
            case PREDICTOR.HORIZONTALX2:
                def codec(data, axis=-1, out=None):
                    return imagecodecs.delta_encode(
                        data, axis=axis, out=out, dist=2
                    )
            case PREDICTOR.HORIZONTALX4:
                def codec(data, axis=-1, out=None):
                    return imagecodecs.delta_encode(
                        data, axis=axis, out=out, dist=4
                    )
            case PREDICTOR.FLOATINGPOINTX2:
                def codec(data, axis=-1, out=None):
                    return imagecodecs.floatpred_encode(
                        data, axis=axis, out=out, dist=2
                    )
            case PREDICTOR.FLOATINGPOINTX4:
                def codec(data, axis=-1, out=None):
                    return imagecodecs.floatpred_encode(
                        data, axis=axis, out=out, dist=4
                    )
            case _:
                raise KeyError(f'{key} is not a known PREDICTOR')
    except AttributeError:
        raise KeyError(
            f'{PREDICTOR(key)!r}' " requires the 'imagecodecs' package"
        )
    except NotImplementedError:
        raise KeyError(f'{PREDICTOR(key)!r} not implemented')
    return codec
