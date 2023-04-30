"""____________________________________________________________________________
Script Name:        customfunctions.py
Description:        Functions to handle different actions inside precessing_wv3
                    jupyter notebook script.
Requirements:       GDAL version >= "3.1.4"
____________________________________________________________________________"""
import os
import re
import csv
from datetime import datetime
import string
import subprocess
from Py6S import * # 6S python module

# Earth engine modules
import ee
from google.auth import compute_engine
from atmospheric import Atmospheric
# https://github.com/google/earthengine-api/issues/181#issue-1194580090
import collections

RADIOMETRIC_USE = "D:/arqueologia-proceso-copiaseguridad/codigo-zenodo/wv3-radiometric-use.csv"

def translate(resx, resy, input_path, output_path):

    """
    Use gdal_translate to convert image from TIL to TIF
    extension.

    :resx: Number of pixels in X axis
    :resy: Number of pixels in Y axis
    :input_path: Input image src
    :output_path: Output image src
    """

    gdal_translate = [
        'gdal_translate',
        '-of GTiff',
        '-ot UInt16',
        '-co COMPRESS=DEFLATE -co PREDICTOR=2',
        '-tr {resx} -{resy}',
        '-a_nodata 0 "{img_input}" "{img_output}"'
    ]

    command = ' '.join(gdal_translate).format(
        resx = resx,
        resy = resy,
        img_input = input_path,
        img_output = output_path
    )

    output = subprocess.check_output(command, shell=True)
    return [command, output]

def clip(resx, resy, aoi, input_path, output_path):

    """
    Use gdalwarp tool to clip the image by aoi limits.

    :resx: Number of pixels in X axis
    :resy: Number of pixels in Y axis
    :aoi: geoJSON with polyline to use as clip mask
    :input_path: Input image src
    :output_path: Output image src
    """

    if (not os.path.exists(aoi)):
        errmsg = (
            "ERROR: AOI file in " + aoi + " is not defined.",
            "Check site variable again or the aoi_filenames dict."
        )
        raise ValueError(' '.join(errmsg))        

    gdal_warp = [
        'gdalwarp',
        '-of GTiff',
        '-ot UInt16',
        '-co COMPRESS=DEFLATE -co PREDICTOR=2',
        '-tr {resx} -{resy} -r cubicspline',
        '-overwrite',
        '-dstnodata 0',
        '-cutline "{aoi_src}" -crop_to_cutline',
        '"{img_input}" "{img_output}"'
    ]

    command = ' '.join(gdal_warp).format(
        resx = resx,
        resy = resy,
        aoi_src = aoi,
        img_input = input_path,
        img_output = output_path
    )

    output = subprocess.check_output(command, shell=True)
    return [command, output]

def calc(formulas: str, bands: str, bands_number: str, output_path: str):
    # Get the src where gdal tool is located
    module = os.path.abspath(os.path.join(__file__, os.pardir))
    gdal_calc = [
        f'python "{module}/gdal_calc.py"', # gdal_calc tool src
        '--format=GTiff',
        '--type=Float32 --quiet',
        '--co COMPRESS=DEFLATE --co PREDICTOR=2 --overwrite',
        '--NoDataValue=0 --outfile="{outimg}"'
    ]

    command = ' '.join(gdal_calc + formulas + bands + bands_number)
    command = command.format(outimg=output_path)

    output = subprocess.check_output(command, shell=True)
    return [command, output]

def createDir(root: str, dirname: str):
    """
    Create a new folder inside a directory.

    :root: Directory path inside the new folder is created
    :dirname: New folder's name
    """
    new_path = os.path.join(root, dirname)
    if (not os.path.exists(new_path)):
        # Create directory
        os.mkdir(new_path)

def listFiles(path: str, suffix: str, pattern=False) -> list:
    """
    Function to retrieve files from a directory
    ============================================
    Two options:
    1. If there is a suffix and pattern = False, find
    files that ends with suffix.
    2. When suffix exists and pattern will be a string, search
    files that contains the regex in pattern and ends with
    suffix.

    :path: Directory path where the files are searched.
    :suffix: Like the files must end.
    :pattern: Regex to search files inside the dir.
    """
    files = []
    # Option 2
    if pattern:
        for file in os.listdir(path):
            if file.endswith(suffix) and re.search(pattern,file):
                files.append(os.path.join(path,file))
    # Option 1
    else:
        for file in os.listdir(path):
            if file.endswith(suffix):
                files.append(os.path.join(path,file))

    return files

