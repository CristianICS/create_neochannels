# WV3 images path (folder with the images inside)
WV3_MUL = "D:/arqueologia-proceso-copiaseguridad/codigo-zenodo/test_images/wv3/015105921010_01/processed_data/17MAY29064346-M2AS-015105921010_01_P001_6S.tif"
WV3_PSH = "D:/arqueologia-proceso-copiaseguridad/codigo-zenodo/test_images/wv3/015105921010_01/processed_data/17MAY29064346-P2AS-015105921010_01_P001_wBrovey.tif"
# NOTE: The 6S corrected WV3 multispectral image is used to compute B8 (which is not 
# inside PANSHARPENED image)

# Georreferenced CORONA image
CORONA = "D:/arqueologia-proceso-copiaseguridad/codigo-zenodo/test_images/corona/D3C1207-100019A030_g_zar_tepe_grd_clip.tif"

# ONLY CHANGE CODE ABOVE TO THIS LINE ----------------------------------------->

bands_pos = [1, 2, 3, 4, 5, 6, 7, 8]
bands_key = ["C", "B", "G", "Y", "R", "RE1", "N", "N2"]
# NOTE: Band keys must be same as indices.json band keys.
# NOTE: Band keys must be ordered from first image's band to last band
# NOTE: Band keys must include all image bands.

import os
import indices as spin
import pca
import customfunctions as cf
import highpassfilter as hpf

ROOT = os.path.abspath(os.path.join(__file__, os.pardir))
cf.createDir(ROOT, 'neochannels')

if len(WV3_PSH) > 0 and len(WV3_MUL) > 0:

    print("==== SPECTRAL INDICES (WV3 image) ====\n")
    image_name = os.path.basename(WV3_PSH).split('.')[0]
    OUTPUT_DIR = os.path.join(ROOT, f'neochannels/{image_name}/indices')
    cf.createDir(ROOT, f'neochannels/{image_name}')
    cf.createDir(ROOT, f'neochannels/{image_name}/indices')
    spin.compute_all_indices(WV3_PSH, bands_pos, bands_key, OUTPUT_DIR, img_120cm_path = WV3_MUL)

    print("==== PCA (WV3 image) ====\n")
    # NOTE: PCA will be executed both, with pansharpen imagen (7 bands) and with original image (8 bands)
    tasks = [
        {
            'folder': "PCA120cm",
            'image_path': WV3_MUL,
            'bands': ["C", "B", "G", "Y", "R", "RE", "N1", "N2"]
        },
        {
            'folder': "PCA31cm",
            'image_path': WV3_PSH,
            'bands': ["C", "B", "G", "Y", "R", "RE", "N1"]
        }
    ]
    for task in tasks:
        OUTPUT_DIR = os.path.join(ROOT, f'neochannels/{image_name}/{task["folder"]}')
        cf.createDir(ROOT, f'neochannels/{image_name}/{task["folder"]}')
    

        combis_dict = pca.combis(task['bands'], 3, OUTPUT_DIR)

        for combi_id, combi_bands in combis_dict.items():
            # Create PCA image
            print(f"\nWriting PCA from combi {combi_id} bands\n")
            print(f"==========================================\n")
            name = os.path.basename(task['image_path']).split('.')[0]
            out_name = '_'.join([name, task['folder'], 'C' + str(combi_id)])
            img_out_path = os.path.join(OUTPUT_DIR, out_name + '.tif')
            eigenvals, eigenvectors = pca.compute_pca(task['image_path'], combi_bands, img_out_path)
            # Write stats
            out_stats = os.path.join(OUTPUT_DIR, out_name +'_stats.csv')
            pca.write_stats(eigenvals, eigenvectors, out_stats, "csv")

elif len(CORONA) > 0:
    print('==== CORONA HIGH PASS FILTER ====\n')
    image_name = os.path.basename(CORONA).split('.')[0]
    OUTPUT_DIR = os.path.join(ROOT, f'neochannels/{image_name}')
    cf.createDir(ROOT, f'neochannels/{image_name}')
    output = os.path.join(OUTPUT_DIR, image_name + '_focal.tif')
    hpf.focal(CORONA, output)