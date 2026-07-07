from datetime import datetime

import xarray as xr
import pandas as pd
import numpy as np

from warnings import warn


def nearest_index(array, values):
    """Return indices of the closest values from `array` for each value in `values`"""
    array = np.asarray(array)
    return np.abs(array[:, None] - values).argmin(axis=0)


def load_climate_impact_file(file_path=None, col_name_hotspot='Climate_hotspots99'):
    ds = xr.open_dataset(file_path)

    # Preload variables to memory as numpy arrays (or xarray.DataArray)
    aCCF_merged = ds['aCCF_merged'].load()
    try:
        hotspot_data = ds[col_name_hotspot].load()
    except KeyError:
        hotspot_data = None
        warn('Not computing hotspot crossings because no data on hotspots in the {} file'.format(file_path))

    co2_data = ds['aCCF_CO2'].load()

    return {'aCCF_merged': aCCF_merged, 'hotspot_data': hotspot_data, 'co2_data': co2_data}


def compute_flight_emission(df_traj, climate_data, time_range=list(range(6, 19)),
                            start_date = datetime(2019, 9, 1),
                            end_date = datetime(2019, 9, 30)) -> pd.DataFrame:
    """
    Format for df_traj needs to be as prescribed in the README.md
    """

    aCCF_merged = climate_data['aCCF_merged']
    hotspot_data = climate_data['hotspot_data']
    co2_data = climate_data['co2_data']

    # df = trajectory_dfs[trajectory_dfs['tact_id'] == f].copy()
    df_traj['Timestamp'] = pd.to_datetime(df_traj['Timestamp'])
    # Original start time of the trajectory
    original_start_time = df_traj['Timestamp'].iloc[0]
    minutes = original_start_time.minute
    seconds = original_start_time.second

    # Define day and hour ranges - change this to suit the period under construction
    day_range = pd.date_range(start=start_date, end=end_date)

    res = []

    for day in day_range:
        for hour in time_range:
            # Define new starting timestamp
            new_start_time = datetime(day.year, day.month, day.day, hour, minutes, seconds)

            # Compute time difference (delta)
            time_shift = new_start_time - original_start_time

            # Shift entire trajectory
            df_shifted = df_traj.copy()
            df_shifted['Shifted Timestamp'] = df_traj['Timestamp'] + time_shift
            lat_arr = df_shifted['Latitude'].to_numpy()
            lon_arr = df_shifted['Longitude'].to_numpy()
            plev_arr = df_shifted['pressure_Level'].to_numpy()  # original pressure level
            time_arr = df_shifted['Shifted Timestamp'].to_numpy()
            fuel_arr = df_shifted['fuel'].to_numpy()

            # map the arrays to the indices in the netcdf file
            time_idx = nearest_index(aCCF_merged['time'].values, time_arr)
            lat_idx = nearest_index(aCCF_merged['latitude'].values, lat_arr)
            lon_idx = nearest_index(aCCF_merged['longitude'].values, lon_arr)
            lev_idx = nearest_index(aCCF_merged['level'].values, plev_arr)

            impact_vals = aCCF_merged.values[
                time_idx, lev_idx, lat_idx, lon_idx
            ]

            CO2_vals = co2_data.values[
                time_idx, lev_idx, lat_idx, lon_idx
            ]

            if hotspot_data is not None:
                hotspot_vals = hotspot_data.values[
                    time_idx, lev_idx, lat_idx, lon_idx
                ]

            CO2_total = fuel_arr * CO2_vals
            CO2tot = sum(CO2_total)
            EI_total = fuel_arr * impact_vals
            ei_sum = sum(EI_total)

            if hotspot_data is not None:
                hot_o = sum(hotspot_vals)
            else:
                hot_o = None
            res.append({
                'date': day,
                'hour': hour,
                'EI, [K]': ei_sum,
                'CO2_impact, [K]}': CO2tot,
                'hotspot': hot_o,
            })

    res = pd.DataFrame(res)

    return res


def compute_all_flights_emissions(df_trajs, climate_file_path=None, col_id='tact_id') -> pd.DataFrame:
    climate_data = load_climate_impact_file(file_path=climate_file_path)

    flight_ids = list(df_trajs['tact_id'].unique())

    all_results = []
    for f in flight_ids:
        df_traj = df_trajs.loc[df_trajs[col_id]==f] #  .copy()

        res = compute_flight_emission(df_traj, climate_data)

        all_results.append(res)

    all_results = pd.concat(all_results, ignore_index=True)

    return all_results


if __name__=='__main__':
    traj_file_path = 'test/trajectories.csv'
    climate_file_path = "test/env_impact_data_from_climaccf/env_processed.nc"

    df_trajs = pd.read_csv(traj_file_path)

    all_results = compute_all_flights_emissions(df_trajs,
                                                climate_file_path=climate_file_path
                                                )

    save_output = 'test/emissions.csv'

    all_results.to_csv(save_output)

    print('Saved results in {}'.format(save_output))
