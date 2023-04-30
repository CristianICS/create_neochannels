

# WV3 images path (folder with the images inside)
MUL_PATH = "D:/arqueologia-proceso-copiaseguridad/codigo-zenodo/test_images/wv3/015105921010_01/015105921010_01_P001_MUL"
PAN_PATH = "D:/arqueologia-proceso-copiaseguridad/codigo-zenodo/test_images/wv3/015105921010_01/015105921010_01_P001_PAN"

# GEOJSON feature to clip the above images (optional)
AOI_PATH = "D:/arqueologia-proceso-copiaseguridad/codigo-zenodo/aois/aoi_zar_tepe_reduced.geojson"

# Google Earth Engine API private key json
CREDENTIALS = "D:/arqueologia-proceso-copiaseguridad/codigo-zenodo/earthengine-private-key.json"
# client_email inside private key JSON
SERVICE_ACCOUNT = "id-s-atmosphericcorrection@s-correction.iam.gserviceaccount.com" 

# ONLY CHANGE CODE ABOVE TO THIS LINE ----------------------------------------->

# Import packages
import os
from xml.dom import minidom
import customfunctions as cf

ROOT = os.path.abspath(os.path.join(MUL_PATH, os.pardir))
OUTPUT_DIR = os.path.join(ROOT, 'processed_data')
cf.createDir(ROOT, 'processed_data')

# Import custom modules
import customfunctions as cf

# Store the last MUL processed image
PROCESSED_MUL = ""

# Store the last PAN processed image
PROCESSED_PAN = ""

for folder in [MUL_PATH, PAN_PATH]:
    # Select the image
    IMAGE = cf.listFiles(folder, 'TIL')[0]

    # Handle metadata
    # Store metadata from XML and IMD files
    IMD = cf.writeIMD(cf.listFiles(folder, 'IMD')[0])
    XML = minidom.parse(cf.listFiles(ROOT, 'README.XML')[0])
    
    # Retrieve resolution
    resx = IMD['MAP_PROJECTED_PRODUCT']['colSpacing']
    resy = IMD['MAP_PROJECTED_PRODUCT']['rowSpacing']

    # Get image name and switch the extension
    image_name = os.path.basename(IMAGE).split('.')[0]
    
    print("Computed image: "+ image_name +"\n")
    print("==== PRETREATMEANTS ====\n")
    # Output image path
    output_tiff = os.path.join(OUTPUT_DIR, image_name + '.tif')

    if len(AOI_PATH) != 0:
        print('..Clip image '+ image_name +'\n')
        
        output = cf.clip(resx, resy, AOI_PATH, IMAGE, output_tiff)
        # Handle possible errors in AOI path 
        print(output[0], '\n')
        print(output[1], '\n')
        
        IMAGE = output_tiff
        
    else:
        print('..Translate TIL to TIF '+ image_name +'\n')
        output = cf.translate(resx, resy, IMAGE, output_tiff)
        print(output[0], '\n')
        print(output[1], '\n')
        IMAGE = output_tiff

    print('==== ATMOSPHERIC CORRECTION ====\n')
    print('..ARC transformation\n')
    output_arc = os.path.join(OUTPUT_DIR, image_name + '_ARC.tif')
    output = cf.ARC(IMAGE, output_arc, IMD)
    print(output[0], '\n')
    print(output[1], '\n')
    IMAGE = output_arc

    print('..6S Atmospheric correction\n')
    output_sixs = os.path.join(OUTPUT_DIR, image_name + '_6S.tif')
    output = cf.sixs(IMAGE, output_sixs, XML, CREDENTIALS, SERVICE_ACCOUNT, IMD)
    print(output[0], '\n')
    print(output[1], '\n')
    IMAGE = output_sixs

    if folder == MUL_PATH:
        PROCESSED_MUL = IMAGE
    else:
        PROCESSED_PAN = IMAGE

print('==== PANSHARPENING ====\n')
print("\n..Compute wBrovey pansharpening\n\n")
output_brovey = os.path.join(OUTPUT_DIR, image_name + '_wBrovey.tif')
# Note: Mul image must not be resize
output = cf.wBrovey(PROCESSED_MUL, PROCESSED_PAN, output_brovey)
print(output[0], '\n')
print(output[1], '\n')