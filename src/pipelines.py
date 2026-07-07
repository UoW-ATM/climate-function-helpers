from pathlib import Path
import pandas as pd

from era5_to_climate_impact import compute_climate_impact
from hotspot_computation import compute_hotspots_from_climate_impact
from lib.trajectory_construction import compute_trajectories
from compute_emissions import compute_all_flights_emissions


def compute_all_emissions_from_all_ft(era5_input_path=None, era5_name_list=[], working_directory=None,
                                      compute_hotspot=False, threshold=1e-9, allft_path=None, flight_ids=[],
                                      interpolation_distance_km=15):

    # Compute climate impact files
    era5_input_path = Path(era5_input_path)
    working_directory = Path(working_directory)
    working_directory.mkdir(parents=True, exist_ok=True)

    for name in era5_name_list:
        climate_impact_file_name = '{}_env_processed.nc'.format(name)
        climate_impact_file_path = working_directory / 'climate_files' / climate_impact_file_name

        (working_directory / 'climate_files').mkdir(parents=True, exist_ok=True)

        if not climate_impact_file_path.exists():
            full_name_pl = '{}_pressure_mod.nc'.format(name)
            full_name_sur = '{}_surface_mod.nc'.format(name)

            compute_climate_impact(str(era5_input_path / full_name_pl),
                                   str(era5_input_path / full_name_sur),
                                   output_path=str(climate_impact_file_path).rstrip('.nc'),
                                   climaccf_lib_path=None,
                                   climaccf_config_user_file=None)
        else:
            print('Skipping already computed climate file {}'.format(climate_impact_file_path))

        if compute_hotspot:
            climate_hotspot_file_path = working_directory / 'climate_files' / str(climate_impact_file_name).replace('.nc', '_hotspot.nc')

            compute_hotspots_from_climate_impact(env_impact_file=climate_impact_file_path,
                                                 threshold=threshold,
                                                 output_file=climate_hotspot_file_path,
                                                 variable_name_for_threshold="aCCF_merged")#


    # Compute trajectories from all_ft+
    trajectory_file_path = working_directory / 'trajectories' / 'trajectories.csv'
    (working_directory / 'trajectories').mkdir(parents=True, exist_ok=True)

    if not trajectory_file_path.exists():
        df_trajs = compute_trajectories(allft_path=allft_path,
                             flight_ids=flight_ids,
                             output_path=trajectory_file_path,
                             interpolation_distance_km=interpolation_distance_km)
    else:
        df_trajs = pd.read_csv(trajectory_file_path)


    # Compute flight emissions
    for name in era5_name_list:
        if compute_hotspot:
            climate_impact_file_name = '{}_env_processed_hotspot.nc'.format(name)
        else:
            climate_impact_file_name = '{}_env_processed.nc'.format(name)

        climate_impact_file_path = working_directory  / 'climate_files' / climate_impact_file_name

        all_results = compute_all_flights_emissions(df_trajs,
                                      climate_file_path=climate_impact_file_path,
                                      col_id='tact_id')

        output_name = 'emissions_{}.csv'.format(name)
        output_path = working_directory / 'emissions' / output_name
        (working_directory / 'emissions').mkdir(parents=True, exist_ok=True)

        all_results.to_csv(output_path)

        print('Final emission file saved as {}'.format(output_path))


if __name__ == '__main__':
    compute_all_emissions_from_all_ft(era5_input_path='/home/earendil/Documents/Westminster/Green-Gear/Model/ERA5/OneDrive_1_6-19-2026',
                                      era5_name_list=['DEC2019'],
                                      working_directory='test_pipeline_all_ft',
                                      compute_hotspot=True,
                                      allft_path="/home/earendil/Documents/Westminster/Libraries/test data",
                                      flight_ids=['697364'],
                                      )
