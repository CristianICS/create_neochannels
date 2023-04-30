"""____________________________________________________________________________
Script Name:        pca.py
Description:        Functions to compute PCA and export the image.
Prerequisites:      GDAL version "3.1.4" or greater
____________________________________________________________________________"""
# 0. Import packages
# =============================================================================
import os, json, itertools
import numpy as np
from osgeo import gdal
from multiprocessing.pool import ThreadPool
import dask
from dask import array as da

# 1. Module functions
# =============================================================================

def combis(band_keys: list, n_min: int, out_path: str) -> dict:
    """
    Create a dictionary and a csv file with all posible combinations
    with image bands.

    The dict has a key as combi id and a value formed by a list of
    band indexs inside current combination. This list of indexs is
    used to select the bands from the image.

    CSV file has two rows:

    - id: Unique combi identifier
    - bands: Acronyms of bands in current combi separated by '-'

    :bands: List with band keys.
    :n_min: Minimun number of bands to combine. Maximun number
    will be the image's band number.
    :out_path: Dir to save a csv file with all combis.
    """

    # List with numbers of band possible combinations
    n_combis = list(range(n_min,len(band_keys)))

    combis_dict = {}

    combi_id = 1

    def write_csv_combi(cid: int, bkeys: list) -> str:
        """
        Construct csv line

        :cid: Combination ID
        :bkeys: Band letters/keys inside combination
        """
        combi_selected_bands = '-'.join(bkeys)

        line = '\n'+str(cid)+',"'+combi_selected_bands+'"'

        return line

    def get_bands_index(combi: list, bkeys: list) -> list:
        """
        Retrieve the position of combis bands relative to the
        original image bands.

        :combi: List with combitantion selected bands.
        :bkeys: Ordered image's bands
        """
        indxs = []
        for c in combi:
            # Index plus one, python indexing start from 0
            indxs.append(bkeys.index(c) + 1)
        return indxs

    csv_header = '"id","bands"'
    csv_output = open(out_path + '/pca_band_combis.csv', 'w')
    csv_output.write(csv_header)

    # Calculate all combinations
    for L in n_combis:

        for subset in itertools.combinations(list(band_keys), L):
            # subset variable is a list with all the band keys in current combi
            combis_dict[combi_id] = get_bands_index(subset, band_keys)

            csv_line = write_csv_combi(combi_id, subset)
            csv_output.write(csv_line)

            combi_id += 1

    # The last combination is integrated by all image bands
    combis_dict[combi_id] = get_bands_index(band_keys, band_keys)
    csv_line = write_csv_combi(combi_id, band_keys)
    csv_output.write(csv_line)
    csv_output.close()

    return combis_dict