def writeIMD(imdpath: str) -> dict:
    """
    Transform IMD file into a dictionary
    ==========================================
    Walk throught IMD file and transform key = val
    lines into a key: val dictionary.

    :imdpath: String with path to IMD file.
    """
    metadata = {}

    if not imdpath:
        raise ValueError(f'IMD path is not valid.')

    with open(imdpath) as imdfile:

        # If start_subdict True, current line it's a group of metadata
        # e.g. "BEGIN_GROUP = ..."
        start_subdict = False

        # Save group's name as line value
        # e.g., in "BEGIN_GROUP = BAND_B" subdict_key = 'BAND_B'
        subdict_key = ""

        subdict = {} # Save key:value inside the group

        for line in imdfile:

            # Find lines with metadata
            # i.e. key = val lines except lines end with 'END;'
            if("=" in line):

                if(";" in line):
                    # Save line except ';'
                    line = line[0:len(line)-2]

                (key, value) = line.split("=")
                # Remove white strips
                key = key.strip()
                value = value.strip()

                # Handle BANDS and GLOBAL image metadata
                if("BEGIN_GROUP" in key):
                    start_subdict = True
                    subdict_key = value # Group name
                    continue
                elif("END_GROUP" in key):
                    start_subdict = False
                    # Save group's key:val items inside IMD metadata
                    metadata[subdict_key] = subdict
                    subdict = {} # Reset variable
                    continue

                if(start_subdict):
                    subdict[key] = value # Save key:val group values
                else:
                    metadata[key] = value

    return(metadata)

# Retrieve bands keys from IMD file
def get_band_keys(imd: dict) -> list:
    bands = []
    for i in imd.keys():
        if re.search('BAND',i):
            band = i.split("_")[1]
            bands.append(band)
    return(bands)

def get_csv_row(value: str, column: str, csvPath: str) -> list:
    """
    Get csv row by column value
    ==============================

    Walk csv by row and return the ones which contains in
    required <column> the <parameter> string.

    :value: Value should be inside the column
    :column: Column name which must contain the parameter <value>
    :csvPath: Path with the csv to read
    """
    with open(csvPath) as file:
        # Read csv as json (column as key in each value row)
        csvReader = csv.DictReader(file)
        for row in csvReader:
            if row[column] == value:
                return row

def ARC(input_image, output_image, imd: dict):
    """
    Calculate Formula to AbsoluteRadiometricCorrection ARC in gdal_calc by band
    ============================================================================

    Formula: L = GAIN * DN * ( abscalfactor / effectivebandwith ) + OFFSET

    The required parameters are in wv3 radiometric use file (GAIN and OFFSET) and
    IMD metadata (abscalfactor and effectivebandwith).

    :input_image: Path from the image to transform
    :output_image: Path to store the atmospheric corrected image
    :imd: IMD image metadata transformed in a dict.
    """
    # Get WV3 image bands
    wv_bands = get_band_keys(imd)
    # Return formula to compute ARC BY BAND
    formulas = []
    # Return bands
    bands = []
    # Return band number
    b_number = []
    for i in range(0, len(wv_bands)):
        band = wv_bands[i]
        # Assign a letter to each band
        band_letter = list(string.ascii_uppercase)[i]

        # Return global metadata by band
        gm = get_csv_row(band, 'bandas', RADIOMETRIC_USE)
        gain = gm['GAIN_2015v2']
        offset = gm['OFFSET_2015v2']

        # Return image metadata by band
        band_metadata = imd['BAND_'+band]
        absCalFactor = band_metadata['absCalFactor']
        effectiveBandwidth = band_metadata['effectiveBandwidth']

        # Retrun ARC formula
        f = f"abs( {gain} * {band_letter} * ( {absCalFactor} / {effectiveBandwidth} ) + ({offset}) )"
        formulas.append('--calc="' + f + '"')

        # Match input band and its letter (the image is the same)
        b = f'-{band_letter} "{input_image}"'
        bands.append(b)
        # Custom band number
        n = f'--{band_letter}_band={wv_bands.index(band)+1}'
        b_number.append(n)

    # Perform ARC calc
    output = calc(formulas, bands, b_number, output_image)
    return(output)

