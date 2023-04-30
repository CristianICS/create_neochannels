"""____________________________________________________________________________
Script Name:          indices.py
Description:          Formulas to apply spectral indices with gdal calc
                      command to apply in GDAL version "3.1.4"
____________________________________________________________________________"""
import os, re
import json
import subprocess

INDICES_MTDT_PATH = os.path.join(os.path.normpath(__file__), os.pardir, 'indices.json')

def check_bands(img_band_keys: list, index_bands: list) -> bool:
    """
    Test if the index bands are inside image bands.
    """
    for b in index_bands:
        if b not in img_band_keys:
            return False
    return True

def compute_index(index_key, img_path, img_bands_pos, img_bands, out_dir, img_path_120cm = False):
    """
    Write and perform gdal_calc command in cmd to compute a spectral
    index.

    :index_key: Index short name. Must be the same as JSON's key inside index
    metadata is stored.
    :img_path: MUL image path.
    :img_path_120m: MUL image without pansharpening
    :img_bands_pos: Position of image bands linked to img_bands keys.
    :img_bands: Image band keys.
    :out_dir: Directory to store image.
    """

    # Open index metadata's JSON
    indices_mtd = open(INDICES_MTDT_PATH)
    indices_mtd_json = json.load(indices_mtd)

    # Get index parameters
    index_bands = indices_mtd_json[index_key]['bands']
    formula = str(indices_mtd_json[index_key]['formula'])

    if not check_bands(img_bands, index_bands):
        raise ValueError(f'Index required band is not inside the image.')

    # Get the src where gdal tool is located
    module = os.path.abspath(os.path.join(__file__, os.pardir))
    # Write GDAL command to compute the index
    gdal_calc = [f'python "{module}/gdal_calc.py" --quiet']

    # 1. Switch bands keys in index's formula with abecedary letters (by band order)
    abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    modified_formula = formula
    gdal_bands_src = []
    gdal_bands_n = []
    for i in range(0, len(index_bands)):
        b = index_bands[i]
        gdal_band = abc[i]
        modified_formula = modified_formula.replace(b, gdal_band)

        # 2. Write connection between new gdal letter and image band number
        img_band_n = img_bands_pos[img_bands.index(b)]
        band_src = f'-{gdal_band} "{img_path}"'
        band_n = f'--{gdal_band}_band={img_band_n}'
        gdal_bands_src.append(band_src)
        gdal_bands_n.append(band_n)

    # Output image
    img_name = os.path.basename(img_path).split('.')[0]
    out_path = os.path.join(out_dir, img_name + '_30cm_' + index_key + '.tif')

    gdal_calc.append(f'--calc="{modified_formula}"')
    gdal_calc.append(" ".join(gdal_bands_n))
    gdal_calc.append(" ".join(gdal_bands_src))
    gdal_calc.append('--co COMPRESS=DEFLATE --co PREDICTOR=3 --overwrite')
    gdal_calc.append(f'--outfile="{out_path}"')
    command = " ".join(gdal_calc)

    # Print info
    print(
        f'\nComputed Index: {index_key}\n' +
        f'--------------\n' +
        f'..Bands: {", ".join(index_bands)}\n' +
        f'..Formula: {formula}\n' +
        f'..Calc formula: {modified_formula}\n' +
        f'..Calc bands: {" ".join(gdal_bands_n)}\n' +
        f'..GDAL command:\n\n{command}'
    )

    output = subprocess.check_output(command, shell=True)

    # Compute Nir IVs twice: with 7 and 8 bands respectively
    if "N" in index_bands and img_path_120cm:
        command_120 = re.sub("_band=7","_band=8", command)
        command_120 = re.sub("_30cm","_120cm", command_120)
        command_120 = re.sub(img_path,img_path_120cm, command_120)
    
        print("\nCompute IV again switching the NIR bands..")
        output = subprocess.check_output(command_120, shell=True)


def compute_all_indices(img_path, img_bands_pos, img_bands, out_dir, img_120cm_path = False, all = True):
    """
    Perform compute_index() for all indice.json keys (all indices).

    :all: If there is no true, all parameter requires a list of iv's index keys
    to compute.
    """

    if all != True:
        idx_metadata_json = all
    else:
        # Open index metadata's JSON
        idx_metadata = open(INDICES_MTDT_PATH)
        idx_metadata_json = json.load(idx_metadata)

    for index_key in idx_metadata_json:

        # Compute all index but if there is one that cannot be performed
        # pass to the next one
        try:
            if img_120cm_path:
                compute_index(index_key, img_path, img_bands_pos, img_bands, out_dir, img_120cm_path)
            else:
                compute_index(index_key, img_path, img_bands_pos, img_bands, out_dir)
        except ValueError:
            err_msg = (
                f"Index {index_key} cannot be computed due to" +
                " the image does not contain some requested bands."
            )
            print("\n\n" + err_msg)
            pass

    idx_metadata.close()
