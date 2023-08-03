# WSI Pseudonymisation - 2022/23

There is the source code of a system for creating pseudonyms for WSI files (Whole Slide Image)

### Current support files
- Aperio SVS Fileformat

### Installation
#### Using Pip
```pip install -r requirements.txt ```

#### Using Docker


### Where can we find WSI-files to test:


## Aperio 
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
