from pathlib import Path
from typing import Union


rgi_regions = {'v7.0': [
    'RGI2000-v7.0-G-01_alaska',
    'RGI2000-v7.0-G-02_western_canada_usa',
    'RGI2000-v7.0-G-03_arctic_canada_north',
    'RGI2000-v7.0-G-04_arctic_canada_south',
    'RGI2000-v7.0-G-05_greenland_periphery',
    'RGI2000-v7.0-G-06_iceland',
    'RGI2000-v7.0-G-07_svalbard_jan_mayen',
    'RGI2000-v7.0-G-08_scandinavia',
    'RGI2000-v7.0-G-09_russian_arctic',
    'RGI2000-v7.0-G-10_north_asia',
    'RGI2000-v7.0-G-11_central_europe',
    'RGI2000-v7.0-G-12_caucasus_middle_east',
    'RGI2000-v7.0-G-13_central_asia',
    'RGI2000-v7.0-G-14_south_asia_west',
    'RGI2000-v7.0-G-15_south_asia_east',
    'RGI2000-v7.0-G-16_low_latitudes',
    'RGI2000-v7.0-G-17_southern_andes',
    'RGI2000-v7.0-G-18_new_zealand',
    'RGI2000-v7.0-G-19_subantarctic_antarctic_islands'
], 'v6.0': [
    '01_rgi60_Alaska',
    '02_rgi60_WesternCanadaUS',
    '03_rgi60_ArcticCanadaNorth',
    '04_rgi60_ArcticCanadaSouth',
    '05_rgi60_GreenlandPeriphery',
    '06_rgi60_Iceland',
    '07_rgi60_Svalbard',
    '08_rgi60_Scandinavia',
    '09_rgi60_RussianArctic',
    '10_rgi60_NorthAsia',
    '11_rgi60_CentralEurope',
    '12_rgi60_CaucasusMiddleEast',
    '13_rgi60_CentralAsia',
    '14_rgi60_SouthAsiaWest',
    '15_rgi60_SouthAsiaEast',
    '16_rgi60_LowLatitudes',
    '17_rgi60_SouthernAndes',
    '18_rgi60_NewZealand',
    '19_rgi60_AntarcticSubantarctic'
]}

def rgi_loader(rgi_dir: Union[str, Path], rgi_reg: Union[int, str, Path], version: str = 'v7.0') -> Path:
    """
    Returns the path to the RGI shapefile for the given region and version. Checks whether RGI files are stored in
    a single directory, or in sub-directories.

    :param rgi_dir: The path to the directory where the RGI files or folders are stored.
    :param rgi_reg: The RGI region name (e.g., RGI2000-v7.0-G-01_alaska) or number (e.g., 1 for region 01)
    :param version: The RGI version (v7.0 or v6.0)
    """
    # if we've given a number, get the region name from that
    if isinstance(rgi_reg, int):
        rgi_reg = rgi_regions[version][rgi_reg-1] # subtract 1 to get the index

    # load the RGI outlines
    if Path(rgi_dir, rgi_reg + '.shp').exists():
        return Path(rgi_dir, rgi_reg + '.shp')
    elif Path(rgi_dir, rgi_reg, rgi_reg + '.shp').exists():
        return Path(rgi_dir, rgi_reg, rgi_reg + '.shp')
    else:
        raise FileNotFoundError(f"Unable to find {rgi_reg}.shp in {rgi_dir}, or a sub-directory. Please check path and filename.")
