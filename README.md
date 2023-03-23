# WSI Pseudonymisation - 2022/23

There is the source code of a system for creating pseudonyms for WSI files (Whole Slide Image)

### Current support files
- Aperio SVS Fileformat

### Library
- faker 16.6.0:

```bash
pip install Faker
```

- nanoid 2.0 :
```bash
pip install nanoid
```

- numpy 1.24.2:
```bash
pip install numpy
```

- tifffile 2023.3.15:
```bash
pip install tifffile
```

- opencv2 4.7.0.72:
     + Windows: ```pip install opencv-python ```
     + Ubuntu: ```https://docs.opencv.org/3.4/d2/de6/tutorial_py_setup_in_ubuntu.html```

- zlib 1.2.13
- imagecodecs 2023.1.23:
```bash
pip install imagecodecs
```

- sqlalchemy 1.4.46:
```bash
pip install sqlalchemy
pip install mysqlclient
pip install sqlalchemy_utils
```

- jsonschema 4.17.3 :
```bash
pip install jsonschema
```

- pylibdmtx 0.1.10 :
```bash
pip install pylibdmtx
```
- Pillow 9.1.0 :
```bash
pip install pillow
```

- Asyncmy:
```bash
pip install asyncmy
```

### Where can we find WSI-files to test:

#### Aperio 
+ https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/
+ http://haeckel.case.edu:8080/gallery 

### Getting started


1. configure database in db/config.py

2. Execute db_generator.py to generate the database.

If there is an error "Exception during deleting the database: The database does not exist," then run db_generator.py again, please.

3. Edit JSON-input at data/json/input_"object name"

4. Go to main.py to perform functions:

Note: Because there are synchronized functions, just uncomment the one you want to run.

5. The output files will be in the same folder as the input files.


### Quickstart

- Perform Pseudonymisation for a Slide (WSI):
+ `input_wsi.json`
 ```json
  {
      "id": "0001",
      "name": "Fall/Studienname_1",
      "acquired_at": "10:43AM 21.02.2022",
      "stain": "Ki67",
      "tissue": "bone marrow",
      "path": ".\\CMU-1.svs"
  }
 ```
+ run:  using the `pseudonymisation` method
```bash
  import asyncio
  asyncio.run(pseudonymisation("input_wsi.json"))
  write_json_file("output_wsi.json", rs_json)
```
 + `output_wsi.json`
 ```json
{
    "id": "TklrinZ6s6usU",
    "name": "wsi_TklrinZ6s6usU",
    "acquired_at": "08:16AM 21.05.2019",
    "stain": "Ki67",
    "tissue": "bone marrow",
    "path": ".\\TklrinZ6s6usU.svs"
}
 ```

 - Perform De-Pseudonymisation for a Slide (WSI):
 + run: using the `de_pseudonymisation` method
```bash
  import asyncio
  asyncio.run(de_pseudonymisation("output_wsi.json"))
  write_json_file("origin_wsi.json", rs_json)
```
+ `origin_wsi.json`
 ```json
  {
      "id": "0001",
      "name": "Fall/Studienname_1",
      "acquired_at": "10:43AM 21.02.2022",
      "stain": "Ki67",
      "tissue": "bone marrow",
      "path": ".\\CMU-1.svs"
  }
 ```

 for Study and Case are the same
### Author

Truong An Nguyen:
Truong.Nguyen@Student.HTW-Berlin.de
