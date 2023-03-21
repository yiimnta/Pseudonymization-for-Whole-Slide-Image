import jsonschema
import pathlib
import json
import os
import tifffile
from enum import IntEnum, Enum


abs_path_to_wsi_schema = './jsonschema/wsi.json'
abs_path_to_case_schema = './jsonschema/case.json'
abs_path_to_study_schema = './jsonschema/study.json'

class Vendor(Enum):
    """
        The library can read slides in the following formats:
    """
    APERIO = "Aperio"
    HAMAMATSU = "Hamamatsu"
    MIRAX = "Mirax"
    UNKNOWN = "Unknown"


class SupportFileType(Enum):
    """
        The library can read slides in the following extensions:
    """
    SVS = "svs"
    TIFF = "tiff"
    HAMAMATSU = "ndpi"
    MIRAX = "mrxs"


class SubImageType(IntEnum):
    """
        Associated Image type
    """
    LABEL = 1
    MACRO = 2


class Slide:
    """ Virtual Slide(WSI) class
                contains all data of the slide

                :parameter
                    path: path of slide
    """
    class SubImage:
        """ Associated Image class
            contains data of metadata of the image

            :parameter
                ifd: image file directory of the image (tifffile.TiffPage)

                img_type: image type (SubImageType)
        """

        def __init__(self, slide, ifd: tifffile.TiffPage, img_type: SubImageType):
            self.type = img_type
            self.height = ifd.imagelength
            self.width = ifd.imagewidth
            self.samples_per_pixel = ifd.samplesperpixel
            self.bits_per_sample = ifd.bitspersample
            self.compression = ifd.compression
            self.data_byte_counts = ifd.databytecounts
            self.data_offsets = ifd.dataoffsets
            self.description = ifd.description
            self.photometric = ifd.photometric
            self.ifd = ifd
            self.parent = slide

        def get_image_data(self):
            """ Get image data in tiles
                :return
                    numpy array
            """
            data = b""
            with open(self.parent.path, "rb") as f:
                f.seek(self.data_offsets[0])
                for count in self.data_byte_counts:
                    data += f.read(count)

            return data

        def get_image(self):
            """ Get image
                :return
                    numpy array
            """
            return self.ifd.asarray()


    class SlideMetadata:
        """ Virtual Slide Metadata class
           contains data of metadata of the slide

           :parameter
               slide: the instance of slide (tifffile.TiffFile)
       """
        class ImageInfo:
            """ Image short-info class
                contains some information of all images in the slide

                :parameter
                    series: image series of the image (tifffile.TiffPageSeries)
            """
            def __init__(self, series: tifffile.TiffPageSeries):
                self.name = series.name
                self.width = series.sizes["width"]
                self.height = series.sizes["height"]
                self.sample = series.sizes["sample"]
                self.num_levels = len(series.levels)
                self.levels = series.levels

        def __init__(self, slide: tifffile.TiffFile):

            self.vendor = Vendor.UNKNOWN

            if slide.is_svs is True:
                self.vendor = Vendor.APERIO
            elif slide.is_ndpi is True:
                self.vendor = Vendor.HAMAMATSU

            self.extension = slide.flags.pop() if (len(slide.flags) > 0) else ""
            self.is_bigtiff = slide.is_bigtiff
            self.images = []

            for series in slide.series:
                self.images.append(self.ImageInfo(series))

    def __init__(self, path):
        if check_path_exist(path) is False:
            return None
        self.path = path
        self.slide = tifffile.TiffFile(self.path)
        if len(self.slide.pages) == 0:
            raise Exception("Can not find any Image File Directory")

        self.metadata = self.SlideMetadata(self.slide)
        self.label = None
        self.macro = None

        if self.slide.is_svs is True:
            self.get_data_aperio()
        elif self.slide.is_ndpi is True:
            self.get_data_hamamatsu()

    def get_data_aperio(self):
        for ifd in self.slide.pages:
            try:
                img_description_tag = ifd.tags["ImageDescription"]
            except IndexError:
                continue

            if "label" in img_description_tag.value.lower():
                self.label = self.SubImage(self, ifd, img_type=SubImageType.LABEL)
            elif "macro" in img_description_tag.value.lower():
                self.macro = self.SubImage(self, ifd, img_type=SubImageType.MACRO)

    def get_data_hamamatsu(self):
        for ifd in self.slide.pages:
            try:
                source_lens_tag = ifd.tags.get(65421)
            except IndexError:
                continue
            # SourceLens of -1 in NDPI means the macro image
            if source_lens_tag.value == -1:
                self.macro = self.SubImage(ifd, img_type=SubImageType.MACRO)


class InputType(object):
    """ JSON Input type
    """
    SINGLE_WSI = "wsi"
    CASE = "case"
    STUDY = "study"


def check_path_exist(path):
    """
        used to check the existence of the path
        :param path: path of file
        :return: Boolean (True: existed)
    """
    if path is None:
        return False
    try:
        full_path = pathlib.Path(path).resolve()
        return os.path.exists(full_path)
    except Exception:
        return False


def check_format_support(path):
    """
        check whether file type is supported or not
        :param path:
        :return: Boolean (True: be supported)
    """
    full_path = pathlib.Path(path).resolve()
    try:
        slide = tifffile.TiffFile(full_path)
    except Exception:
        return False

    # get list of current supported extensions
    support_types = [e.value for e in SupportFileType]

    # the property flags contain the available extensions of the file
    for t in slide.flags:
        if t in support_types:
            return True

    return False


