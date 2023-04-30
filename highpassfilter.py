import os
from osgeo import gdal
from multiprocessing.pool import ThreadPool
import numpy as np
import dask
from dask import array as da
from scipy import ndimage

# Save raster image as numpy array
def read_raster(path: str):
    """
    Parse raster as numpy array with raster dimensions.
    Important: The nodata value will be replaced as
    numpy.nan data.
    Important: The default datatype is float32
    Example: Raster with 5 bands, 30 rows and 25 columns
    generates an array with shape (5,30,30).
    :path: Dirpath with image to read.
    return the array with the image and its properties.
    """
    # init dask as threads (shared memory is required)
    dask.config.set(pool=ThreadPool(1))

    raw_image = []
    src_ds = gdal.Open(str(path), gdal.GA_ReadOnly)
    n_bands = src_ds.RasterCount

    projection = src_ds.GetProjection()
    geoTrans = src_ds.GetGeoTransform()

    print("..Read raster")
    nodata = None
    # Write each band in a numpy array
    for band in range(1,n_bands + 1):
        # Transform image band into numpy array
        ds = src_ds.GetRasterBand(band).ReadAsArray().astype(np.float32)

        nodata_value = src_ds.GetRasterBand(band).GetNoDataValue()
        if nodata is None:
            nodata = nodata_value
        elif nodata != nodata_value:
            raise ValueError("Image nodata value must be equal in all bands.")
        print(f"....Band {band} nodata value: {nodata}")
        # Fill nodata values with NaN
        ds[ds == nodata] = np.nan
        # Add band to a list
        raw_image.append(ds)

    # Merge each dimension (bands) in n dimension array (n = number of bands)
    raw_image_np = da.stack(raw_image).rechunk(('auto'))
    return (raw_image_np, projection, geoTrans, nodata)

def get_bbox(path: str) -> dict:
    """
    Return the bounding box of a raster plus its
    resolution.
    https://gis.stackexchange.com/a/201320
    :path: Raster path
    return [minx, miny, maxx, maxy, resx, resy]
    """
    if not os.path.exists(path):
        raise ValueError('The inserted image is not valid. Check its path again.')

    src_ds = gdal.Open(str(path), gdal.GA_ReadOnly)
    geoTrans = src_ds.GetGeoTransform()
    # Get BBOX parameters
    resX = geoTrans[1]
    resY = geoTrans[5]
    # ulx, uly is the upper left corner
    # lrx, lry is the lower right corner
    ulx = geoTrans[0]
    uly = geoTrans[3]
    lrx = ulx + (src_ds.RasterXSize * resX)
    lry = uly + (src_ds.RasterYSize * resY)

    bbox = [ulx,lry,lrx, uly, resX, resY]
    return bbox

def high_pass_filter(array):
    """
    Obtain a numpy array with convolve mul image
    :array: 3D Numpy array with format (n_bands,rows,columns)
    """
    # Create high pass filter to extract spatial component
    # 5x5 Weight matrix (Gangkofner et al., 2007)
    highPassMatrix = np.array([
        [-1, -1, -1,-1, -1],
        [-1, -1, -1,-1, -1],
        [-1, -1, 24, -1, -1],
        [-1, -1, -1,-1, -1],
        [-1, -1, -1,-1, -1],
    ]) / 25

    # Kernel in 3D (repeat kernel for each image band)
    # The convolve function only works if kernel shape is equal
    # array shape.
    k = []

    for b in range(0,array.shape[0]):
        k.append(highPassMatrix)
    k = np.stack(k)

    # Apply convolve automatically with scipy
    convolve_image = ndimage.convolve(array,k,mode='constant',cval=np.nan)
    return convolve_image

def focal(image: str, output_path: str):
    """
    Compute High Pass Filter
    :image: Image to perform focal filter
    :output_path: File output path
    """
    # init dask as threads (shared memory is required)
    dask.config.set(pool=ThreadPool(1))

    # PAN image
    pan_arr, projection, geoTrans = read_raster(image)[0:3]

    # PAN spatial component
    pan_spatial = high_pass_filter(pan_arr)

    # Perform pansharpening
    n_bands = pan_arr.shape[0] # MUL's band number
    rows = pan_arr.shape[1]
    columns = pan_arr.shape[2]
 
    # Create empty raster
    creation_options = ['COMPRESS=DEFLATE','PREDICTOR=3']
    tmp_file = os.path.normpath(output_path)
    driver = gdal.GetDriverByName("GTiff")
    out_img = driver.Create(
        str(tmp_file),
        columns,
        rows,
        n_bands,
        gdal.GDT_Float32,
        options=creation_options
    )

    # Pan image has 3D size, get the first band (and the only one)
    # pan_arr2d = pan_arr[0,:,:]
    pan_spatial2d = pan_spatial[0,:,:]
    pansharpen_band = out_img.GetRasterBand(1)
    pansharpen_band.WriteArray(np.array(pan_spatial2d))

    # set projection and geotransform
    if geoTrans is not None:
        out_img.SetGeoTransform(geoTrans)
    if projection is not None:
        out_img.SetProjection(projection)
    out_img.FlushCache()