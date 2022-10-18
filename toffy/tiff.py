import tifffile as tiff


def write_zlib(file, data, level=8):
    """
    Writes image data to a zlib-compressed TIFF file.
    See: https://github.com/cgohlke/tifffile/blob/master/tifffile/tifffile.py

    Parameters:
        file:   string or path-like object
        data:   NumPy or bytes array
        level:  compression level (1=minimum, 9=maximum)
    """
    tiff.imwrite(file,
                 data,
                 compression='zlib',
                 compressionargs={'level': int(level)})
