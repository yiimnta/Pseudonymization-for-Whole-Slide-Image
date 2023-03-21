import tifffile

from input_handler import InputData, InputType, Vendor, Slide
from faker import Faker
from nanoid import generate
import dateutil.parser
import random
import shutil
from pathlib import Path
import os
import pseudonymisation_utils as pu
import compression_utils as cu
import db.db as db
import db.model as model
from enum import IntEnum
from cryptography.fernet import Fernet, InvalidToken
import json
import numpy as np

STORE_PATH = "data/store/"  # store path
STORE_FILE_NAME_SIZE = 20  # length of filename in the store
DATE_FORMAT = "%d.%m.%Y"  # date format in JSON output
DATETIME_FORMAT = "%I:%M%p %d.%m.%Y"  # datetime format in JSON output


# .strftime(DATETIME_FORMAT)


def generate_id(size=13) -> str:
    """
        using nanoid to generate kinda unique string ID with length = size
        with alphabet is 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz
        based on Nano ID Collision Calculator: https://zelark.github.io/nano-id-cc/

        Get 100 IDs/ sec
            size 13:  ~7 thousand years needed, in order to have a 1% probability of at least one collision.
            //   14: ~57 thousand years
            //   15: ~448 thousand years

        :param size: length of id, default 13
        :return: uid (Str)
    """
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    return f'{generate(alphabet, size)}'


def generate_person_name() -> str:
    """
        using faker to generate a pseudo fullname
        :return: fullname (str)
    """
    faker = Faker()
    return faker.name()


def generate_random_date_from_str(date_str, gap_year=0):
    """
        using nanoid to generate date between (date_str - gap year, now)
        the randomized date will never be same the input date
        :param:
            date_str: date
            gap_year: to calc "start date"
        :return: randomized date (Date/DateTime)
    """
    faker = Faker()
    dt = dateutil.parser.parse(date_str)
    start_date = dt.replace(year=dt.year - gap_year)

    while True:
        if (dt.hour + dt.minute + dt.second) > 0:  # if input date is datetime type
            new_date = faker.date_time_between(start_date=start_date, end_date='now')
        else:
            # input date is date type
            new_date = faker.date_between(start_date=dt, end_date='now')

        # if new date and input date are not the same
        if new_date != dt:
            return new_date

    return None


async def create_unique_pseudo_id(slide_id, db_model, check_exist_trials=10):
    """
        using nanoid to generate kinda unique string pseudo-ID
        :param
            slide_id: Slide ID
            db_model: Model of Database (Study, WSI and Case)
            check_exist_trials:
                number of trials to generate pseudo id. It means when the pseudo id was already in DB,
                so the pseudo id will be re-randomized.
                after all trials, still be existed then throws an exception.
        :return: pseudo-uid (Str)
    """

    # generate pseudo id
    pseudo_id = generate_id()

    # go to database to check exist of new pseudo id
    while check_exist_trials >= 0:
        async with model.Session() as session:
            async with session.begin():
                dao_instance = db.DAO(db_model, session)
                obj = await dao_instance.get_by_pseudo_id(pseudo_id)

                # pseudo_id was already existed
                if obj is not None:
                    check_exist_trials -= 1
                else:
                    # not exist
                    break

                if check_exist_trials <= 0:
                    # ran out trials
                    raise Exception(f"Slide {slide_id}: Can not create pseudo-ID, please try again!")

    return pseudo_id


async def get_object_by_id(object_id, db_model, get_children=False):
    """
        get Object in DB by id
        :param
            id: Object's ID
            db_model: Model of Database (Study, WSI and Case)
            get_children:
                this flag True means the children objects will be taken also
                e.g. slides are the children of case and patient
        :return: pseudo-object
    """

    async with model.Session() as session:
        async with session.begin():
            match db_model:
                case model.WSI:
                    dao_instance = db.WSIDAO(session)
                case model.Case:
                    dao_instance = db.CaseDAO(session)
                    if get_children:
                        return await dao_instance.get_by_id_with_slides(object_id)
                case model.Patient:
                    dao_instance = db.PatientDAO(session)
                    if get_children:
                        return await dao_instance.get_by_id_with_slides(object_id)
                case model.Study:
                    dao_instance = db.StudyDAO(session)
                    if get_children:
                        return await dao_instance.get_by_id_with_patients(object_id)
                case _:
                    raise Exception("Model is not valid")

            return await dao_instance.get(object_id)


async def get_object_by_pseudo_id(object_pseudo_id, db_model, get_children=False):
    """
        get Object in DB by pseudo-id
        :param
            pseudo-id: Object's pseudo-ID
            db_model: Model of Database (Study, WSI and Case)
            get_children:
                this flag True means the children objects will be taken also
                e.g. slides are the children of case and patient
        :return: pseudo-object
    """
    async with model.Session() as session:
        async with session.begin():
            match db_model:
                case model.WSI:
                    dao_instance = db.WSIDAO(session)
                case model.Case:
                    dao_instance = db.CaseDAO(session)
                    if get_children:
                        return await dao_instance.get_by_pseudo_id_with_slides(object_pseudo_id)
                case model.Patient:
                    dao_instance = db.PatientDAO(session)
                    if get_children:
                        return await dao_instance.get_by_pseudo_id_with_slides(object_pseudo_id)
                case model.Study:
                    dao_instance = db.StudyDAO(session)
                    if get_children:
                        return await dao_instance.get_by_pseudo_id_with_patients(object_pseudo_id)
                case _:
                    raise Exception("Model is not valid")

            return await dao_instance.get_by_pseudo_id(object_pseudo_id)


def create_file_path_in_store(store_folder_path):
    """
        create image path in the store
        the filename of the image will be randomized. This makes it more secure

        :param store_folder_path: store path (Path)
        :return: filename, path string
    """
    # generate uid as filename
    fname = generate_id(size=STORE_FILE_NAME_SIZE)

    # create store path
    f_path = store_folder_path.joinpath(fname, '')
    root, ext = os.path.splitext(f_path)
    i = 0

    # if the path already existed, add a number in suffix of filename
    while os.path.exists(f_path):
        i += 1
        f_path = '%s_%i%s' % (root, i, ext)

    return fname, f_path


class WSI:
    """
        Slide (WSI) class
        contains information will be stored in DB
    """

    def __init__(self):
        self.vendor = None
        self.id = None
        self.name = None
        self.acquired_at = None
        self.tissue = None
        self.stain = None
        self.path = None
        self.pseudo_id = None
        self.pseudo_name = None
        self.pseudo_acquired_at = None
        self.pseudo_metadata_name = None
        self.pseudo_metadata_key = None
        self.pseudo_label_name = None
        self.pseudo_label_key = None
        self.pseudo_macro_name = None
        self.pseudo_macro_key = None
        self.pseudo_file_path = None
        self.fields_count = 1  # the number of fields will be written on label
        self.get_from_database = False  # flag to check, whether data will be taken from DB?
        self.need_to_be_updated = set()  # contains something new needs to be updated in DB
        self.slide_data = None

    async def create(self, pseudo, input_data=None):
        """
            to generate pseudo-data from json-data, if the slide ID existed already in DB,
            the pseudo-data will be not created anymore and just be taken from DB through the ID.
            :param pseudo: Pseudonymisation object
            :param input_data:  slide json data
            :return: WSI Object
        """
        """
            to get origin-data (include pseudo-data) in DB by pseudo-ID.
            This function is used to de-pseudonymisation
            :param pseudo: Pseudonymisation object
            :param input_data:  slide json pseudo-data
            :return: WSI Object
        """
        if input_data is None:
            input_data = pseudo.input_data.json_data

        self.id = input_data["id"]
        try:
            """
                if the slide has already made pseudonymous before
                then we just get its old data in the database, 
                no need to create new pseudonymous data.
            """
            pseudo_wsi = await get_object_by_id(self.id, model.WSI)

            if pseudo_wsi is not None:  # already existed in DB
                self.pseudo_id = pseudo_wsi.pseudo_id
                self.pseudo_name = pseudo_wsi.pseudo_name
                self.pseudo_acquired_at = pseudo_wsi.pseudo_acquired_at
                self.pseudo_metadata_name = pseudo_wsi.pseudo_metadata_name
                self.pseudo_metadata_key = pseudo_wsi.pseudo_metadata_key

                # get_from_database flag informs the pseudo-data taken from database
                self.get_from_database = True
            else:
                # not existed in DB, generate new pseudo id
                self.pseudo_id = await create_unique_pseudo_id(self.id, model.WSI)
        except Exception as ex:
            print(str(ex))
            return None

        if "name" in input_data:
            self.name = input_data["name"]
            if pseudo_wsi is None:
                self.pseudo_name = f'wsi_{self.pseudo_id}'
            else:   # pseudo wsi is not None
                if pseudo_wsi.name is None:
                    self.pseudo_name = f'wsi_{self.pseudo_id}'
                    self.need_to_be_updated.add("name")
                    self.need_to_be_updated.add("pseudo_name")
                elif pseudo_wsi.name != self.name:
                    self.need_to_be_updated.add("name")

            self.fields_count += 1

        if "acquired_at" in input_data:
            self.acquired_at = dateutil.parser.parse(input_data["acquired_at"])
            if pseudo_wsi is None:
                self.pseudo_acquired_at = generate_random_date_from_str(input_data["acquired_at"],
                                                                        gap_year=pseudo.gap_year)
            else:
                if pseudo_wsi.acquired_at is None:
                    self.pseudo_acquired_at = generate_random_date_from_str(input_data["acquired_at"],
                                                                        gap_year=pseudo.gap_year)
                    self.need_to_be_updated.add("acquired_at")
                    self.need_to_be_updated.add("pseudo_acquired_at")
                elif pseudo_wsi.acquired_at != self.acquired_at:
                    self.need_to_be_updated.add("acquired_at")

            self.fields_count += 1

        if "stain" in input_data:
            self.stain = input_data["stain"]
            self.fields_count += 1
            if pseudo_wsi is not None:
                if pseudo_wsi.stain is None or pseudo_wsi.stain != self.stain:
                    self.need_to_be_updated.add("stain")

        if "tissue" in input_data:
            self.tissue = input_data["tissue"]
            self.fields_count += 1
            if pseudo_wsi is not None:
                if pseudo_wsi.tissue is None or pseudo_wsi.tissue != self.tissue:
                    self.need_to_be_updated.add("tissue")

        # path of file
        self.path = input_data["path"]

        # image data
        self.slide_data = input_data["slide_data"]

        # file type
        self.vendor = self.slide_data.metadata.vendor

        return self

    async def get(self, pseudo, input_data=None):
        """
            to get origin-data (include pseudo-data) in DB by pseudo-ID.
            This function is used to de-pseudonymisation
            :param pseudo: Pseudonymisation object
            :param input_data:  slide json pseudo-data
            :return: WSI Object
        """
        if input_data is None:
            input_data = pseudo.input_data.json_data

        self.pseudo_id = input_data["id"]

        try:
            # get pseudo-object by pseudo id
            pseudo_wsi = await get_object_by_pseudo_id(self.pseudo_id, model.WSI)

            if pseudo_wsi is not None:
                self.id = pseudo_wsi.id
                self.name = pseudo_wsi.name
                self.acquired_at = pseudo_wsi.acquired_at
                self.tissue = pseudo_wsi.tissue
                self.stain = pseudo_wsi.stain
                self.pseudo_name = pseudo_wsi.pseudo_name
                self.pseudo_acquired_at = pseudo_wsi.pseudo_acquired_at
                self.pseudo_metadata_name = pseudo_wsi.pseudo_metadata_name
                self.pseudo_metadata_key = pseudo_wsi.pseudo_metadata_key
                self.pseudo_label_name = pseudo_wsi.pseudo_label_name
                self.pseudo_label_key = pseudo_wsi.pseudo_label_key
                self.pseudo_macro_name = pseudo_wsi.pseudo_macro_name
                self.pseudo_macro_key = pseudo_wsi.pseudo_macro_key
                self.pseudo_file_path = input_data["path"]
                self.slide_data = input_data["slide_data"]
                self.vendor = self.slide_data.metadata.vendor
                self.get_from_database = True
            else:
                raise Exception(f"Pseudonym Slide[id={self.pseudo_id}] is not found")
        except Exception as e:
            print(str(e))
            return None

        return self