class InputData:
    """ JSON Input data class
        contains all data of the json input.
        During initialization, this class also checks the validity of the input json file.
        If the data is invalid, error messages will be added to error_messages

        :parameter
            json_path: path of the json input

    """
    def __init__(self, json_path):

        # check path
        json_path = pathlib.Path(json_path).resolve()

        if not os.path.exists(json_path):
            raise Exception(f'JSON-File not found: {json_path}')

        json_f = open(json_path)
        try:
            # load data from file
            json_data = json.load(json_f)
        except ValueError as e:
            raise Exception('Input file is not a JSON file')
        finally:
            json_f.close()

        # basic json to creating result json after pseudonymisation
        # copy() helps to avoid "pass by reference"
        self.basic_json = json_data.copy()

        # this json will be used to handle
        self.json_data = json_data

        # check input type
        self.type = InputType.SINGLE_WSI
        if "slides" in json_data:
            self.type = InputType.CASE
        elif "patients" in json_data:
            self.type = InputType.STUDY

        # validate input format
        self.error_messages = []
        self.validate()

        # if input is invalid
        if self.has_errors():
            return

        match self.type:
            case InputType.SINGLE_WSI:
                obj_path = f'$.path'
                s = self.get_slide(self.json_data["path"], obj_path)
                if self.has_errors() is False:
                    self.json_data["slide_data"] = s

            case InputType.CASE:
                for idx, slide in enumerate(self.json_data["slides"]):
                    obj_path = f'$.slides[{idx}]'
                    s = self.get_slide(slide["path"], obj_path)
                    if self.has_errors() is False:
                        self.json_data["slides"][idx]["slide_data"] = s

            case InputType.STUDY:
                for pa_idx, patient in enumerate(self.json_data["patients"]):
                    for idx, slide in enumerate(patient["slides"]):
                        obj_path = f'$.patients[{pa_idx}].slides[{idx}]'
                        s = self.get_slide(slide["path"], obj_path)
                        if self.has_errors() is False:
                            self.json_data["patients"][pa_idx]["slides"][idx]["slide_data"] = s

    def get_slide(self, slide_path, obj_path):
        s = Slide(slide_path)

        if s.metadata.vendor is Vendor.UNKNOWN:
            self.error_messages.append(f'{obj_path}: Data type is still not supported: {slide_path}')

        elif s.metadata.is_bigtiff is True:
            self.error_messages.append(f'{obj_path}: BigTIFF format is still not supported: {slide_path}')

        elif s.label is None and s.macro is None:
            self.error_messages.append(f'{obj_path}: Label and Macro Images can not be found in slide: {slide_path}')

        return s

    def has_errors(self):
        return len(self.error_messages) > 0

    def print_errors(self):
        for error in self.error_messages:
            print(error)

    def load_schema(self, schema_path):
        """Load the JSON schema.
        :param:
            schema_path: filename for a JSON schema.
        returns:
            return schema.
        """
        try:
            with open(schema_path, 'r') as fp:
                schema = json.load(fp)
        except ValueError as e:
            raise Exception(f'Invalid JSON {schema_path}: ',  str(e))

        return schema

    def validate(self):
        """
            Validate json input
            :returns Tuple(bool, array):
                + bool: TRUE when there is no error message.
                + array: error message array
        """
        # BEGIN: check null, type
        match self.type:
            case InputType.SINGLE_WSI:
                schema_wsi = self.load_schema(abs_path_to_wsi_schema)
                v = jsonschema.Draft202012Validator(schema_wsi)
            case InputType.CASE:
                schema_case = self.load_schema(abs_path_to_case_schema)
                v = jsonschema.Draft202012Validator(schema_case)
            case InputType.STUDY:
                schema_study = self.load_schema(abs_path_to_study_schema)
                v = jsonschema.Draft202012Validator(schema_study)

        errors = sorted(v.iter_errors(self.json_data), key=lambda e: e.path)
        self.error_messages = [f'{error.json_path}: {error.message}' for error in errors]

        # END: check null, type

        if self.has_errors():
            return

        try:
            # check path, format-support of all slides exist or not
            match self.type:
                case InputType.SINGLE_WSI:
                    s_path = self.json_data["path"]
                    if check_path_exist(s_path) is False:
                        self.error_messages.append(f'{s_path}, file not found')
                    else:
                        if check_format_support(s_path) is False:
                            self.error_messages.append(f'{s_path}, file format is not supported')
                case InputType.CASE:
                    slides = self.json_data["slides"]
                    for idx, slide in enumerate(slides):
                        s_path = slide["path"]
                        if check_path_exist(s_path) is False:
                            self.error_messages.append(f'$.slides[{idx}]: {s_path}, file not found')
                        else:
                            if check_format_support(s_path) is False:
                                self.error_messages.append(f'$.slides[{idx}]: {s_path}, file format is not supported')
                case InputType.STUDY:
                    patients = self.json_data["patients"]
                    for p_idx, patient in enumerate(patients):
                        slides = patient["slides"]
                        for s_idx, slide in enumerate(slides):
                            s_path = slide["path"]
                            if check_path_exist(s_path) is False:
                                self.error_messages.append(f'$.patients[{p_idx}].slides[{s_idx}]: {s_path}, file not '
                                                           f'found')
                            else:
                                if check_format_support(s_path) is False:
                                    self.error_messages.append(f'$.patients[{p_idx}].slides[{s_idx}]: {s_path}, file '
                                                               f'format is not supported')
        except Exception as e:
            self.error_messages.append(str(e))
