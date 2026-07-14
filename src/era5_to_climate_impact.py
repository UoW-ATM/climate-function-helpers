"""
This script will convert raw ERA5 data files into climate impact grid data.
The climate impact data is based on an assumption of the type of aircraft (wide body, narrow body, regional).
The climate impact is in nK/Kg (or fuel burnt).
"""
import os
import sys
from pathlib import Path

import argparse

import yaml
from climaccf.main_processing import ClimateImpact


def get_virtualenv_name() -> str | None:
    """
    Return the active virtual environment name if the script is running inside one.

    Works for:
    - venv
    - virtualenv
    - conda

    Returns None if no virtual environment is detected.
    """

    # Conda exposes the environment name directly.
    conda_env = os.environ.get("CONDA_DEFAULT_ENV")
    if conda_env:
        return conda_env

    # venv / virtualenv usually expose the environment path here.
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        return Path(virtual_env).name

    # Generic Python check: in a venv, sys.prefix differs from sys.base_prefix.
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return Path(sys.prefix).name

    return None


def compute_climate_impact(path_pl, path_sur, output_path=None, climaccf_lib_path=None,  climaccf_config_user_file=None,
                           config_dict_climaccf={}):
    """climate_indicator='ATR',
                           TimHorizon=20, ac_type='wide-body', merged=True,"""

    print("Converting:\n - ", path_pl, "\n - ", path_sur)
    print()

    if climaccf_lib_path is None:
        # climaccf_lib_path = (Path(__file__).parent.parent / 'climaccf').resolve()
        climaccf_lib_path = Path('~/.virtualenvs') / get_virtualenv_name()

    # Dictionary containing input directories where the input data can be found. Two directories need to be specified for input data:
    input_dir = {}

    # 1) Directory for input data provided in pressure levels such as temperature, geopotentialand relative humidity
    input_dir['path_pl'] = path_pl # input_path + 'MAR2019_pressure.nc'  # 'pressure_lev_june2018_res0.5.nc'

    # 2) Directory for input data provided at single pressure level such as top net thermal radiation on the TOA

    input_dir['path_sur'] = path_sur # input_path + 'MAR2019_surface_mod.nc'  # 'surface_june2018_res0.5.nc'

    # In addition to the directories for input data, directory of the CLIMaCCF needs to be specified within input_dir:
    input_dir['path_lib'] = climaccf_lib_path

    # Destination directory where all output will be written:
    if output_path is None:
        PROJECT_ROOT = Path(__file__).resolve().parents[1]
        output_path = PROJECT_ROOT / 'test' / "env_impact_data_from_climaccf" / "env_processed"
        output_path.resolve().parents[0].mkdir(parents=True, exist_ok=True)
        output_path = str(output_path)

    if climaccf_config_user_file is None:
        climaccf_config_user_file = "climaccf_config_user.yml"

    with open(climaccf_config_user_file, "r") as ymlfile:
        confg = yaml.safe_load(ymlfile)

    for k, v in config_dict_climaccf.items():
        confg[k] = v

    # confg['climate_indicator'] = climate_indicator
    # confg['TimHorizon'] = TimHorizon
    # confg['ac_type'] = ac_type
    # confg['merged'] = merged

    CI = ClimateImpact(input_dir, output_path, **confg)
    CI.calculate_accfs(**confg)

    print("\nOutput saved as:", output_path)


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Convert ERA5 data into climate impact")
    parser.add_argument("input_netcdf", type=str,
                        help="Path to the NetCDF env_processed file, result of climaccf library.")
    parser.add_argument("output_netcdf", type=str, help="Path to the output NetCDF file")
    parser.add_argument("-thr", "--threshold", type=float,
                        help="Threshold value for comparison (supports scientific notation)")


    path_pl = "/home/earendil/Documents/Westminster/Green-Gear/Model/ERA5/OneDrive_1_6-19-2026/DEC2019_pressure_mod.nc"
    path_sur = "/home/earendil/Documents/Westminster/Green-Gear/Model/ERA5/OneDrive_1_6-19-2026/DEC2019_surface_mod.nc"

    compute_climate_impact(path_pl,
                           path_sur,
                           output_path=None
                           )