class Case:
    """
        Case class
        contains information will be stored in DB
    """

    def __init__(self):
        self.id = None
        self.name = None
        self.created_at = None
        self.pseudo_id = None
        self.pseudo_name = None
        self.pseudo_created_at = None
        self.slides = []
        self.fields_count = 1  # the number of fields will be written on label
        self.get_from_database = False  # flag to check, whether data will be taken from DB?
        self.need_to_be_updated = set()  # contains something new needs to be updated in DB

    async def create(self, pseudo):
        """
            to generate pseudo-data from json-data, if the slide ID existed already in DB,
            the pseudo-data will be not created anymore and just be taken from DB through the ID.
            :param pseudo: Pseudonymisation object
            :return: Case Object
        """
        input_data = pseudo.input_data.json_data
        self.id = input_data["id"]
        try:
            """
                if the case has already made pseudonymous before
                then we just get its old data in the database, 
                no need to create new pseudonymous data for this case.
            """
            pseudo_case = await get_object_by_id(self.id, model.Case)

            if pseudo_case is not None:
                self.pseudo_id = pseudo_case.pseudo_id
                self.pseudo_name = pseudo_case.pseudo_name
                self.pseudo_created_at = pseudo_case.pseudo_created_at

                # get_from_database flag informs the pseudo-data taken from database
                self.get_from_database = True
            else:
                self.pseudo_id = await create_unique_pseudo_id(self.id, model.Case)
        except Exception as ex:
            print(str(ex))
            return None

        if "name" in input_data:
            self.name = input_data["name"]
            if pseudo_case is None:
                self.pseudo_name = f'case_{self.pseudo_id}'
            else:  # pseudo_case is not None
                if pseudo_case.name is None:
                    self.pseudo_name = f'case_{self.pseudo_id}'
                    self.need_to_be_updated.add("name")
                    self.need_to_be_updated.add("pseudo_name")
                elif pseudo_case.name != self.name:
                    self.need_to_be_updated.add("name")
            self.fields_count += 1

        if "created_at" in input_data:
            self.created_at = dateutil.parser.parse(input_data["created_at"])

            if pseudo_case is None:
                self.pseudo_created_at = generate_random_date_from_str(input_data["created_at"],
                                                                       gap_year=pseudo.gap_year)
            else:
                if pseudo_case.created_at is None:
                    self.pseudo_created_at = generate_random_date_from_str(input_data["created_at"],
                                                                           gap_year=pseudo.gap_year)
                    self.need_to_be_updated.add("created_at")
                    self.need_to_be_updated.add("pseudo_created_at")
                elif pseudo_case.created_at != self.created_at:
                    self.need_to_be_updated.add("created_at")

        # read slides from json to create pseudo data for each slide
        for slide in input_data['slides']:
            wsi = WSI()
            await wsi.create(pseudo, input_data=slide)
            self.slides.append(wsi)

        return self

    async def get(self, pseudo):
        """
            to get origin-data (include pseudo-data) in DB by pseudo-ID.
            This function is used to de-pseudonymisation
            :param pseudo: Pseudonymisation object
            :return: Case Object
        """
        # insert data
        input_data = pseudo.input_data.json_data
        self.pseudo_id = input_data["id"]

        try:
            # get pseudo-object by pseudo-id
            pseudo_case = await get_object_by_pseudo_id(self.pseudo_id, model.Case, get_children=True)

            if pseudo_case is not None:
                self.id = pseudo_case.id
                self.name = pseudo_case.name
                self.created_at = pseudo_case.created_at
                self.pseudo_name = pseudo_case.pseudo_name
                self.pseudo_created_at = pseudo_case.pseudo_created_at
                # get_from_database flag informs the pseudo-data taken from database
                self.get_from_database = True

                # get all slide's ids of the case,
                # then checks whether the slide in the input json belongs to the case or not
                slide_pseudo_ids = [sl.pseudo_id for sl in pseudo_case.slides]

                for slide in input_data['slides']:
                    if slide['id'] not in slide_pseudo_ids:
                        # if the slide does not belong to the case
                        print(f"No data found between Slide[id={slide['id']}] and Case[id={self.pseudo_id}]")
                        continue
                    wsi = WSI()
                    await wsi.get(pseudo, input_data=slide)
                    self.slides.append(wsi)
            else:
                raise Exception(f"Pseudonym Case[id={self.pseudo_id}] is not found")
        except Exception as e:
            print(str(e))
            return None

        return self


class Patient:
    """
        Patient class
        contains information will be stored in DB
    """

    class SEX(IntEnum):
        FEMALE = 1
        MALE = 2
        UNKNOWN = 3

    def __init__(self):
        self.id = None
        self.name = None
        self.sex = self.SEX.UNKNOWN
        self.age = 0
        self.pseudo_id = None
        self.pseudo_name = None
        self.pseudo_age = 0
        self.slides = []
        self.fields_count = 1  # the number of fields will be written on label
        self.get_from_database = False  # flag to check, whether data will be taken from DB?
        self.need_to_be_updated = set()  # contains something new needs to be updated in DB

    async def create(self, pseudo, input_data=None):
        """
            to generate pseudo-data from json-data, if the slide ID existed already in DB,
            the pseudo-data will be not created anymore and just be taken from DB through the ID.
            :param pseudo: Pseudonymisation object
            :param input_data: Patient json data
            :return: Patient Object
        """
        if input_data is None:
            input_data = pseudo.input_data.json_data

        self.id = input_data["id"]
        try:
            """
                if the patient has already made pseudonymous before
                then we just get its old data in the database, 
                no need to create new pseudonymous data for this patient.
            """
            pseudo_patient = await get_object_by_id(self.id, model.Patient)

            if pseudo_patient is not None:
                self.pseudo_id = pseudo_patient.pseudo_id
                self.pseudo_name = pseudo_patient.pseudo_name
                self.pseudo_age = pseudo_patient.pseudo_age

                # get_from_database flag informs the pseudo-data taken from database
                self.get_from_database = True
            else:
                self.pseudo_id = await create_unique_pseudo_id(self.id, model.Patient)
        except Exception as ex:
            print(str(ex))
            return None

        if "name" in input_data:
            self.name = input_data["name"]
            if pseudo_patient is None:
                self.pseudo_name = generate_person_name()
            else:
                if pseudo_patient.name is None:
                    self.pseudo_name = generate_person_name()
                    self.need_to_be_updated.add("name")
                    self.need_to_be_updated.add("pseudo_name")
                elif pseudo_patient.name != self.name:
                    self.need_to_be_updated.add("name")

        if "sex" in input_data:
            sex = str(input_data["sex"]).lower()
            if sex == "male":
                self.sex = self.SEX.MALE
            elif sex == "female":
                self.sex = self.SEX.FEMALE
            else:
                self.sex = self.SEX.UNKNOWN

            if pseudo_patient is not None:
                if pseudo_patient.sex is None or pseudo_patient.sex != self.sex.value:
                    self.need_to_be_updated.add("sex")

        if "age" in input_data:
            self.age = int(input_data["age"])
            if pseudo_patient is None:
                self.pseudo_age = random.randint(20, 70)  # random age between 20 and 70
            else:
                if pseudo_patient.age is None:
                    self.pseudo_age = random.randint(20, 70)
                    self.need_to_be_updated.add("age")
                    self.need_to_be_updated.add("pseudo_age")
                elif pseudo_patient.age != self.age:
                    self.need_to_be_updated.add("age")

        # read slides from json to create pseudo data for each slide
        for slide in input_data["slides"]:
            wsi = WSI()
            await wsi.create(pseudo, input_data=slide)
            self.slides.append(wsi)

        return self

    async def get(self, pseudo, input_data=None):
        """
            to get origin-data (include pseudo-data) in DB by pseudo-ID.
            This function is used to de-pseudonymisation
            :param pseudo: Pseudonymisation object
            :param input_data: Patient json pseudo-data
            :return: Patient Object
        """
        # insert data
        if input_data is None:
            input_data = pseudo.input_data.json_data

        self.pseudo_id = input_data["id"]

        try:
            # get pseudo-object by pseudo-id
            pseudo_patient = await get_object_by_pseudo_id(self.pseudo_id, model.Patient, get_children=True)

            if pseudo_patient is not None:
                self.id = pseudo_patient.id
                self.name = pseudo_patient.name
                self.age = pseudo_patient.age
                self.pseudo_name = pseudo_patient.pseudo_name
                self.pseudo_age = pseudo_patient.pseudo_age
                self.get_from_database = True

                # get all slide's ids of the patient,
                # then checks whether the slide in the input json belongs to the patient or not
                slide_pseudo_ids = [sl.pseudo_id for sl in pseudo_patient.slides]

                for slide in input_data['slides']:
                    if slide['id'] not in slide_pseudo_ids:
                        # if the slide does not belong to the patient
                        print(f"No data found between Slide[id={slide['id']}] and Patient[id={self.pseudo_id}]")
                        continue
                    wsi = WSI()
                    await wsi.get(pseudo, input_data=slide)
                    self.slides.append(wsi)
            else:
                raise Exception(f"Pseudonym Patient[id={self.pseudo_id}] is not found")
        except Exception as e:
            print(str(e))
            return None

        return self