def sixs(input_image, output_image, xml, gee_credentials, service_account, imd):
    """
    Formula: REF(BOA) = pi * (L - Lp) / t * ( Edir + Edif )

    Lp = Path radiance
    t = transmissivity (absorption transmissivity (TAUv?) * scattering transmissivity (TAUz?))
    Edir = Direct Solar Irradiance (Eo?)
    Edif = Diffuse solar irradiance (Edown?)
    * Terms follow by ? are the closest approx to 6S formula terms (from Sam
    Murphy repo) in Chavez 1996 radiance to BOA reflectance function.

    :input_image: Path from the image to transform
    :output_image: Path to store the atmospheric corrected image
    :xml: Global image metadata in XML (parsed xml)
    :gee_credentials: GEE PRIVATE API KEY
    :service_account: Email from private API key
    :imd: IMD image metadata transformed in a dict.
    """
    collections.Callable = collections.abc.Callable
    # Credentials path
    credentials = ee.ServiceAccountCredentials(service_account, gee_credentials)
    ee.Initialize(credentials)

    # Retrieve BBOX to get geompoint (retrieve altitude and atmospheric data)
    # Get BBOX coordinates in EPSG:4326
    coords = []
    for i in ['NWLONG','NWLAT','SELONG','SELAT']:
        coord = xml.getElementsByTagName(i)[0].firstChild.data
        coords.append(float(coord))
    # Create geom poligon with image footprint
    footprint = ee.Geometry.Rectangle(coords)
    # Get center point
    geom = footprint.centroid()

    """
    6S object

    The backbone of Py6S is the 6S (i.e. SixS) class. It allows you to define the
    various input parameters, to run the radiative transfer code and to access
    the outputs which are required to convert radiance to surface reflectance.
    """
    # Instantiate
    s = SixS()

    """
    Geometric conditions

    - Month
    - Day
    - Sun zenith and azimuth angles
    - Sensor/View zenith and azimuth angles
    """
    s.geometry = Geometry.User()
    # Date
    strDate = imd['MAP_PROJECTED_PRODUCT']['earliestAcqTime']
    # Convert a string with UTC date to python datetime
    date = datetime.strptime(
        strDate,
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    s.geometry.month = date.month # Month (used for Earth-Sun distance)
    s.geometry.day = date.day     # Day (used for Earth-Sun distance)
    
    # Sensor zenith angle (NADIR)
    s.geometry.view_z = 0
    # Sensor azimuth angle
    s.geometry.view_a = float(imd['IMAGE_1']['meanSatAz'])
    # Solar zenith angle
    solar_z = round(90 - float(imd['IMAGE_1']['meanSunEl']), 2) 
    s.geometry.solar_z = solar_z
    # Solar azimuth angle
    s.geometry.solar_a = float(imd['IMAGE_1']['meanSunAz'])

    """
    Atmospheric profile and Aerosol Profile

    * Import manually the atmospheric constitutients
    * AOT at 550nm
    """
    # Atmospheric constituents
    date = ee.Date(str(date.year)+"-"+str(date.month)+"-"+str(date.day))
    h2o = Atmospheric.water(geom,date).getInfo()
    o3 = Atmospheric.ozone(geom,date).getInfo()
    aot = Atmospheric.aerosol(geom,date).getInfo()

    # Atmospheric constituents
    s.atmos_profile = AtmosProfile.UserWaterAndOzone(h2o,o3)
    # s.aero_profile = AeroProfile.Continental
    s.aero_profile = AeroProfile.Desert
    s.aot550 = aot

    """
    Altitudes

    Allows the specification of target and sensor altitudes.
    """
    # Altitude - Shuttle Radar Topography mission (covers *most* of the Earth)
    SRTM = ee.Image('CGIAR/SRTM90_V4') 
    alt = SRTM.reduceRegion(
        reducer = ee.Reducer.mean(),
        geometry = geom.centroid()
    ).get('elevation').getInfo()
    km = alt/1000 # i.e. Py6S uses units of kilometers
    s.altitudes.set_target_custom_altitude(km)
    sensor_altitude = float(imd['IMAGE_1']['meanSatEl'])
    s.altitudes.set_sensor_custom_altitude(sensor_altitude)

    """
    Wavelenght conditions

    Wavelenght spectral response is computed with Wavelength() function passing
    the start and end band wavelength (micrometers)

    - Wavelength function: 
    https://github.com/robintw/Py6S/blob/master/Py6S/Params/wavelength.py
    - WV3 Spectral Response:
    https://dg-cms-uploads-production.s3.amazonaws.com/uploads/document/file/105/DigitalGlobe_Spectral_Response_1.pdf

    """
    # Get WV3 image bands
    wv_bands = get_band_keys(imd)
    # Return formula to compute ARC BY BAND
    formulas = []
    # Return bands
    bands = []
    # Return band number
    b_number = []
    for i in range(0, len(wv_bands)):
        band = wv_bands[i]
        # Assign a letter to each band
        band_letter = list(string.ascii_uppercase)[i]

        gm = get_csv_row(band, 'bandas', RADIOMETRIC_USE) 
        lowerWav = float(gm['lowerBandEdge'])
        upperWav = float(gm['upperBandEdge'])

        s.wavelength = Wavelength(lowerWav, upperWav)

        # print(
        #     "6S inputs:\n"+
        #     f"- H2O: {h2o}\n"
        #     f"- O3: {o3}\n"
        #     f"- AOT: {aot}\n"
        #     f"- Altitude: {km}\n"
        #     f"- Solar zenith angle: {solar_z}\n"
        # )
    
        # run 6S for this waveband
        s.run()

        # extract 6S outputs
        Edir = s.outputs.direct_solar_irradiance             #direct solar irradiance
        Edif = s.outputs.diffuse_solar_irradiance            #diffuse solar irradiance
        Lp   = s.outputs.atmospheric_intrinsic_radiance      #path radiance
        absorb  = s.outputs.trans['global_gas'].upward       #absorption transmissivity
        scatter = s.outputs.trans['total_scattering'].upward #scattering transmissivity
        tau2 = absorb*scatter                                #total transmissivity

        # print(f"Solar zenith angle: {solar_z}, Altitude (km): {km}, % Water Vapour: {h2o}, Ozone: {o3}, AOT: {aot}")
        # print(f"Band {band} Path radiance: {Lp}")
        
        # Compute surface reflectance formula
        f = f'(pi*({band_letter} - {Lp}))/({tau2}*({Edir}+{Edif}))'
        formulas.append('--calc="' + f + '"')

        # Match input band and its letter (the image is the same)
        b = f'-{band_letter} "{input_image}"'
        bands.append(b)
        # Custom band number
        n = f'--{band_letter}_band={wv_bands.index(band)+1}'
        b_number.append(n)

    # Perform 6S
    output = calc(formulas, bands, b_number, output_image)
    return(output)
    
def wBrovey(mul: str, pan: str, output_image: str):
    """
    Compute pansharpening with "wighted" Brovey technique
    :mul: Path of MUL image without resizing.
    :pan: Original PAN image path
    :output_image: output path
    """
    weights_wv3 = [0.005, 0.142, 0.209, 0.144, 0.234, 0.157, 0.116]
    # Transform weights to introduce in gdal tool
    weights_str = [str(w) for w in weights_wv3]
    weights = (" -w ").join(weights_str)
    # Add specific mul bands (1-7)
    bands_str = [str(b + 1) for b in range(0, len(weights_wv3))]
    bands = (f' "{mul}",band=').join(bands_str)

    # Get the src where gdal tool is located
    module = os.path.abspath(os.path.join(__file__, os.pardir))
    gdal_pansharpen = [
        f'python {module}/gdal_pansharpen.py "{pan}"',
        f'"{mul}",band={bands} "{output_image}" -of GTiff',
        f'-w {weights}'
    ]
    command = (" ").join(gdal_pansharpen)
    output = subprocess.check_output(command, shell=True)
    return [command, output]