def compute_pca(img_path: str, bands: list, out_path: str,
estimator_matrix: str = "Covariance"):
    """
    Perform PCA with selected bands and export new image
    with principal components as bands.

    :img_path: Image path.
    :bands: List with selected bands to compute PCA.
    :out_path: Output image path
    :estimator_matrix: Correlation | Covariance

    From PCA4CD QGIS plugin
    https://github.com/SMByC/PCA4CD/blob/master/core/pca_dask_gdal.py
    copyright: (C) 2018-2019 by Xavier Corredor Llano, SMByC

    Important:
    - The number of PCs is 3 in this version. It could be until the max
    number of bands.
    - Dask block size is computed automatically.
    - It's assumed image data is in float32
    - All bands must have the same dimensions
    """
    # Init dask as threads (shared memory is required)
    dask.config.set(pool=ThreadPool(1))

    raw_image = []
    nodata_mask = None
    src_ds = gdal.Open(str(img_path), gdal.GA_ReadOnly)

    nodata = None
    # Image dimensions
    img_rows = None
    img_columns = None

    for band in bands:
        src_ds_band = src_ds.GetRasterBand(band).ReadAsArray()

        # Retrieve image dimensions
        rows = src_ds_band.shape[0]
        columns = src_ds_band.shape[1]

        if img_rows is None:
            img_rows = rows
        elif img_rows != rows:
            raise ValueError("All bands must have same dimensions.")

        if img_columns is None:
            img_columns = columns
        elif img_columns != columns:
            raise ValueError("All bands must have same dimensions.")

        ds = src_ds_band.flatten().astype(np.float32)

        # Specify the nodata value, all bands must have the same
        nodata_value = src_ds.GetRasterBand(band).GetNoDataValue()
        if nodata is None:
            nodata = nodata_value
        elif nodata != nodata_value:
            raise ValueError("Image nodata value must be equal in all bands.")

        # Handle nodata mask
        if np.isnan(nodata):
            nodata_mask = np.isnan(ds) if nodata_mask is None else np.logical_or(nodata_mask, np.isnan(ds))
        elif nodata is not None:
            nodata_mask = ds == nodata if nodata_mask is None else np.logical_or(nodata_mask, ds == nodata)
        raw_image.append(ds)

    # Pair-masking data, let only the valid data across all dimensions/bands
    if nodata is not None:
        raw_image = [b[~nodata_mask] for b in raw_image]

    # Stack the array with flattened bands into a numpy array
    # with row dimension = number of image bands
    flat_dims = da.vstack(raw_image).rechunk(('auto'))
    n_bands = flat_dims.shape[0]

    print("..Scaling the matrix\n")
    # Compute the mean of each band.
    band_mean = []
    for i in range(n_bands):
        band_mean.append(dask.delayed(np.mean)(flat_dims[i]))
    band_mean = dask.compute(*band_mean)

    print("..Compute covariance/correlation\n")
    # Empty array to save new matrix with cov/corr between all bands
    estimation_matrix = np.empty((n_bands, n_bands))
    if estimator_matrix == "Correlation":
        for i in range(n_bands):
            deviation_scores_band_i = flat_dims[i] - band_mean[i]
            for j in range(i, n_bands):
                deviation_scores_band_j = flat_dims[j] - band_mean[j]
                estimation_matrix[j][i] = estimation_matrix[i][j] = \
                    da.corrcoef(deviation_scores_band_i, deviation_scores_band_j)[0][1]
    elif estimator_matrix == "Covariance":
        for i in range(n_bands):
            deviation_scores_band_i = flat_dims[i] - band_mean[i]
            for j in range(i, n_bands):
                deviation_scores_band_j = flat_dims[j] - band_mean[j]
                estimation_matrix[j][i] = estimation_matrix[i][j] = \
                    da.cov(deviation_scores_band_i, deviation_scores_band_j)[0][1]
    else:
        raise ValueError("The 'estimator_matrix' parameter is not valid.")
    # free mem
    del raw_image, flat_dims, ds

    if estimation_matrix[~np.isnan(estimation_matrix)].size == 0:
        raise ValueError("Invalid estimation matrix.")

    print("..Calculate eigenvectors&eigenvalues\n")
    # calculate eigenvectors & eigenvalues of the matrix
    # use 'eigh' rather than 'eig' since estimation_matrix
    # is symmetric, the performance gain is substantial
    eigenvals, eigenvectors = np.linalg.eigh(estimation_matrix)

    # sort eigenvalue in decreasing order
    idx_eigenvals = np.argsort(eigenvals)[::-1]
    eigenvals = eigenvals[idx_eigenvals]

    # sort eigenvectors according to same index
    eigenvectors = eigenvectors[:,idx_eigenvals]

    # select the first n eigenvectors (n is desired dimension
    # of rescaled data array, or dims_rescaled_data)
    n_pc = 3 # Web mapping where pca images are displayed not allow band selection
    eigenvectors = eigenvectors[:, :n_pc]

    print("..Save new tif image\n")
    # Create empty raster
    creation_options = ['COMPRESS=DEFLATE','PREDICTOR=3']
    tmp_file = os.path.normpath(out_path)
    driver = gdal.GetDriverByName("GTiff")
    out_img = driver.Create(
        str(tmp_file),
        img_columns,
        img_rows,
        n_bands,
        gdal.GDT_Float32,
        options=creation_options
    )

    def select_band(band_num):
        """
        Select the image band number from 'bands' variable.
        The bands integrated in PCA could not be 1,2,3
        """
        return bands[band_num]

    def get_raw_band_from_stack(band_num):
        selected_band = select_band(band_num)
        return src_ds.GetRasterBand(selected_band).ReadAsArray().flatten().astype(np.float32)

    for i in range(n_pc):
        pc = 0

        print(f"....Compute PC{i + 1}\n")
        for j in range(n_bands):
            pc = pc + eigenvectors[j, i] * (get_raw_band_from_stack(j) - band_mean[j])

        if nodata is not None:
            pc[nodata_mask] = nodata
        pc = pc.reshape((src_ds.RasterYSize, src_ds.RasterXSize))

        print("....Write PC as a band\n")
        pc_band = out_img.GetRasterBand(i+1)
        if nodata is not None:
            pc_band.SetNoDataValue(nodata)
        pc_band.WriteArray(pc)

    # set projection and geotransform
    geotrs = src_ds.GetGeoTransform()
    if geotrs is not None:
        out_img.SetGeoTransform(geotrs)
    prj = src_ds.GetProjection()
    if prj is not None:
        out_img.SetProjection(prj)
    out_img.FlushCache()
    del pc, pc_band, out_img

    # free mem
    del src_ds, nodata_mask

    # compute the pyramids for the pc_image
    os.system('gdaladdo -q --config BIGTIFF_OVERVIEW YES "{}"'.format(out_path))

    return eigenvals, eigenvectors

def write_stats(eigenvals, eigenvectors, outfile, outformat: str = "json"):
    """
    Calculate PCA statistics and write in a file.

    :eigenvals: Matrix with eigenvalues from compute_pca
    :eigenvectors: Matrix with eigenvectors from compute_pca
    :outfile: Output file path
    :outformat: json | csv
    """
    # pca statistics
    n_bands = len(eigenvals.tolist())

    if outformat == "json":
        pca_stats = {}
        pca_stats["eigenvals"] = eigenvals.tolist()
        pca_stats["eigenvals_%"] = (eigenvals*100/n_bands).tolist()
        pca_stats["eigenvectors"] = eigenvectors.tolist()
        # Save stats
        with open(os.path.abspath(outfile),'w') as fp:
            json.dump(pca_stats, fp)
    elif outformat == "csv":
        pca_stats = [] # csv rows
        # Add header. Same columns as number of bands
        header_bandnames = ["band_" + str(band + 1) for band in range(0, n_bands)]
        header = '"stat_name",' + '"' + ('","').join(header_bandnames) + '"'
        pca_stats.append(header)
        # Eigenvalues stats
        eigenvals_str = [str(eval) for eval in eigenvals.tolist()]
        pca_stats.append('"eigenvals",' + (',').join(eigenvals_str))

        eigenvals_prc_str = [str(eval) for eval in (eigenvals*100/n_bands).tolist()]
        pca_stats.append('"eigenvals_%",' + (',').join(eigenvals_prc_str))

        # Eigenvectors stats
        ev_list = eigenvectors.tolist()
        for i in range(0, len(ev_list)):
            ev_str = [str(ev) for ev in ev_list[i]]
            pca_stats.append(f'"eigenvectors_pc{i + 1}",' + (',').join(ev_str))

        # Save stats
        csvfile = open(outfile, 'w')
        for row in pca_stats:
            csvfile.write(row + '\n')
        csvfile.close()


