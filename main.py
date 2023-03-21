import json
from input_handler import InputData
from pseudonymisation import Pseudonymization
import asyncio
import platform

# Windows has a problem with EventLoopPolicy
# It can make an async function "Asyncio Event Loop is Closed" when getting loop
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def pseudonymisation(json_path, debug=True) -> list:
    """ Perform Pseudonymisation
        used to create pseudonyms for WSI files based on 3 structures of 3 objects: Study, Case and single WSI.
        This means that the structure of the JSON object in the input file has to be correct
        and appropriate for each object type.

        :parameter:
            json_path:
                path of JSON input file.
            debug:
                if True, processing messages will be displayed
        :return
            JSON: contains pseudo-data
            None: failed
    """
    try:
        # read json data
        if debug:
            print("Read json input file")
        inputData = InputData(json_path)

        # read error messages during reading the input file
        if inputData.has_errors():
            inputData.print_errors()
            print("Input data is invalid")
            return None

        if debug:
            print("Perform pseudonymisation")

        # create a pseudonymization object to perform pseudonymisation
        pseudo_factory = Pseudonymization(inputData)

        if pseudo_factory is not None:

            # init data + generate pseudo-data
            await pseudo_factory.create()

            if pseudo_factory.pseudo_data is not None:

                # perform pseudonym
                pseudo_json = await pseudo_factory.perform_pseudonym()

                # if successful
                if pseudo_json is not None:
                    print("Done")
                    return pseudo_json

        # pseudonym process has been failed
        print("Failed. Can not perform pseudonym")
    except Exception as e:
        print(str(e))

    return None


async def de_pseudonymisation(json_path, debug=True) -> list:
    """ Perform De-Pseudonymisation
            used to take original data for WSI files from pseudonyms based on 3 structures of 3 objects: Study,
            Case and single WSI. This means that the structure of the JSON object in the input file has to be correct
            and appropriate for each object type.

            :parameter:
                json_path:
                    path of pseudonym JSON input file.
                debug:
                    if True, processing messages will be displayed
            :return
                JSON: contains original-data
                None: failed
        """
    try:
        # read json data
        if debug:
            print("Read input file")

        inputData = InputData(json_path)

        if inputData.has_errors():
            inputData.print_errors()
            print("Input data is invalid")
            return None

        if debug:
            print("Perform de-pseudonymisation")

        # create a de-pseudonymization object to perform de-pseudonymisation
        # (the flag is_de_pseudonym = True ensures creating this object for de-pseudonymization)
        pseudo_factory = Pseudonymization(inputData, is_de_pseudonym=True)

        if pseudo_factory is not None:

            # init data
            await pseudo_factory.create()

            if pseudo_factory.pseudo_data is not None:

                # perform de-pseudonymisation
                pseudo_json = await pseudo_factory.perform_de_pseudonym()

                if pseudo_json is not None:
                    print("Done")
                    return pseudo_json

        print("Failed. Can not perform de-pseudonym")

    except Exception as e:
        print(str(e))

    return None


def write_json_file(destination_path, input_json):

    if input_json is None:
        print("Can not write Json file: Input json data is None")
        return None

    with open(destination_path, "w") as f:
        json.dump(input_json, f, indent=4)


#:::::::::::: SINGLE WSI ::::::::::::::::::::::::
# ======= Peusdonymisation ==========
rs_json = asyncio.run(pseudonymisation("./data/json/input_wsi.json"))
write_json_file("./data/json/input_wsi2.json", rs_json)

# ======= De-Peusdonymisation ==========
# rs_json = asyncio.run(de_pseudonymisation("./data/json/input_wsi2.json"))
# write_json_file("./data/json/input_wsi_origin.json", rs_json)


#:::::::::::: CASE ::::::::::::::::::::::::
# ======= Peusdonymisation ==========
# rs_json = asyncio.run(pseudonymisation("./data/json/input_case.json"))
# write_json_file("./data/json/input_case3.json", rs_json)

# ======= De-Peusdonymisation ==========
# rs_json = asyncio.run(de_pseudonymisation("./data/json/input_case3.json"))
# write_json_file("./data/json/input_case_origin.json", rs_json)


#:::::::::::: STUDY ::::::::::::::::::::::::
# ======= Peusdonymisation ==========
# rs_json = asyncio.run(pseudonymisation("./data/json/input_study.json"))
# write_json_file("./data/json/input_study2.json", rs_json)

# ======= De-Peusdonymisation ==========
# rs_json = asyncio.run(de_pseudonymisation("./data/json/input_study2.json"))
# write_json_file("./data/json/input_study_origin.json", rs_json)