class Study:
    """
        Study class
        contains information will be stored in DB
    """

    def __init__(self):
        self.id = None
        self.name = None
        self.date = None
        self.pseudo_id = None
        self.pseudo_name = None
        self.pseudo_date = None
        self.patients = []
        self.fields_count = 1  # the number of fields will be written on label
        self.get_from_database = False  # flag to check, whether data will be taken from DB?
        self.need_to_be_updated = set()  # contains something new needs to be updated in DB

    async def create(self, pseudo):
        """
            to generate pseudo-data from json-data, if the slide ID existed already in DB,
            the pseudo-data will be not created anymore and just be taken from DB through the ID.
            :param pseudo: Pseudonymisation object
            :return: Study Object
        """
        input_data = pseudo.input_data.json_data

        self.id = input_data["id"]
        try:
            """
                if the study has already made pseudonymous before
                then we just get its old data in the database, 
                no need to create new pseudonymous data for this study.
            """
            pseudo_study = await get_object_by_id(self.id, model.Study)

            if pseudo_study is not None:
                self.pseudo_id = pseudo_study.pseudo_id
                self.pseudo_name = pseudo_study.pseudo_name
                self.pseudo_date = pseudo_study.pseudo_date

                # get_from_database flag informs the pseudo-data taken from database
                self.get_from_database = True
            else:
                self.pseudo_id = await create_unique_pseudo_id(self.id, model.Study)
        except Exception as ex:
            print(str(ex))
            return None

        if "name" in input_data:
            self.name = input_data["name"]
            if pseudo_study is None:
                self.pseudo_name = f'study_{self.pseudo_id}'
            else:
                if pseudo_study.name is None:
                    self.pseudo_name = f'study_{self.pseudo_id}'
                    self.need_to_be_updated.add("name")
                    self.need_to_be_updated.add("pseudo_name")
                elif pseudo_study.name != self.name:
                    self.need_to_be_updated.add("name")
            self.fields_count += 1

        if "date" in input_data:
            self.date = dateutil.parser.parse(input_data["date"])

            if pseudo_study is None:
                self.pseudo_date = generate_random_date_from_str(input_data["date"],
                                                                 gap_year=pseudo.gap_year)
            else:
                if pseudo_study.date is None:
                    self.pseudo_date = generate_random_date_from_str(input_data["date"],
                                                                 gap_year=pseudo.gap_year)
                    self.need_to_be_updated.add("date")
                    self.need_to_be_updated.add("pseudo_date")
                elif pseudo_study.date != self.date:
                    self.need_to_be_updated.add("date")

        # read patients from json to create pseudo data for each patient
        for in_patient in input_data['patients']:
            patient = Patient()
            await patient.create(pseudo, input_data=in_patient)
            self.patients.append(patient)

        return self

    async def get(self, pseudo):
        """
            to get origin-data (include pseudo-data) in DB by pseudo-ID.
            This function is used to de-pseudonymisation
            :param pseudo: Pseudonymisation object
            :return: Study Object
        """
        input_data = pseudo.input_data.json_data
        self.pseudo_id = input_data["id"]

        try:
            # get pseudo-object by pseudo-id
            pseudo_study = await get_object_by_pseudo_id(self.pseudo_id, model.Study, get_children=True)

            if pseudo_study is not None:
                self.id = pseudo_study.id
                self.name = pseudo_study.name
                self.date = pseudo_study.date
                self.pseudo_name = pseudo_study.pseudo_name
                self.pseudo_date = pseudo_study.pseudo_date
                self.get_from_database = True

                # get all patient's ids of the study,
                # then checks whether the patient in the input json belongs to the study or not
                patient_pseudo_ids = [pat.pseudo_id for pat in pseudo_study.patients]

                for patient_data in input_data['patients']:
                    if patient_data['id'] not in patient_pseudo_ids:
                        # if the patient does not belong to the study
                        print(f"No data found between Patient[id={patient_data['id']}] and Study[id={self.pseudo_id}]")
                        continue

                    patient = Patient()
                    await patient.get(pseudo, input_data=patient_data)
                    self.patients.append(patient)

            else:
                raise Exception(f"Pseudonym Study[id={self.pseudo_id}] is not found")
        except Exception as e:
            print(str(e))
            return None

        return self


