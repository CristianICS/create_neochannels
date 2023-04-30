# Create neochannels to detect cropmarks

The workflow is divided in two parts:

1. Process WV3 images
2. Apply the script to compute neochannels

Both parts are applied with two python scripts. The recomended way to use them is
with [miniconda](https://docs.conda.io/en/latest/miniconda.html)

First create an environment with conda console.

1. Open *Anaconda Prompt (miniconda3)*.
2. Create an *environment*:
    ```
    conda create -n env_name python=3.9
    ```
    - *Some Google Earth Engine API functions only work with python 9.* 
3. Activate the above environment with `conda activate env_name`.

Then install the required modules:

1. GDAL: `conda install -c conda-forge gdal`
2. Earthengine:
    - [Create a Google Cloud project](https://developers.google.com/earth-engine/earthengine_cloud_project_setup#create-a-cloud-project)
    - [Create a service account](https://developers.google.com/earth-engine/guides/service_account#create-a-service-account)
    - [Create a service account](https://developers.google.com/earth-engine/guides/service_account#create-a-private-key-for-the-service-account)
    **in JSON format**.
    - [Install earthengine package](https://anaconda.org/conda-forge/earthengine-api/labels)
    `conda install -c conda-forge earthengine-api=0.1.320`. *Note: A prior version
    is installed due to error in the last one.*
3. Py6S: `conda install -c conda-forge py6s`
4. Dask: `conda install -c conda-forge dask`
5. Scipy: `conda install -c conda-forge scipy`

Lastly, open the desired script inside a text editor and change the input
parameters (variables in uppercase). Then run the script inside conda console:
`python path/to/script/script_name.py`

## Process WV3 images

It's mandatory that images are stored in the predefined directorytree:

```
+---image_id
|   +---img_id_MUL (multispectral image)
|   +---img_id_PAN (panchromatic image)
|   \---GIS_FILES (AOI)
```

Open the script `01_process_wv3.py` in a text editor. Change the lines below:

```py
# WV3 images path (folder with the images inside)
MUL_PATH = "absolute/path/to/the/mul_image/folder/015105921010_01_P001_MUL"
PAN_PATH = "absolute/path/to/the/pan_image/folder/015105921010_01_P001_PAN"

# GEOJSON feature to clip the above images (optional)
AOI_PATH = "absolute/path/aois/aoi_zar_tepe.geojson"

# Google Earth Engine API private key json
CREDENTIALS = "absolute_path/earthengine-private-key.json"
# client_email inside private key JSON
SERVICE_ACCOUNT = "id-s-example@correction.account.com" 
```

Then run the script inside conda prompt:

```
(env_name) disc/User > python absolute_path/to_the_script/01_process_wv3.py
```

The new processed images will be stored inside `original_image_folder/processed_data`.

## Neochannels

1. Spectral indices: Compute the spectral indices inside `indices.json`. If an
index uses NIR band, it will be computed with B7 (31cm from Pansharpened band)
and B8 (120cm from atmospherically corrected band without Pansharpening).
2. Principal components: Each image is named with the combination's id which
identifies the bands with this PCA has been computed. The image has the three
principal componentes with more explained variancia. The first component is
located in the first band and so on.
3. High Pass Filter from CORONA images

Open the script `02_neochannels.py` in a text editor. Change the lines below:

```py
# WV3 images path (folder with the images inside)
WV3_MUL = "absolute_path/processed_data/image-id_6S.tif"
WV3_PSH = "absolute_path/processed_data/image-id_wBrovey.tif"

# Georreferenced CORONA image
CORONA = "absolute_path/D3C1207-100019A030.tif"
```

## Further developments

1. Encapsulate all the modules inside a Docker container and create a jupyter
notebook with a good user interface.
2. Increase customization (e.g. allow High Pass matrix creation)
