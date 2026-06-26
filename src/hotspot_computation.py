# script for calculating hotspot grid cells, needs to have the following specified in the command line (path to those files):
# command line: python Hotspot.py input_netcdf output_netcdf -thr

from pathlib import Path
import xarray as xr
import argparse


def compute_hotspot(env_impact_file=None, threshold=1e-9, output_file=None,
                    variable_name_for_threshold="aCCF_merged"):
    if env_impact_file is None:
        PROJECT_ROOT = Path(__file__).resolve().parents[1]
        env_impact_file = PROJECT_ROOT / "env_impact_data_from_climaccf" / "env_processed.nc"
        # env_impact_file = "hotspot.nc"

    print('Computing hotspot based on file', env_impact_file)

    # Open the NetCDF file
    ds = xr.open_dataset(env_impact_file, engine="netcdf4")

    comparison_value = threshold

    # Create the binary variable
    binary_mask = (ds[variable_name_for_threshold] > comparison_value).astype(int)

    # Assign the binary mask to the dataset with a meaningful name
    ds["hotspot"] = binary_mask

    # Add attributes to the new variable for metadata
    ds["hotspot"].attrs = {
        "description": "Binary mask where 1 indicates aCCF_merged > threshold, 0 otherwise",
        "source": "Derived from aCCF_merged and percentile threshold",
        "valid_range": "0 to 1",
        "units": "binary"
    }

    if output_file is None:
        PROJECT_ROOT = Path(__file__).resolve().parents[1]
        output_file = PROJECT_ROOT / "env_impact_data_from_climaccf" / "env_processed_hotspot.nc"
        output_file.resolve().parents[0].mkdir(parents=True, exist_ok=True)

    # Save to a new NetCDF file
    ds.to_netcdf(output_file)
    ds.close()

    print('Threshold filed saved as', output_file)


if __name__ == "__main__":
# Set up argument parser
    parser = argparse.ArgumentParser(description="Specify NetCDF file and the value of hotspot threshold to calculate hotspot grid cells. ")
    parser.add_argument("-input",
                        "--input_netcdf",
                        type=str,
                        help="Path to the NetCDF env_processed file, result of climaccf library.")
    parser.add_argument("-output",
                        "--output_netcdf",
                        type=str,
                        help="Path to the output NetCDF file")
    parser.add_argument("-thr",
                        "--threshold",
                        type=float,
                        help="Threshold value for comparison (supports scientific notation)")

    # Parse arguments
    args = parser.parse_args()
    input_file = args.input_netcdf

    compute_hotspot(env_impact_file=args.input_netcdf,
                    threshold=args.threshold,
                    output_file=args.output_netcdf
                    )