class Pseudonymization:
    """
        This class is used to perform Pseudonymization and de-Pseudonymization on WSI images.
        However, each instance of the Pseudonymisation-class cannot perform both pseudonymisation and
        de-pseudonymisation features. Depending on whether is_de_pseudonym is False or True,
        the instance created has the possibility of Pseudonymization(False) or de-Pseudonymization (True).
        Default of is_de_pseudonym is False

        :param:
            input_data: contains information about the input json file.
            is_de_pseudonym: is a flag, default is False
                    if False: An instance for Pseudonymization will be created.
                    if True: An instance for De-Pseudonymization will be created.

    """

    def __init__(self, input_data: InputData, is_de_pseudonym=False):

        if input_data.has_errors():
            input_data.print_errors()
            print("Input data is invalid")
            return None

        self.input_data = input_data
        self.is_de_pseudonym = is_de_pseudonym
        self.gap_year = -1
        self.pseudo_data = None

    async def create(self):
        """
            generate pseudo-data when it is a pseudonymization form.
            and get origin-data when it is a de-pseudo form.
            :return: Pseudonymization object
        """
        if self.input_data is None or self.input_data.json_data is None:
            # Input data is invalid
            return self

        try:
            # based on type of input data, pseudo-data will be generated by other ways
            match self.input_data.type:
                case InputType.SINGLE_WSI:
                    self.pseudo_data = WSI()
                case InputType.CASE:
                    self.pseudo_data = Case()
                case InputType.STUDY:
                    self.pseudo_data = Study()

            if self.is_de_pseudonym:
                # get origin data
                rs = await self.pseudo_data.get(self)
            else:

                # gap year is used to calculate random date
                self.gap_year = random.randint(1, 8)

                # generate pseudo-data
                rs = await self.pseudo_data.create(self)

            if rs is None:
                raise Exception("Something wrong during creating data for Pseudonymization")
        except Exception as ex:
            print(str(ex))
            self.pseudo_data = None

        return self

    async def perform_pseudonym(self):
        """
            controller of perform pseudonymisation
        """

        # if there is any error during generating pseudo-data
        if self.pseudo_data is None:
            print("Can not generate pseudo-data")
            return None

        if self.is_de_pseudonym:
            print("Can not perform pseudonym when the object is a de-pseudonym instance")
            return None

        match self.input_data.type:
            case InputType.SINGLE_WSI:
                return await self.perform_single_wsi()
            case InputType.CASE:
                return await self.perform_case()
            case InputType.STUDY:
                return await self.perform_study()

        return None

    async def perform_de_pseudonym(self):
        """
            controller of perform de-pseudonymisation
        """

        # if there is any error during generating pseudo-data
        if self.pseudo_data is None:
            print("Data is not found. Can not de-pseudonym")
            return None

        if self.is_de_pseudonym is False:
            print("Can not perform de-pseudonym when the object is a pseudonym instance")
            return None

        match self.input_data.type:
            case InputType.SINGLE_WSI:
                return await self.perform_de_single_wsi()
            case InputType.CASE:
                return await self.perform_de_case()
            case InputType.STUDY:
                return await self.perform_de_study()

        return None

    def check_store_path(self):
        """
            Check store path valid
            :return: path of store (Path)
        """
        if STORE_PATH is not None:
            try:
                os.makedirs(STORE_PATH)
            except FileExistsError:
                pass
            except Exception as ex:
                print(f"Store path is not valid:{str(ex)}")
                return None

            store_folder = Path(STORE_PATH)
            return store_folder
        else:
            print("Store path is not None")
            return None

    def check_valid_before_pseudonym(self, input_type: InputType):
        """
            Validate some input data before pseudonymisation
            :param input_type:
            :return: Boolean
        """
        if self.is_de_pseudonym:
            return "Can not perform pseudonym when the object is a de-pseudonym instance"

        if self.input_data is None or self.pseudo_data is None:
            return "Data not found"

        if self.input_data.type is not input_type:
            return "Data is not valid"

    def check_valid_before_de_pseudonym(self, input_type: InputType):
        """
            Validate some input data before de-pseudonymisation
            :param input_type:
            :return: Boolean
        """
        if self.is_de_pseudonym is False:
            return "Can not perform de-pseudonym when the object is a pseudonym instance. " \
                   "Set is_de_pseudonym = True please!"

        if self.input_data is None or self.pseudo_data is None:
            return "Data not found"

        if self.input_data.type is not input_type:
            return "Data is not valid"

    def copy_clone(self, slide, dest_folder: Path, prefix_error=""):
        """
            Copy a clone of the Slide "slide" into "dest_folder"
            :param slide: WSI data
            :param dest_folder: destination folder path
            :param prefix_error: prefix of message
            :return destination file path
        """
        try:

            if self.is_de_pseudonym:
                start_path = Path(slide.pseudo_file_path)
                slide_id = slide.id
            else:
                start_path = Path(slide.path)
                slide_id = slide.pseudo_id

            # create clone path (dest_path)
            if dest_folder is None:
                dest_path = start_path.with_stem(slide_id)
            else:
                dest_path = dest_folder.joinpath(slide_id, start_path.suffix)
            file_counter = 1

            # if clone path already existed
            while dest_path.exists():
                dest_path = dest_path.with_stem(f"{slide_id}_{file_counter}")
                file_counter += 1

            # copy clone
            shutil.copy2(start_path, dest_path)

            return dest_path

        except Exception as e:
            raise Exception(f"{prefix_error}Can not copy clone of the Slide: {str(e)}") from None

    def create_pseudonym(self, slide: WSI, case: Case = None,
                         patient: Patient = None, study: Study = None, prefix_error=""):
        """
            Create pseudonym based on type of JSON input
            :param slide: WSI data
            :param case:  Case of WSI
            :param patient: Patient of WSI
            :param study: Study of Patient and WSI
            :param prefix_error: prefix of message
            :return: pseudonym label (numpy array)
        """
        input_type = self.input_data.type

        try:
            if slide is None:
                raise Exception(f"{prefix_error}Slide data is None")

            if input_type is InputType.CASE and case is None:
                raise Exception(f"{prefix_error}Case data is None")

            if input_type is InputType.STUDY:
                if patient is None:
                    raise Exception(f"{prefix_error}Patient data is None")
                if study is None:
                    raise Exception(f"{prefix_error}Study data is None")

            # label image
            label = slide.slide_data.label
            # macro = slide_data.macro

            if label is None:
                raise Exception(f"{prefix_error}Can not find the label of the Slide")

            # define a schema (content table) for pseudonym-label
            col_num = 1
            row_num = slide.fields_count

            if input_type is InputType.CASE:
                row_num += case.fields_count

            if input_type is InputType.STUDY:
                row_num += patient.fields_count + study.fields_count

            ratio = label.width / label.height
            padding = (0, 15, 10, 15)  # padding default (ratio 1:1)

            if ratio < 1.5:  # ratio 3:2
                padding = (5, 10, 15, 10)

            row_num += 1  # adding a row for barcode

            schema = pu.Schema(col_num, row_num, padding=padding)

            # add info of slide to pseudo-label
            row = 0

            # add info of case
            if input_type is InputType.CASE:
                schema.add_cell(
                    pu.Field(case.pseudo_id, 0, row, font_size=10,
                             font=pu.EFieldFont.HMADURAI))
                row += 1

                if case.name is not None:
                    schema.add_cell(
                        pu.Field(case.pseudo_name, 0, row, font_size=10,
                                 font=pu.EFieldFont.HMADURAI))
                    row += 1

            elif input_type is InputType.STUDY:
                # add info of study
                schema.add_cell(
                    pu.Field(study.pseudo_id, 0, row, font_size=10,
                             font=pu.EFieldFont.HMADURAI))
                row += 1

                if study.name is not None:
                    schema.add_cell(
                        pu.Field(study.pseudo_name, 0, row, font_size=10,
                                 font=pu.EFieldFont.HMADURAI))
                    row += 1

                # add info of patient
                schema.add_cell(
                    pu.Field(patient.pseudo_id, 0, row, font_size=10,
                             font=pu.EFieldFont.HMADURAI))
                row += 1

            schema.add_cell(
                pu.Field(slide.pseudo_id, 0, row, font_size=18, font=pu.EFieldFont.SEGOEBL))
            row += 1

            if slide.name is not None:
                schema.add_cell(pu.Field(slide.pseudo_name, 0, row, font_size=18))
                row += 1
            if slide.stain is not None:
                schema.add_cell(pu.Field(slide.stain, 0, row, font_size=18))
                row += 1
            if slide.tissue is not None:
                schema.add_cell(pu.Field(slide.tissue, 0, row, font_size=18))
                row += 1

            barcode_val = f"{slide.pseudo_id}"

            if slide.acquired_at is not None:
                year = slide.pseudo_acquired_at.year
                barcode_val = f"{year}-{barcode_val}"

            if slide.stain is not None:
                barcode_val = f"{barcode_val}-{slide.stain}"

            if slide.tissue is not None:
                barcode_val = f"{barcode_val}-{slide.tissue}"

            schema.add_cell(
                pu.Field(barcode_val, 0, row,
                         type=pu.EFieldType.PDF417, code_size=250, align=pu.EFieldAlign.CENTER))
            row += 1

            if slide.acquired_at is not None:
                schema.add_cell(
                    pu.Field(slide.pseudo_acquired_at.strftime(DATETIME_FORMAT), 0, row,
                             font_size=15))

            # create pseudonym-label
            pseudo_label = pu.create_pseudo_label(label.width, label.height, schema)

            return pseudo_label
        except Exception as e:
            raise Exception(f"Can not create pseudonym: {str(e)}") from None

    def save_image_data_to_store(self, sub_image: Slide.SubImage, store_folder, prefix_error=""):
        """
            Save an associated image data to store
            :param sub_image: image data
            :param store_folder: store folder path
            :param prefix_error: prefix message
            :return: path of label in the store, name, encrypt key
        """
        try:
            # get image data
            # we need following data to back up later
            data = {
                     "data_byte_counts": sub_image.data_byte_counts,
                     "data_offsets": sub_image.data_offsets,
                     "compression": sub_image.compression,
                     "data": list(sub_image.get_image_data())
                    }

            data = json.dumps(data).encode('utf-8')

            # create key
            encrypted_img_key = Fernet.generate_key()

            # create encrypt generator
            fernet = Fernet(encrypted_img_key)

            # encrypt data
            encrypted_img_bytes = fernet.encrypt(data)

            # generate a path of image in the store
            encrypted_img_name, encrypted_img_path = create_file_path_in_store(store_folder)

            # write encrypted data to store
            with open(encrypted_img_path, "wb") as lif:
                lif.write(encrypted_img_bytes)

            return encrypted_img_path, encrypted_img_name, encrypted_img_key
        except Exception as e:
            raise Exception(f"{prefix_error}Can not save encrypted label in store: {str(e)}") from None

    def get_image_data_in_store(self, key, pseudo_image_data_name, store_folder, prefix_error=""):
        """
            Decrypt an associated image data in store
            :param key: key to decrypt
            :param pseudo_image_data_name: name of file in store
            :param store_folder: store folder path
            :param prefix_error: prefix message
            :return: path of label in the store, name, encrypt key
        """
        try:
            # get path of encrypted data in the store
            encrypted_image_path = store_folder.joinpath(pseudo_image_data_name, '')

            # check exist path
            if os.path.exists(encrypted_image_path) is False:
                raise Exception(f"{prefix_error}Can not find the label in store")

            # get image data of encrypted label
            with open(encrypted_image_path, "rb") as lif:
                data = lif.read()

            fernet = Fernet(key)
            try:
                # decrypt data to get origin data
                decrypted_data = fernet.decrypt(data)
                decrypted_data = json.loads(decrypted_data.decode('utf-8'))
                decrypted_data["data"] = bytes(decrypted_data["data"])
                return decrypted_data
            except InvalidToken:
                raise Exception("Key is invalid")

        except Exception as e:
            raise Exception(f"{prefix_error}Can not decrypt image in store: {str(e)}") from None

    def save_metadata_to_store(self, file_path, key, metadata, prefix_error=""):
        """
            Save an associated image data to store
            :param file_path: file path in the store
            :param key: key to encrypt
            :param metadata: image metadata
            :param prefix_error: prefix message
            :return: path of file in the store, filename, encrypt key
        """
        try:
            # get image data
            # we need following data to back up later
            data = json.dumps(metadata).encode('utf-8')

            # create encrypt generator
            fernet = Fernet(key)

            # encrypt data
            encrypted_bytes = fernet.encrypt(data)

            # generate a path in the store

            # write encrypted data to store
            with open(file_path, "wb") as lif:
                lif.write(encrypted_bytes)

            return True
        except Exception as e:
            raise Exception(f"{prefix_error}Can not save metadata in store: {str(e)}") from None

        return False

    def get_metadata_in_store(self, key, filename, store_folder, prefix_error=""):
        """
            Decrypt an associated image data in store
            :param key: key to decrypt
            :param filename: name of file in store
            :param store_folder: store folder path
            :param prefix_error: prefix message
            :return: path of label in the store, name, encrypt key
        """
        try:
            # get path of encrypted data in the store
            encrypted_path = store_folder.joinpath(filename, '')

            # check exist path
            if os.path.exists(encrypted_path) is False:
                raise Exception(f"{prefix_error}Can not find metadata in store")

            # get image data of encrypted label
            with open(encrypted_path, "rb") as lif:
                data = lif.read()

            fernet = Fernet(key)
            try:
                # decrypt data to get origin data
                decrypted_data = fernet.decrypt(data)
                decrypted_data = json.loads(decrypted_data.decode('utf-8'))
                return decrypted_data
            except InvalidToken:
                raise Exception("Key is invalid")

        except Exception as e:
            raise Exception(f"{prefix_error}Can not decrypt data in store: {str(e)}") from None

    def generate_metadata_svs(self, file_path, new_data, prefix_error=""):
        """
        generate metadata for each IFD in an Aperio file
        :param file_path: path of file
        :param new_data: new data of metadata contains fields that need to be replaced
        :param prefix_error: prefix of message/error
        :return: original metadata, new metadata
        """
        # read file
        tif = tifffile.TiffFile(file_path)

        # origin metadata to save for backup
        origin_data = []

        # new metadata
        new_metadata = []

        try:
            # read each image file directory to find metadata in the description tag
            for page in tif.pages:

                # get description of idf
                description = page.description

                if description is not None:
                    have_data = False  # does the idf have identifier in metadata?
                    for key in new_data.keys():
                        if key in description:
                            have_data = True
                            break

                    if have_data is False:
                        continue

                    # if identifier was found
                    data = description.split("|")

                    # contains index of metadata-info will be deleted because of no corresponding value
                    removing_index = []

                    for idx, info in enumerate(data):
                        separator = "="
                        if separator in info:
                            if " = " in info:
                                separator = " = "

                            key_val = info.split(separator)

                            if len(key_val) == 2:
                                key, val = key_val[0], key_val[1]

                                if key in new_data:
                                    if new_data[key] is None:
                                        # value is None => will be deleted
                                        removing_index.append(idx)
                                    else:
                                        data[idx] = f"{key}{separator}{new_data[key]}"

                    # remove unnecessary info in metadata
                    data = np.delete(data, removing_index)

                    # create new metadata
                    new_description = "|".join(data)
                    new_metadata.append((page.index, new_description))

                    # save origin metadata
                    description_tag = page.tags.get(270)
                    origin_data.append({
                        "page_index": page.index,
                        "shape": page.shape,
                        "count": description_tag.count,
                        "value_offset": description_tag.valueoffset,
                        "value": description_tag.value,  # description
                    })

        except Exception as e:
            print(str(e))
            raise Exception(f"{prefix_error}Can not generate new metadata") from None
        finally:
            tif.close()

        return origin_data, new_metadata

    def replace_metadata_svs(self, file_path, new_data, prefix_error=""):
        """
        replace metadata for each IFD in an Aperio file
        :param file_path: path of file
        :param new_data: new data of metadata contains fields that need to be replaced
        :param prefix_error: prefix of message/error
        :return: original metadata
        """
        # read file
        tif = tifffile.TiffFile(file_path)

        try:
            # generate new metadata for each IFD and save the original metadata for de-pseudonymization
            origin_data, new_metadata = self.generate_metadata_svs(file_path, new_data, prefix_error)

            # replace in file
            with open(file_path, "r+b") as f:
                # get endian order of bytes
                big_endian = True if f.read(2) == b"MM" else False  # b"II" is litle-endian
                for idx, metadata in new_metadata:
                    page = tif.pages[idx]
                    description_tag = page.tags.get(270)
                    # write length of new metadata to file
                    f.seek(description_tag.offset + 4)  # offset + 4 to move to length-offset
                    f.write(cu.int_to_bytes(len(metadata), length=4, is_big_endian=big_endian))

                    if len(page.description) > len(metadata):
                        # pad new metadata to a fixed length of old metadata with spaces
                        # this helps wipe all original data too
                        metadata = metadata.ljust(description_tag.count)

                        # write data
                        f.seek(description_tag.valueoffset)
                        f.write(metadata.encode())
                    else:
                        # the memory space of the original description data is not enough for pseudonymous data
                        # therefore, the new metadata will be written in end of the file
                        # and the original data will be removed out the file also
                        f.seek(description_tag.valueoffset)
                        f.write("".ljust(description_tag.count).encode())

                        f.seek(0, 2)  # go to eof to avoid conflict

                        offset = f.tell()   # save value offset

                        # write new metadata to the file
                        f.write(metadata.encode())

                        # write new value offset
                        f.seek(description_tag.offset + 8)  # offset + 8 to move to value-offset
                        f.write(cu.int_to_bytes(offset, length=4, is_big_endian=big_endian))

                    f.flush()

        except Exception as e:
            print(str(e))
            raise Exception(f"{prefix_error}Can not replace metadata") from None
        finally:
            tif.close()

        return origin_data

    def back_up_metadata_svs(self, file_path, origin_metadata_data, prefix_error=""):
        """
        back up original metadata for an Aperio file
        :param file_path: path of file
        :param origin_metadata_data: original metadata
        :param prefix_error: prefix of message/error
        :return: No return
        """
        required_keys = ["page_index", "shape", "count", "value_offset", "value"]

        for origin_metadata in origin_metadata_data:
            for key in required_keys:
                if key not in origin_metadata:
                    raise Exception(f"{prefix_error}{key} is not found")

        # check exist path
        if os.path.exists(file_path) is False:
            raise Exception(f"{prefix_error}Can not find the file in store")

        # read file
        tif = tifffile.TiffFile(file_path)

        # replace in file
        try:
            with open(file_path, "r+b") as f:
                # get endian order of bytes
                big_endian = True if f.read(2) == b"MM" else False  # b"II" is litle-endian
                for metadata in origin_metadata_data:
                    page = tif.pages[metadata["page_index"]]

                    if page.shape != tuple(metadata["shape"]):
                        raise Exception("Shape image does not match")

                    description_tag = page.tags.get(270)

                    # wipe pseudo metadata
                    f.seek(description_tag.valueoffset)
                    f.write("".ljust(description_tag.count).encode())

                    # write length of metadata to file
                    f.seek(description_tag.offset + 4)  # offset + 4 to move to length-offset
                    f.write(cu.int_to_bytes(metadata["count"], length=4, is_big_endian=big_endian))

                    # write new value offset
                    f.write(cu.int_to_bytes(metadata["value_offset"], length=4, is_big_endian=big_endian))

                    # write data
                    f.seek(metadata["value_offset"])
                    f.write(metadata["value"].encode())

                    f.flush()
        except Exception as e:
            print(str(e))
            raise Exception(f"{prefix_error}Can not replace metadata") from None
        finally:
            tif.close()

    async def perform_single_wsi(self, dest_folder=None) -> list:
        """
            perform pseudonymisation for a single slide (WSI)
            :parameter:
                dest_folder: path of folder the output pseudo-file will be saved
            :return:
                pseudo-data JSON
        """

        # validate input
        error_msg = self.check_valid_before_pseudonym(InputType.SINGLE_WSI)

        if error_msg is not None:
            print(error_msg)
            return None

        # validate store folder path
        store_folder = self.check_store_path()
        if store_folder is None:
            return None

        # validate destination folder path
        if dest_folder is not None:
            dest_folder = Path(dest_folder)
            if not os.path.isdir(dest_folder):
                print("Destination path must be a directory")
                return None

        copied_clone_flag = False
        saved_encrypted_label_flag = False
        saved_encrypted_metadata_flag = False

        # check vendor of the slide
        match self.pseudo_data.vendor:
            case Vendor.APERIO:
                encrypted_label_path = None
                try:
                    slide_data = self.pseudo_data.slide_data

                    # label image
                    label = slide_data.label
                    # macro = slide_data.macro

                    if label is None:
                        print(f"Can not find the label of the Slide")
                        return None

                    # copy clone of slide
                    pseudo_file_path = self.copy_clone(self.pseudo_data, dest_folder)

                    copied_clone_flag = True
                    self.pseudo_data.pseudo_file_path = pseudo_file_path

                    # create pseudonym
                    pseudo_label = self.create_pseudonym(self.pseudo_data)

                    try:
                        # replace pseudonym with label
                        rs = pu.replace_label_with_pseudonym_svs(pseudo_file_path, pseudo_label, label.ifd)
                        if rs is False:  # failed
                            raise Exception("Can not replace pseudonym with label")
                    except Exception as e:
                        raise Exception(f"Can not replace label with pseudo-label: {str(e)}") from None

                    # create pseudo-json
                    rs_json = self.create_json(InputType.SINGLE_WSI, self.pseudo_data,
                                               self.input_data.basic_json)

                    # failed during creating json
                    if rs_json is None:
                        raise Exception("Something wrong, can not create data of JSON")

                    # create pseudo metadata
                    pseudo_metadata = {"Filename": self.pseudo_data.pseudo_id,
                                       "Title": self.pseudo_data.pseudo_id,
                                       "Date": None, "Time": None,  "Time Zone": None, "User": None}

                    # replace metadata with pseudo metadata
                    origin_metadata = self.replace_metadata_svs(pseudo_file_path, pseudo_metadata)

                    # if pseudo-data is not retrieved from DB
                    # it means that new pseudo-data has just been created
                    # therefore, this data has to be added to the store and database also
                    if self.pseudo_data.get_from_database is False:

                        # create key to encrypt metadata
                        encrypt_meta_key = Fernet.generate_key()

                        # generate a path in the store
                        encrypt_meta_name, encrypt_meta_path = create_file_path_in_store(store_folder)

                        # save metadata to store
                        saved_encrypted_metadata_flag = self.save_metadata_to_store(encrypt_meta_path,
                                                                                    encrypt_meta_key,
                                                                                    origin_metadata)
                        if saved_encrypted_metadata_flag is False:
                            raise Exception("Can not save metadata in the store")

                        # save label to store
                        rs_saved_to_store = self.save_image_data_to_store(label, store_folder)
                        encrypted_label_path, encrypted_label_name, encrypted_label_key = rs_saved_to_store
                        print("Saved label in store")

                        # successful flag
                        saved_encrypted_label_flag = True

                        # save data to database

                        # create db slide
                        wsi = model.WSI()
                        wsi.id = self.pseudo_data.id
                        wsi.name = self.pseudo_data.name
                        wsi.acquired_at = self.pseudo_data.acquired_at
                        wsi.stain = self.pseudo_data.stain
                        wsi.tissue = self.pseudo_data.tissue
                        wsi.pseudo_id = self.pseudo_data.pseudo_id
                        wsi.pseudo_name = self.pseudo_data.pseudo_name
                        wsi.pseudo_acquired_at = self.pseudo_data.pseudo_acquired_at
                        wsi.pseudo_metadata_name = encrypt_meta_name
                        wsi.pseudo_metadata_key = encrypt_meta_key
                        wsi.pseudo_label_name = encrypted_label_name
                        wsi.pseudo_label_key = encrypted_label_key

                        # save db slide to DB
                        async with model.Session() as session:
                            try:
                                async with session.begin():
                                    wsiDAO = db.WSIDAO(session, auto_commit=False)
                                    if await wsiDAO.create(wsi) is False:
                                        raise Exception(
                                            "Something wrong during creating WSI in DB") from None

                                    await wsiDAO.commit()
                                    print("Saved data in DB")
                            except Exception as ex:
                                session.rollback()
                                print(str(ex))
                                raise Exception("Can not save data in DB") from None

                    elif len(self.pseudo_data.need_to_be_updated) > 0:
                        # if there is some information different from data in the DB, it will be updated
                        async with model.Session() as session:
                            try:
                                async with session.begin():
                                    wsiDAO = db.WSIDAO(session, auto_commit=False)
                                    wsi = await wsiDAO.get(self.pseudo_data.id)
                                    for attr in self.pseudo_data.need_to_be_updated:
                                        setattr(wsi, attr, getattr(self.pseudo_data, attr))
                                    await session.commit()
                                    print("Saved data in DB")
                            except Exception as ex:
                                await session.rollback()
                                print(str(ex))
                                raise Exception("Can not save data in DB") from None
                    return rs_json
                except Exception as ex:
                    print(str(ex))
                    print("Rollback....")

                    # remove clone file
                    if copied_clone_flag:
                        Path(pseudo_file_path).unlink()

                    # remove metadata file
                    if saved_encrypted_metadata_flag:
                        Path(encrypt_meta_path).unlink()

                    # remove encrypted label in the store
                    if saved_encrypted_label_flag:
                        Path(encrypted_label_path).unlink()
                pass
            # case Vendor.HAMAMATSU:
            # case Vendor.MIRAX:
            # case Vendor.UNKNOWN:
            case _:
                print(f"Vendor of Slide is still not supported!")
                pass

        return None

    async def perform_de_single_wsi(self, dest_folder=None) -> list:
        """
            perform de-pseudonymisation for a single slide (WSI)
            :parameter:
                dest_folder: path of folder the output clone file will be saved
            :return:
                origin-data JSON
        """
        # validate input
        error_msg = self.check_valid_before_de_pseudonym(InputType.SINGLE_WSI)

        if error_msg is not None:
            print(error_msg)
            return None

        # validate store folder path
        store_folder = self.check_store_path()
        if store_folder is None:
            return None

        # validate destination folder path
        if dest_folder is not None:
            dest_folder = Path(dest_folder)

            if not os.path.isdir(dest_folder):
                print("Destination path must be a directory")
                return None

        # flag to check whether clone file has already copied or not
        copied_clone_flag = False

        # check vendor of the slide
        match self.pseudo_data.vendor:
            case Vendor.APERIO:
                slide_data = self.pseudo_data.slide_data

                # get label image
                label = slide_data.label

                if label is None:
                    print("Can not find the label of the Slide")
                    return None
                try:
                    # decrypt label to get origin label
                    decrypted_label_data = self.get_image_data_in_store(self.pseudo_data.pseudo_label_key,
                                                                        self.pseudo_data.pseudo_label_name,
                                                                        store_folder)

                    # copy clone
                    origin_file_path = self.copy_clone(self.pseudo_data, dest_folder)

                    copied_clone_flag = True
                    self.pseudo_data.path = origin_file_path

                    # restore metadata
                    metadata_in_store = self.get_metadata_in_store(self.pseudo_data.pseudo_metadata_key,
                                                                   self.pseudo_data.pseudo_metadata_name,
                                                                   store_folder)

                    self.back_up_metadata_svs(origin_file_path, metadata_in_store)

                    try:
                        # replace pseudonym with origin label
                        rs = pu.back_up_image_svs(self.pseudo_data.path, decrypted_label_data, label.ifd)

                        if rs is False:  # failed
                            raise Exception("Can not write label to pseudo-file")
                    except Exception as e:
                        raise Exception(f"Can not replace pseudo-label with label: {str(e)}") from None

                    # create json
                    rs_json = self.create_json(InputType.SINGLE_WSI, self.pseudo_data, self.input_data.basic_json)

                    if rs_json is None:
                        raise Exception("Something wrong, can not write JSON")

                    return rs_json
                except Exception as ex:
                    print(str(ex))
                    print("Rollback....")

                    # remove clone file
                    if copied_clone_flag:
                        Path(origin_file_path).unlink()

                pass
            # case Vendor.HAMAMATSU:
            # case Vendor.MIRAX:
            # case Vendor.UNKNOWN:
            case _:
                print(f"Vendor of Slide is still not supported!")
                pass

        return None

    async def perform_case(self, dest_folder=None) -> list:
        """
            perform pseudonymisation for a Case
            :parameter:
                dest_folder: path of folder the output clone file will be saved
            :return:
                pseudo-data JSON
        """
        # validate input
        error_msg = self.check_valid_before_pseudonym(InputType.CASE)

        if error_msg is not None:
            print(error_msg)
            return None

        # validate store folder path
        store_folder = self.check_store_path()
        if store_folder is None:
            return None

        # validate destination folder path
        if dest_folder is not None:
            dest_folder = Path(dest_folder)
            if not os.path.isdir(dest_folder):
                print("Destination path must be a directory")
                return None

        clone_paths = []  # slide's clone paths
        file_in_store_paths = []  # encrypted images paths in the store
        metadata_in_store_paths = []  # encrypted metadata paths in the store
        db_wsis = []  # list of slide will be inserted to DB
        db_update_wsis = []  # list of slide will be updated in DB
        try:
            # read data of each slide
            for idx, slide in enumerate(self.pseudo_data.slides):

                # prefix of each message
                prefix_message = f"Slide[id = {slide.id}]: "

                match slide.vendor:
                    case Vendor.APERIO:

                        # get label
                        label = slide.slide_data.label

                        if label is None:
                            print(f"{prefix_message}Can not find the label of the Slide")
                            continue

                        # copy clone of slide
                        pseudo_file_path = self.copy_clone(slide, dest_folder, prefix_error=prefix_message)

                        clone_paths.append(pseudo_file_path)
                        self.pseudo_data.slides[idx].pseudo_file_path = pseudo_file_path

                        # create pseudonym
                        pseudo_label = self.create_pseudonym(slide, case=self.pseudo_data, prefix_error=prefix_message)

                        try:
                            # replace pseudonym with label
                            rs = pu.replace_label_with_pseudonym_svs(pseudo_file_path, pseudo_label, label.ifd)
                            if rs is False:  # failed
                                raise Exception("Can not replace pseudonym with label")
                        except Exception as e:
                            raise Exception(f"{prefix_message}Can not replace label with "
                                            f"pseudo-label: {str(e)}") from None

                        # create pseudo metadata
                        pseudo_metadata = {"Filename": slide.pseudo_id,
                                           "Title": slide.pseudo_id,
                                           "Date": None, "Time": None, "Time Zone": None, "User": None}

                        # replace metadata with pseudo metadata
                        origin_metadata = self.replace_metadata_svs(pseudo_file_path, pseudo_metadata)

                        # if pseudo-data of the slide is not retrieved from DB
                        # it means that new pseudo-data has just been created
                        # therefore, this data has to be added to the store and database also
                        if slide.get_from_database is False:

                            # create key to encrypt metadata
                            encrypt_meta_key = Fernet.generate_key()

                            # generate a path in the store
                            encrypt_meta_name, encrypt_meta_path = create_file_path_in_store(store_folder)

                            # save metadata to store
                            saved_rs = self.save_metadata_to_store(encrypt_meta_path,
                                                                   encrypt_meta_key,
                                                                   origin_metadata)

                            metadata_in_store_paths.append(encrypt_meta_path)

                            if saved_rs is False:
                                raise Exception(f"{prefix_message}Can not save metadata in the store")

                            # save label to store
                            rs_saved = self.save_image_data_to_store(label, store_folder, prefix_error=prefix_message)

                            encrypted_label_path, encrypted_label_name, encrypted_label_key = rs_saved
                            print(f"{prefix_message}Saved label in store")

                            # add path to list of path in store,
                            # when something wrong appears, all files in this list will be removed
                            file_in_store_paths.append(encrypted_label_path)

                            # create database-slide
                            wsi = model.WSI()
                            wsi.id = slide.id
                            wsi.name = slide.name
                            wsi.acquired_at = slide.acquired_at
                            wsi.stain = slide.stain
                            wsi.tissue = slide.tissue
                            wsi.pseudo_id = slide.pseudo_id
                            wsi.pseudo_name = slide.pseudo_name
                            wsi.pseudo_acquired_at = slide.pseudo_acquired_at
                            wsi.pseudo_metadata_name = encrypt_meta_name
                            wsi.pseudo_metadata_key = encrypt_meta_key
                            wsi.pseudo_label_name = encrypted_label_name
                            wsi.pseudo_label_key = encrypted_label_key

                            db_wsis.append(wsi)
                        elif slide.need_to_be_updated:
                            db_update_wsis.append(slide)

                    # case Vendor.HAMAMATSU:
                    # case Vendor.MIRAX:
                    # case Vendor.UNKNOWN:
                    case _:
                        print(f"{prefix_message}Vendor of Slide is still not supported!")
                        continue

            # create json
            rs_json = self.create_json(InputType.CASE, self.pseudo_data, self.input_data.basic_json)

            if rs_json is None:
                raise Exception("Something wrong, can not create JSON")

            if self.pseudo_data.get_from_database is False \
                or self.pseudo_data.need_to_be_updated \
                    or len(db_wsis) > 0 or len(db_update_wsis) > 0:  # new case or there are slides not in DB

                # save data to database
                try:
                    async with model.Session() as session:
                        async with session.begin():
                            wsiDAO = db.WSIDAO(session, auto_commit=False)
                            caseDAO = db.CaseDAO(session, auto_commit=False)

                            # insert slides to DB
                            if len(db_wsis) > 0:
                                session.add_all(db_wsis)

                            # collect all slides
                            slides = []
                            for slide in self.pseudo_data.slides:
                                if slide.get_from_database or slide.need_to_be_updated:
                                    db_slide = await wsiDAO.get(slide.id)

                                    # update new data if needed
                                    if len(slide.need_to_be_updated) > 0:
                                        for attr in slide.need_to_be_updated:
                                            setattr(db_slide, attr, getattr(slide, attr))

                                    slides.append(db_slide)

                            slides += db_wsis

                            if self.pseudo_data.get_from_database is False:

                                # insert new case
                                db_case = model.Case()
                                db_case.id = self.pseudo_data.id
                                db_case.name = self.pseudo_data.name
                                db_case.created_at = self.pseudo_data.created_at
                                db_case.pseudo_id = self.pseudo_data.pseudo_id
                                db_case.pseudo_name = self.pseudo_data.pseudo_name
                                db_case.pseudo_created_at = self.pseudo_data.pseudo_created_at

                                # assign slides for case
                                db_case.slides = slides

                                # insert patient into DB
                                session.add(db_case)
                            else:

                                # get old case
                                db_case = await caseDAO.get_by_id_with_slides(self.pseudo_data.id)

                                # update new data if needed
                                if len(self.pseudo_data.need_to_be_updated) > 0:
                                    for attr in self.pseudo_data.need_to_be_updated:
                                        setattr(db_case, attr, getattr(self.pseudo_data, attr))

                                # get the current slide list of the case
                                slide_ids = [sl.id for sl in db_case.slides]

                                for slide in slides:

                                    # if slide is not in the slide list of the case
                                    if slide.id not in slide_ids:
                                        # add slide into the list
                                        db_case.slides.append(slide)

                            # save data
                            await session.commit()
                            print("Saved data in DB")
                except Exception as ex:
                    await session.rollback()
                    raise Exception("Can not save data in DB: ", str(ex))

            return rs_json

        except Exception as e:
            print(str(e))
            print("Rollback...")

            # remove clones
            for clone_path in clone_paths:
                Path(clone_path).unlink()

            # remove encrypted images in store
            for file_path in file_in_store_paths:
                Path(file_path).unlink()

            # remove encrypted metadata in store
            for metadata_path in metadata_in_store_paths:
                Path(metadata_path).unlink()

            return None

        return None

    async def perform_de_case(self, dest_folder=None) -> list:
        """
            perform de-pseudonymisation for a Case
            :parameter:
                dest_folder: path of folder the output clone file will be saved
            :return:
                origin-data JSON
        """
        # validate input
        error_msg = self.check_valid_before_de_pseudonym(InputType.CASE)

        if error_msg is not None:
            print(error_msg)
            return None

        # validate store folder path
        store_folder = self.check_store_path()
        if store_folder is None:
            return None

        # validate destination folder path
        if dest_folder is not None:
            dest_folder = Path(dest_folder)

            if not os.path.isdir(dest_folder):
                print("Destination path must be a directory")
                return None

        # slide's clone paths
        clone_paths = []

        try:

            # read each slide
            for idx, slide in enumerate(self.pseudo_data.slides):
                if slide.id is None:  # slide could not be found in the Database
                    continue

                # prefix of each message
                prefix_message = f"Slide[id = {slide.pseudo_id}]: "

                # check vendor of the slide
                match slide.vendor:
                    case Vendor.APERIO:

                        # get label image
                        label = slide.slide_data.label

                        if label is None:
                            print(f"{prefix_message}Can not find the label of the Slide")
                            continue

                        # decrypt label to get origin label
                        decrypted_label_data = self.get_image_data_in_store(slide.pseudo_label_key,
                                                                            slide.pseudo_label_name,
                                                                            store_folder,
                                                                            prefix_error=prefix_message)
                        # copy clone
                        origin_file_path = self.copy_clone(slide, dest_folder, prefix_error=prefix_message)

                        clone_paths.append(origin_file_path)
                        self.pseudo_data.slides[idx].path = origin_file_path

                        # restore metadata
                        metadata_in_store = self.get_metadata_in_store(slide.pseudo_metadata_key,
                                                                       slide.pseudo_metadata_name,
                                                                       store_folder,
                                                                       prefix_error=prefix_message)

                        self.back_up_metadata_svs(origin_file_path, metadata_in_store, prefix_error=prefix_message)

                        try:
                            # replace pseudonym with origin label
                            rs = pu.back_up_image_svs(origin_file_path, decrypted_label_data, label.ifd)

                            if rs is False:  # failed
                                raise Exception("Something wrong")
                        except Exception as e:
                            raise Exception(f"{prefix_message}Can not replace the label of the Slide:"
                                            f" {str(e)}") from None

                    # case Vendor.HAMAMATSU:
                    # case Vendor.MIRAX:
                    # case Vendor.UNKNOWN:
                    case _:
                        print(f"{prefix_message}Vendor of Slide is still not supported!")
                        continue

            # create json
            rs_json = self.create_json(InputType.CASE, self.pseudo_data, self.input_data.basic_json)

            if rs_json is None:
                raise Exception("Something wrong, can not write JSON")

            return rs_json

        except Exception as ex:
            print(str(ex))
            print("Rollback....")

            # remove all clone paths if something wrong
            for file_path in clone_paths:
                Path(file_path).unlink()

        return None

    async def perform_study(self, dest_folder=None) -> list:
        """
            perform pseudonymisation for Study
            :parameter:
                dest_folder: path of folder the output clone file will be saved
            :return:
                pseudo-data JSON
        """
        # validate input
        error_msg = self.check_valid_before_pseudonym(InputType.STUDY)

        if error_msg is not None:
            print(error_msg)
            return None

        # validate store folder path
        store_folder = self.check_store_path()
        if store_folder is None:
            return None

        # validate destination folder path
        if dest_folder is not None:
            dest_folder = Path(dest_folder)
            if not os.path.isdir(dest_folder):
                print("Destination path must be a directory")
                return None

        clone_paths = []  # slide's clone paths
        file_in_store_paths = []  # encrypted images paths in the store
        metadata_in_store_paths = []  # encrypted metadata paths in the store
        patient_slides = []  # list of patient will be inserted to DB
        db_update_wsis = []  # list of slide will be updated in DB

        try:
            # read data of each patient
            for patient_idx, patient in enumerate(self.pseudo_data.patients):

                db_wsis = []  # list of slide will be inserted to DB

                # read data of each slide
                for idx, slide in enumerate(patient.slides):

                    # prefix of each message
                    prefix_message = f"Patient[id = {patient.id}]__Slide[id = {slide.id}]: "

                    match slide.vendor:
                        case Vendor.APERIO:

                            # get label
                            label = slide.slide_data.label

                            if label is None:
                                print(f"{prefix_message}Can not find the label of the Slide")
                                continue

                            # copy clone of slide
                            pseudo_file_path = self.copy_clone(slide, dest_folder, prefix_error=prefix_message)

                            clone_paths.append(pseudo_file_path)
                            self.pseudo_data.patients[patient_idx].slides[idx].pseudo_file_path = pseudo_file_path

                            # create pseudonym
                            pseudo_label = self.create_pseudonym(slide, patient=patient, study=self.pseudo_data,
                                                                 prefix_error=prefix_message)

                            try:
                                # replace origin label with the pseudonym-label
                                rs = pu.replace_label_with_pseudonym_svs(pseudo_file_path, pseudo_label, label.ifd)

                                if rs is False:  # failed
                                    raise Exception("Can not replace pseudonym with label")
                            except Exception as e:
                                raise Exception(f"{prefix_message}Can not replace label with "
                                                f"pseudo-label: {str(e)}") from None

                            # create pseudo metadata
                            pseudo_metadata = {"Filename": slide.pseudo_id,
                                               "Title": slide.pseudo_id,
                                               "Date": None, "Time": None, "Time Zone": None, "User": None}

                            # replace metadata with pseudo metadata
                            origin_metadata = self.replace_metadata_svs(pseudo_file_path, pseudo_metadata)

                            # if pseudo-data of the slide is not retrieved from DB
                            # it means that new pseudo-data has just been created
                            # therefore, this data has to be added to the store and database also
                            if slide.get_from_database is False:

                                # create key to encrypt metadata
                                encrypt_meta_key = Fernet.generate_key()

                                # generate a path in the store
                                encrypt_meta_name, encrypt_meta_path = create_file_path_in_store(store_folder)

                                # save metadata to store
                                saved_rs = self.save_metadata_to_store(encrypt_meta_path,
                                                                       encrypt_meta_key,
                                                                       origin_metadata)

                                metadata_in_store_paths.append(encrypt_meta_path)

                                if saved_rs is False:
                                    raise Exception(f"{prefix_message}Can not save metadata in the store")

                                # save label to store
                                rs_saved = self.save_image_data_to_store(label, store_folder, prefix_error=prefix_message)

                                encrypted_label_path, encrypted_label_name, encrypted_label_key = rs_saved
                                print(f"{prefix_message}Saved label in store")

                                # add path to list of path in store,
                                # when something wrong appears, all files in this list will be removed
                                file_in_store_paths.append(encrypted_label_path)

                                # create database-slide
                                wsi = model.WSI()
                                wsi.id = slide.id
                                wsi.name = slide.name
                                wsi.acquired_at = slide.acquired_at
                                wsi.stain = slide.stain
                                wsi.tissue = slide.tissue
                                wsi.pseudo_id = slide.pseudo_id
                                wsi.pseudo_name = slide.pseudo_name
                                wsi.pseudo_acquired_at = slide.pseudo_acquired_at
                                wsi.pseudo_metadata_name = encrypt_meta_name
                                wsi.pseudo_metadata_key = encrypt_meta_key
                                wsi.pseudo_label_name = encrypted_label_name
                                wsi.pseudo_label_key = encrypted_label_key

                                db_wsis.append(wsi)
                            elif slide.need_to_be_updated:
                                db_update_wsis.append(slide)

                        # case Vendor.HAMAMATSU:
                        # case Vendor.MIRAX:
                        # case Vendor.UNKNOWN:
                        case _:
                            print(f"{prefix_message}Vendor of Slide is still not supported!")
                            continue

                # add patient and its slides
                patient_slides.append((patient, db_wsis))

            # create json
            rs_json = self.create_json(InputType.STUDY, self.pseudo_data, self.input_data.basic_json)

            if rs_json is None:
                raise Exception("Something wrong, can not create JSON")

            try:
                async with model.Session() as session:
                    async with session.begin():
                        wsiDAO = db.WSIDAO(session, auto_commit=False)
                        patientDAO = db.PatientDAO(session, auto_commit=False)
                        studyDAO = db.StudyDAO(session, auto_commit=False)

                        db_patients = []  # using to assign to study.patients
                        for patient, slides in patient_slides:

                            # insert NEW slides to db
                            if len(slides) > 0:
                                session.add_all(slides)

                            # get OLD slides from db
                            for slide in patient.slides:
                                if slide.get_from_database:
                                    db_slide = await wsiDAO.get(slide.id)

                                    # update new data if needed
                                    if len(slide.need_to_be_updated) > 0:
                                        for attr in slide.need_to_be_updated:
                                            setattr(db_slide, attr, getattr(slide, attr))

                                    slides.append(db_slide)

                            if patient.get_from_database is False:
                                # insert new patient
                                db_patient = model.Patient()
                                db_patient.id = patient.id
                                db_patient.name = patient.name
                                db_patient.age = patient.age
                                db_patient.sex = patient.sex.value
                                db_patient.pseudo_id = patient.pseudo_id
                                db_patient.pseudo_name = patient.pseudo_name
                                db_patient.pseudo_age = patient.pseudo_age

                                # assign slides for patient
                                db_patient.slides = slides

                                # insert patient into DB
                                session.add(db_patient)
                            else:
                                # get old patient, if existed already in DB
                                db_patient = await patientDAO.get_by_id_with_slides(patient.id)

                                # update new data if needed
                                if len(patient.need_to_be_updated) > 0:
                                    for attr in patient.need_to_be_updated:
                                        if attr == "sex":
                                            db_patient.sex = patient.sex.value
                                        else:
                                            setattr(db_patient, attr, getattr(patient, attr))

                                # get the current slide list of the patient
                                slide_ids = [sl.id for sl in db_patient.slides]

                                for slide in slides:

                                    # if slide is not in the slide list of the patient
                                    if slide.id not in slide_ids:
                                        # add slide into the list
                                        db_patient.slides.append(slide)

                            db_patients.append(db_patient)

                        # handle study
                        if self.pseudo_data.get_from_database is False:
                            # insert new study
                            db_study = model.Study()
                            db_study.id = self.pseudo_data.id
                            db_study.name = self.pseudo_data.name
                            db_study.date = self.pseudo_data.date
                            db_study.pseudo_id = self.pseudo_data.pseudo_id
                            db_study.pseudo_name = self.pseudo_data.pseudo_name
                            db_study.pseudo_date = self.pseudo_data.pseudo_date

                            # assign patients for study
                            db_study.patients = db_patients

                            # insert study into DB
                            session.add(db_study)
                        else:

                            # get old study
                            db_study = await studyDAO.get_by_id_with_patients(self.pseudo_data.id)

                            # update new data if needed
                            if len(self.pseudo_data.need_to_be_updated) > 0:
                                for attr in self.pseudo_data.need_to_be_updated:
                                    setattr(db_study, attr, getattr(self.pseudo_data, attr))

                            # get the current patient list of the study
                            patient_ids = [pat.id for pat in db_study.patients]

                            for patient in db_patients:

                                # if patient is not in the patient list of the study
                                if patient.id not in patient_ids:
                                    # add patient into the list
                                    db_study.patients.append(patient)

                        # save data
                        await session.commit()
                        print("Saved data in DB")
            except Exception as ex:
                await session.rollback()
                raise Exception("Can not save data in DB: ", str(ex))

            return rs_json

        except Exception as e:
            print(str(e))
            print("Rollback...")

            # remove clones
            for clone_path in clone_paths:
                Path(clone_path).unlink()

            # remove encrypted images in store
            for file_path in file_in_store_paths:
                Path(file_path).unlink()

            # remove encrypted metadata in store
            for metadata_path in metadata_in_store_paths:
                Path(metadata_path).unlink()

            return None

        return None

    async def perform_de_study(self, dest_folder=None) -> list:
        """
            perform de-pseudonymisation for a Study
            :parameter:
                dest_folder: path of folder the output clone file will be saved
            :return:
                origin-data JSON
        """
        # validate input
        error_msg = self.check_valid_before_de_pseudonym(InputType.STUDY)

        if error_msg is not None:
            print(error_msg)
            return None

        # validate store folder path
        store_folder = self.check_store_path()
        if store_folder is None:
            return None

        # validate destination folder path
        if dest_folder is not None:
            dest_folder = Path(dest_folder)

            if not os.path.isdir(dest_folder):
                print("Destination path must be a directory")
                return None

        # slide's clone paths
        clone_paths = []

        try:

            # read each patient
            for patient_idx, patient in enumerate(self.pseudo_data.patients):

                # read each slide of patient
                for idx, slide in enumerate(patient.slides):
                    if slide.id is None:  # slide could not be found in the Database
                        continue

                    # prefix of each message
                    prefix_message = f"Patient[id = {patient.pseudo_id}]__Slide[id = {slide.pseudo_id}]: "

                    match slide.vendor:
                        case Vendor.APERIO:

                            # get label image
                            label = slide.slide_data.label

                            if label is None:
                                print(f"{prefix_message}Can not find the label of the Slide")
                                continue

                            # decrypt label to get origin label
                            decrypted_label_data = self.get_image_data_in_store(slide.pseudo_label_key,
                                                                                slide.pseudo_label_name,
                                                                                store_folder,
                                                                                prefix_error=prefix_message)
                            # copy clone
                            origin_file_path = self.copy_clone(slide, dest_folder, prefix_error=prefix_message)

                            clone_paths.append(origin_file_path)
                            self.pseudo_data.patients[patient_idx].slides[idx].path = origin_file_path

                            # restore metadata
                            metadata_in_store = self.get_metadata_in_store(slide.pseudo_metadata_key,
                                                                           slide.pseudo_metadata_name,
                                                                           store_folder,
                                                                           prefix_error=prefix_message)

                            self.back_up_metadata_svs(origin_file_path, metadata_in_store, prefix_error=prefix_message)

                            try:
                                # replace pseudonym with origin label
                                rs = pu.back_up_image_svs(origin_file_path, decrypted_label_data, label.ifd)

                                if rs is False:  # Replaced label fail
                                    raise Exception("Something wrong")
                            except Exception as e:
                                raise Exception(f"{prefix_message}Can not replace the label of the Slide:"
                                                f" {str(e)}") from None

                        # case Vendor.HAMAMATSU:
                        # case Vendor.MIRAX:
                        # case Vendor.UNKNOWN:
                        case _:
                            print(f"{prefix_message}Vendor of Slide is still not supported!")
                            continue

            # create json
            rs_json = self.create_json(InputType.STUDY, self.pseudo_data, self.input_data.basic_json)

            if rs_json is None:
                raise Exception("Something wrong, can not write JSON")

            return rs_json

        except Exception as ex:
            print(str(ex))
            print("Rollback....")

            # remove all clone paths
            for file_path in clone_paths:
                Path(file_path).unlink()

        return None

    def create_json(self, data_type, json_data, basic_json):
        """
            create json data, depending on the property "is_de_pseudonym" of the Pseudonymisation object,
            the output will be pseudo-data (is_de_pseudonym = False) or origin-data (is_de_pseudonym = True)
            :parameter:
                data_type: WSI; Study; Case (InputType)
                json_data: data of the output json
                basic_json: base json, data of json_data will be filled in this variable
            :return:
                JSON data
        """
        try:
            match data_type:
                case InputType.SINGLE_WSI:

                    # remove property slide_data (contains image data), which is not relevant with the output
                    if "slide_data" in basic_json:
                        basic_json.pop("slide_data")

                    # if pseudonymisation
                    if self.is_de_pseudonym is False:

                        # add data to output json
                        pseudo_json = basic_json
                        pseudo_json["id"] = json_data.pseudo_id
                        pseudo_json["path"] = str(json_data.pseudo_file_path)

                        if "name" in pseudo_json:
                            pseudo_json["name"] = json_data.pseudo_name
                        if "acquired_at" in pseudo_json and json_data.pseudo_acquired_at is not None:
                            pseudo_json["acquired_at"] = json_data.pseudo_acquired_at.strftime(DATETIME_FORMAT)

                        return pseudo_json
                    else:
                        # de-pseudonymisation
                        origin_json = basic_json
                        origin_json["id"] = json_data.id
                        origin_json["path"] = str(json_data.path)

                        if "name" in origin_json:
                            origin_json["name"] = json_data.name
                        if "acquired_at" in origin_json and json_data.acquired_at is not None:
                            origin_json["acquired_at"] = json_data.acquired_at.strftime(DATETIME_FORMAT)

                        return origin_json
                case InputType.CASE:

                    # pseudonymisation
                    if self.is_de_pseudonym is False:

                        # add data of case to output json
                        pseudo_json = basic_json
                        pseudo_json["id"] = json_data.pseudo_id

                        if "name" in pseudo_json:
                            pseudo_json["name"] = json_data.pseudo_name
                        if "created_at" in pseudo_json and json_data.pseudo_created_at is not None:
                            pseudo_json["created_at"] = json_data.pseudo_created_at.strftime(DATETIME_FORMAT)

                        for idx, slide in enumerate(json_data.slides):
                            if slide.id is None:
                                continue

                            # use recursion to add slides information to output json
                            pseudo_json["slides"][idx] = self.create_json(InputType.SINGLE_WSI, slide,
                                                                          pseudo_json["slides"][idx].copy())
                        return pseudo_json
                    else:
                        # de-pseudonymisation
                        # add data of case to output json
                        origin_json = basic_json
                        origin_json["id"] = json_data.id

                        if "name" in origin_json and json_data.name is not None:
                            origin_json["name"] = self.pseudo_data.name
                        if "created_at" in origin_json and json_data.created_at is not None:
                            origin_json["created_at"] = self.pseudo_data.created_at.strftime(DATETIME_FORMAT)

                        for idx, slide in enumerate(json_data.slides):
                            if slide.id is None:
                                continue

                            # use recursion to add slides information to output json
                            origin_json["slides"][idx] = self.create_json(InputType.SINGLE_WSI, slide,
                                                                          origin_json["slides"][idx])

                        return origin_json
                case InputType.STUDY:

                    # pseudonymisation
                    if self.is_de_pseudonym is False:

                        # add data of study to output json
                        pseudo_json = basic_json
                        pseudo_json["id"] = json_data.pseudo_id

                        if "name" in pseudo_json:
                            pseudo_json["name"] = json_data.pseudo_name
                        if "date" in pseudo_json and json_data.pseudo_date is not None:
                            pseudo_json["date"] = json_data.pseudo_date.strftime(DATE_FORMAT)

                        # add data of each patient to output json
                        for pat_idx, patient in enumerate(json_data.patients):
                            json_patient = pseudo_json["patients"][pat_idx]
                            json_patient["id"] = patient.pseudo_id

                            if "name" in json_patient:
                                json_patient["name"] = patient.pseudo_name
                            if "age" in json_patient:
                                json_patient["age"] = patient.pseudo_age

                            for idx, slide in enumerate(patient.slides):
                                if slide.id is None:
                                    continue

                                # use recursion to add slides information to output json
                                json_patient["slides"][idx] = self.create_json(InputType.SINGLE_WSI, slide,
                                                                               json_patient["slides"][idx].copy())

                            pseudo_json["patients"][pat_idx] = json_patient

                        return pseudo_json

                    else:

                        # de-pseudonymisation
                        # add data of study to output json
                        origin_json = basic_json
                        origin_json["id"] = json_data.id

                        if "name" in origin_json:
                            origin_json["name"] = self.pseudo_data.name
                        if "date" in origin_json and json_data.date is not None:
                            origin_json["date"] = json_data.date.strftime(DATE_FORMAT)

                        # add data of each patient to output json
                        for pat_idx, patient in enumerate(json_data.patients):
                            json_patient = origin_json["patients"][pat_idx]
                            json_patient["id"] = patient.id

                            if "name" in json_patient:
                                json_patient["name"] = patient.name
                            if "age" in json_patient:
                                json_patient["age"] = patient.age

                            for idx, slide in enumerate(patient.slides):
                                if slide.id is None:
                                    continue

                                # use recursion to add slides information to output json
                                json_patient["slides"][idx] = self.create_json(InputType.SINGLE_WSI, slide,
                                                                               json_patient["slides"][idx].copy())

                            origin_json["patients"][pat_idx] = json_patient

                        return origin_json
        except Exception as ex:
            print(str(ex))
            raise Exception("Can not create data of JSON") from None

        return None
