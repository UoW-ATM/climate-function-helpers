# Climate function helpers for ClimaCCF library

## 1. Setup

Install dependencies with the requirement file. With pip:

```
pip install -r requirements.txt
```

## 2. Composition

### 2.1 ERA5 to climate impact

Main entry point: `compute_climate_impact` function in `era5_to_cimate_impact.py`.

Given era5 data in `nc` format, produces an `.nc` file with climate impact of a given engine.

Typical use:

```python
compute_climate_impact(era5_input_path / mod_file,
                       era5_input_path / surface)
```

To run it you need a "mod" ERA5 files and a "surface" ERA5 file.

### 2.2 Hotspot computation (optional)

Main entry point: `compute_hotspots_from_climate_impact` from `hotspot_computation.py`

Given a climate impact file, creates an `.nc` file with one binary variables corresponding to hotspots.

Typical use:

```python
compute_hotspots_from_climate_impact(env_impact_file=output_of_first_step,
                                     threshold=1e-9,
                                     variable_name_for_threshold="aCCF_merged")
```

### 2.3 Compute trajectories (optional)

Main entry point: `compute_trajectories` in `lib/trajectory_construction`.

This is coming directly from the open library https://github.com/UoW-ATM/read_all_ft.

Compute trajectories based on DDR ALLFT+ data. Format in output is:

| Longitude | Latitude | FL | Timestamp | elapsed_time | GS | vertical_rate | fuel_flow | fuel | ifps_id | tact_id | origin | destination | ac_type | pressure_Level |
|-------|-----|------------| ------------|------------|------------|------------|------------|------------|------------|------------|------------|------------|------------|------------|
| 4.764166666666667 | 52.308055555555555 | 0.0 | 2019-09-01 19:22:00 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | AA17484092 | 697364 | EHAM | EKCH | B738 | 1013 |
|4.733055555555556 | 52.36361111111111 | 35.0 | 2019-09-01 19:23:12 | 72.0 | 176.0 | 2916.0 | 2.1596402493251556 | 155.49409795141122 | AA17484092 | 697364 | EHAM | EKCH | B738 | 891 |
|4.715277777777778 | 52.39527777777778 | 51.0 | 2019-09-01 19:23:37 | 25.0 | 289.0 | 3840.0 | 2.1114527125101987 | 52.786317812754966 | AA17484092 | 697364 | EHAM | EKCH | B738 | 839 |
| 4.719444444444445 | 52.439166666666665 | 70.0 | 2019-09-01 19:24:08 | 31.0 | 306.0 | 3677.0 | 2.0799385780489823 | 64.47809591951845 | AA17484092 | 697364 | EHAM | EKCH | B738 | 781 |

Typical use:

```python
compute_trajectories(allft_path=allft_path,
                         flight_ids=['697364'], # tactical ids of the flights to extract
                         output_path="trajectories.csv",
                         interpolation_distance_km=15)
```

### 2.4 Compute emissions

Main entry point: 

Typical use:

```python
df_trajs = pd.read_csv(traj_file_path)

all_results = compute_all_flights_emissions(df_trajs,
                                            climate_file_path=climate_file_path
                                            )

```

`traj_file_path` can be the output of the previous step, and needs in any case to have the format indicated there.
`climate_file_path` is the output of the first step


### 2.5 Pipelines

Convenient functions to compute everything at the same time.

Typical use:

```
compute_all_emissions_from_all_ft(era5_input_path=era5_input_path,
                                  era5_name_list=['DEC2019'], # to compute several files. The function will look for {era5_name_list}_mod.nc and {era5_name_list}_surface.nc.
                                  working_directory='test_pipeline_all_ft', # to put all output in the same place
                                  compute_hotspot=True,
                                  allft_path=allft_path,
                                  flight_ids=['697364'],
                                  )
```