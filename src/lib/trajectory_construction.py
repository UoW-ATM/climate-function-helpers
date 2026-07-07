#This is temporary explanation, 27 May 2025 The below code is adaptation of Majid's code
# this script first concatenates the all_ft+ files that are needed (depending on the period one wants to analyse
# This can take a while - and that is with choosing only certain columns
# Then the file that contains flight ids chosen for certain scenarios is taken - this identifies which trajectories we want to use
# Those trajectories are then loaded, added interpolation points, pressure level, vertical rate, ground speed, time gap and fuel
# this is rather fast now - 80 seconds for 130 trajectories
# Two csv files are created - one contains the metadata on trajectories (origin, destination, ac_type and tact_id),
# and the other one contains all the trajectories, with the interpolation points added and calculated ground_speed and time elapsed between two trajectory points.

import warnings
import os
import glob
import time
from pathlib import Path
import re
import numpy as np
import pandas as pd
from geopy.distance import geodesic
from datetime import timedelta
import openap
from matplotlib.path import Path as MatPath

from read_all_ft.read_all_ft_functions import read_all_ft_formatted
from read_all_ft.read_trajectories import extract_trajectory

##MTOW of aircraft types encountered in August 2019, copied from CRCO file (TB to specify which files exactly)
# TO DO to change this to load the file - maybe from args
aircraft_mtow = {
    'A318': 68000,  # Airbus A318
    'A319': 70000,  # Airbus A319
    'A320': 77000,  # Airbus A320
    'A321': 83000,  # Airbus A321
    'A20N': 79000,  # Airbus A320neo   *
    'A21N': 89000,  # Airbus A321neo   *
    'A306': 171700,  # Airbus A300-600
    'A332': 230000,  # Airbus A330-200
    'A333': 212000,  # Airbus A330-300
    'A343': 276500,  # Airbus A340-300
    'A346': 365000,  # Airbus A340-600
    'A359': 275000,  # Airbus A350-900
    'B733': 62800,  # Boeing 737-300
    'B734': 68000,  # Boeing 737-400
    'B735': 60680,  # Boeing 737-500
    'B737': 70080,  # Boeing 737-700
    'B738': 78300,  # Boeing 737-800
    'B739': 85139,  # Boeing 737-900
    'B752': 115900,  # Boeing 757-200
    'B763': 186880,  # Boeing 767-300ER
    'B772': 287000,  # Boeing 777-200ER
    'B77L': 347450,  # Boeing 777-200LR
    'B77W': 351530,  # Boeing 777-300ER
    'B788': 227930,  # Boeing 787-8
    'B789': 250830,  # Boeing 787-9
    'B744': 396800,  # Boeing 747-400
    'CRJ9': 38000,  # Bombardier CRJ900
    'CRJX': 38000,  # Bombardier CRJ1000
    'E145': 22000,  # Embraer ERJ145
    'E190': 50300,  # Embraer ERJ190
    'E195': 52290,  # Embraer 195
    'C525': 4800,  # Cessna CitationJet CJ1
    'C56X': 9163,  # Cessna Citation Excel
    'C560': 7212,  # Cessna Citation V
    'C680': 13744,  # Cessna Citation Sovereign
    'C68A': 13744,  # Cessna Citation Latitude
    'C750': 16193,  # Cessna Citation X
    'CL35': 17962,  # Bombardier Challenger 350
    'F2TH': 19142,  # Dassault Falcon 2000
    'GLEX': 45132,  # Bombardier Global Express
    'GLF5': 41277,  # Gulfstream G550
    'H25B': 12701,  # Hawker 800XP
    'P180': 5489  # Piaggio P.180 Avanti
}


##Functions needed
def calculate_pressure(FL):
    """
    P0 = 1013.25  # Sea level standard pressure in hPa
    T0 = 288.15   # Sea level standard temperature in Kelvin
    L = 0.0065    # Temperature lapse rate in K/m
    R = 287.05    # Specific gas constant for dry air in J/(kg·K)
    g = 9.80665   # Gravitational acceleration in m/s^2
    """
    # Convert flight level to altitude in meters (1 FL = 100 feet)
    altitude = FL * 100 * 0.3048  # in meters
    # Pressure formula for the troposphere (below 11 km / 36,089 ft)
    if altitude <= 11000:
        pressure = 1013.25 * (1 - (0.0065 * altitude) / 288.15)**(9.80665 / (287.05 * 0.0065))
    # Above 11 km, temperature is constant (-56.5°C or 216.65 K)
    else:
        T_tropopause = 288.15 - 0.0065 * 11000
        P_tropopause = 1013.25 * (1 - (0.0065 * 11000) / 288.15)**(9.80665 / (287.05 * 0.0065))
        pressure = P_tropopause * np.exp(-9.80665 * (altitude - 11000) / (287.05 * T_tropopause))
    return pressure


# --- Main function to compute time and speed and vertical rate---
def compute_speed_vs_time(df):
    """
    calculate ground speed (GS) in knots and time difference between each point in the trajectory
    """

    # Parse Timestamp (assuming format YYYYMMDDhhmmss)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%Y%m%d%H%M%S')

    # Sort by time just in case
    df = df.sort_values('Timestamp').reset_index(drop=True)

    # Time difference in seconds
    df['gap'] = df['Timestamp'].diff().dt.total_seconds()

    # Distance in km between each point and the previous
    # Compute speed in knots
    df['GS'] = [int((geodesic((df.loc[i - 1, 'Latitude'], df.loc[i - 1, 'Longitude']),
                              (df.loc[i, 'Latitude'], df.loc[i, 'Longitude'])).nm
                     / df.loc[i, 'gap']) * 3600)

                if i > 0 else np.nan
                for i in range(len(df))
                ]
    # compute vertical speed
    df['vertical_rate'] = [int((((df.loc[i, 'FL'] - df.loc[i - 1, 'FL']) * 100) / df.loc[i, 'gap']) * 60)
                           if i > 0 else np.nan
                           for i in range(len(df))]

    # Set first point to zero instead of NaN
    df['gap'] = df['gap'].fillna(0)
    df['GS'] = df['GS'].fillna(0)
    df['vertical_rate'] = df['vertical_rate'].fillna(0)

    return df


#function to add points into the trajectory to have points at 'distance_km' distance along the trajectory
#as sometimes rather large segments are in the data
def interpolate_points_with_timestamps(df, distance_km):
    """
    Interpolate points along a trajectory with a fixed distance between them, including estimated timestamps.

    Parameters:
        df (pd.DataFrame): Original dataframe with Longitude, Latitude, Altitude, and Timestamp.
        distance_km (float): Desired distance between consecutive points (in kilometers).

    Returns:
        pd.DataFrame: New dataframe with interpolated points and estimated timestamps.
    """
    # Initialize new dataframe
    new_points = []

    # Convert Timestamps to datetime objects
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%Y%m%d%H%M%S')

    # Iterate over points in the dataframe
    for i in range(len(df) - 1):
        # Get the start and end points
        start = (df.loc[i, 'Latitude'], df.loc[i, 'Longitude'])
        end = (df.loc[i + 1, 'Latitude'], df.loc[i + 1, 'Longitude'])
        start_alt = df.loc[i, 'FL']
        end_alt = df.loc[i + 1, 'FL']
        start_time = df.loc[i, 'Timestamp']
        end_time = df.loc[i + 1, 'Timestamp']

        # Calculate the distance and time duration between start and end
        segment_distance = geodesic(start, end).km
        segment_duration = (end_time - start_time).total_seconds()

        # If the segment distance is smaller than the desired distance, add the start point
        if segment_distance < distance_km:
            new_points.append((start[1], start[0], start_alt,
                               start_time.strftime('%Y%m%d%H%M%S')))  # (Longitude, Latitude, Altitude, Timestamp)
            continue

        # Interpolate points along the segment
        num_points = int(segment_distance // distance_km)
        for j in range(num_points):
            # Interpolation factor
            t = (j + 1) * distance_km / segment_distance

            # Interpolate latitude, longitude, altitude, and time
            interp_lat = start[0] + t * (end[0] - start[0])
            interp_lon = start[1] + t * (end[1] - start[1])
            interp_alt = start_alt + t * (end_alt - start_alt)
            interp_time = start_time + timedelta(seconds=t * segment_duration)

            new_points.append((interp_lon, interp_lat, interp_alt, interp_time.strftime('%Y%m%d%H%M%S')))

    # Add the last point of the trajectory
    last_point = (df.loc[len(df) - 1, 'Longitude'],
                  df.loc[len(df) - 1, 'Latitude'],
                  df.loc[len(df) - 1, 'FL'],
                  df.loc[len(df) - 1, 'Timestamp'].strftime('%Y%m%d%H%M%S'))
    new_points.append(last_point)

    # Convert to dataframe
    new_df = pd.DataFrame(new_points, columns=['Longitude', 'Latitude', 'FL', 'Timestamp'])
    return new_df


# Function to return the MTOW from the three-letter aircraft type code
def get_mtow(aircraft_code):
    """
    Returns the Maximum Takeoff Weight (MTOW) for the given aircraft code.

    Parameters:
    aircraft_code (str): The code of the aircraft model.

    Returns:
    int: MTOW in kilograms if the aircraft code is found.
    None: If the aircraft code is not found.
    """
    aircraft_code = aircraft_code.upper()
    if aircraft_code in aircraft_mtow:
        return aircraft_mtow[aircraft_code]
    else:
        return None


# fuel flow and fuel calculation
def fuel_flow(ac_type, mass, df_traj):
    with warnings.catch_warnings(record=True) as w:
        fuelflow = openap.FuelFlow(ac=ac_type, use_synonym=True)

    if w:
        # Get the first warning (all should be for the same ac swap type)
        # but we get ac type change, polar change, etc.
        warn = w[0]
        print(f"** Warning caught in OpenAP: {warn.message}")
        msg = str(warn.message)
        match = re.search(r"using synonym (\w+) for (\w+)", msg)
        if match:
            ac_used = match.group(1)
            ac_tried = match.group(2)
            print(f"    ac_type = {ac_type}, ac_used = {ac_used}, ac_tried = {ac_tried}")

    mass_current = mass

    fuelflow_every_step = []
    fuel_every_step = []

    for i, row in df_traj.iterrows():
        if row.GS == 0:
            ff = 0.
        else:
            ff = fuelflow.enroute(
                mass=mass_current,  # in kg
                tas=row.GS,  # in kts
                alt=row.FL * 100,  # in ft
                vs=row.vertical_rate,  # ft/min
            )

        # print('Mass at step', i, mass_current)
        # print('GS at step', i, row.GS)
        # print('Alt at step', i, row.FL * 100)
        # print('Vert. rate at step', i, row.vertical_rate)
        # print('Fuel flow at step', i, ff)
        # print()

        if ff < 0:
            pass
            #print("-->", ac_type, ff, mass, mass_current, row.GS, row.FL, row.vertical_rate)
            #print("----->", (65000, 300, row.FL * 100, row.vertical_rate))
            #print("----->", fuelflow.enroute(mass=65000, tas=300, alt=row.FL * 100, vs=row.vertical_rate+1000))
            #print("----->", (65000, 350, row.FL * 100, row.vertical_rate))
            #print("----->", fuelflow.enroute(mass=65000, tas=350, alt=row.FL * 100, vs=row.vertical_rate+1000))
            #print("----->", (65000, 400, row.FL * 100, row.vertical_rate))
            #print("----->", fuelflow.enroute(mass=65000, tas=400, alt=row.FL * 100, vs=row.vertical_rate+1000))
            #print("----->", (65000, 455, row.FL*100, row.vertical_rate))
            #print("----->", fuelflow.enroute(mass=65000, tas=455, alt=row.FL*100, vs=row.vertical_rate+1000))
        fuel = ff * row.gap  # kg/sec
        fuelflow_every_step.append(ff)
        fuel_every_step.append(ff * row.gap)  # kg
        mass_current -= fuel

    df_traj = df_traj.assign(fuel_flow=fuelflow_every_step, fuel=fuel_every_step)
    return df_traj


def compute_trajectories(allft_path=None, flight_ids=None, output_path=None, interpolation_distance_km=15):
    ### Have a path to all_ft+ files here
    # allft_path='./all_ft/' #path to one or multiple ft+files
    ### a path to the file with the flight ids, which are actually tact_ids that need to be extracted
    # id_path = './Scenario_big_real10_pa/flight_ids_big_real10_pa.csv'
    #
    # ids=pd.read_csv(id_path)

    # ids_extract=list(ids['FlightID'])

    ### distance for interpolation

    # start_time = time.time()  # Start timing
    ## getting all the all_ft+ files into one dataframe and deleting duplicates

    files = glob.glob(os.path.join(allft_path, "*.ALL_FT+"))
    dfs = []
    # id_list = []

    flight_ids = np.array(flight_ids).astype(int)

    for f in files:
        print('Reading ALLFT+ file...', f)
        df_all_ft = read_all_ft_formatted(f, columns=['origin', 'destination', 'ac_id', 'operator', 'ac_type', 'tact_id', 'ftfmAllFtPointProfile',
                               'ftfmConsumedFuel', 'ftfmRouteCharges', 'ifps_id'])
        # df_all_ft = df_all_ft[['origin', 'destination', 'ac_id', 'operator', 'ac_type', 'tact_id', 'ftfmAllFtPointProfile',
        #                        'ftfmConsumedFuel', 'ftfmRouteCharges']] #keep only few columns needed to reduce file size and time
        # print('A few tact IDs:\n', df_all_ft.iloc[:10]['tact_id'])
        df_all_ft = df_all_ft[df_all_ft.tact_id.isin(flight_ids)]
        dfs.append(df_all_ft)

    dfs = pd.concat(dfs, ignore_index=True)
    dfs = dfs.drop_duplicates(subset='tact_id', keep='first')

    if len(dfs)==0:
        raise Exception('No trajectories found in ALLFT+ file with these ids')

    # end_time = time.time()  # End timing
    # print(f"All_ft+ read Execution time: {end_time - start_time:.6f} seconds")
    #
    # #Extract certain trajectories
    # start_time = time.time()  # Start timing

    # Filter from the ALl_FT the rows of flights which are within ids_extract
    # dfs = dfs[dfs.tact_id.isin(flight_ids)]

    # Add aircraft and trajectory dataframe
    # print(dfs)
    # row = dfs.iloc[0]
    # print('COIENOINE\n', row['ifps_id'], row.to_frame().T)
    # print()
    # coin = extract_trajectory(row['ifps_id'],
    #                                                                                         row.to_frame().T,
    #                                                                                         traj_type='ftfm')
    # print(coin)
    # print()
    # print(len(coin))


    # dfs[['aircraft', 'df_trajectory']] = dfs.apply(lambda row: pd.Series(extract_trajectory(row['ifps_id'],
    #                                                                                         row.to_frame().T,
    #                                                                                         traj_type='ftfm')
    #                                                                      ),
    #                                                axis=1)
    df_trajs = []

    for i, row in dfs.iterrows():
        df_traj = extract_trajectory(row['ifps_id'],
                                     row.to_frame().T,
                                     traj_type='ftfm'
                                     )
        mass = get_mtow(row['ac_type'])
        # print('\n\ndf_traj 1:\n', df_traj)
        df_traj = interpolate_points_with_timestamps(df_traj, interpolation_distance_km)
        # print('\n\ndf_traj 2:\n', df_traj)
        df_traj = compute_speed_vs_time(df_traj)
        # print('\n\ndf_traj 3:\n', df_traj)

        # df_traj = df_traj.apply(lambda x: interpolate_points_with_timestamps(x, interpolation_distance_km))
        # df_traj = df_traj.apply(lambda x: compute_speed_vs_time(x))
        # df_traj = compute_speed_vs_time(df_traj)

        # print('MASS:', mass)

        df_traj = fuel_flow(row['ac_type'], mass, df_traj)

        # print('\n\ndf_traj 4:\n', df_traj)

        # df_traj.apply(lambda row: fuel_flow(row['ac_id'], df_traj['mass'].iloc[0], df_traj), axis=1)
        df_traj['ifps_id'] = row['ifps_id']
        df_traj['tact_id'] = row['tact_id']
        df_traj['origin'] = row['origin']
        df_traj['destination'] = row['destination']
        df_traj['ac_type'] = row['ac_type']

        df_trajs.append(df_traj)

    df_trajs = pd.concat(df_trajs, ignore_index=True)
    df_trajs['pressure_Level'] = df_trajs['FL'].apply(calculate_pressure).astype(int)

    # dfs['df_trajectory']= dfs.apply(lambda row: pd.Series(extract_trajectory(row['ifps_id'],
    #                                                                                         row.to_frame().T,
    #                                                                                         traj_type='ftfm')
    #                                                                      ),
    #                                                axis=1)
    # Add mass
    # dfs['mass'] = dfs['aircraft'].apply(lambda x: get_mtow(x))

    # Interpolate points in trajectory
    # dfs['df_trajectory'] = dfs['df_trajectory'].apply(lambda x: interpolate_points_with_timestamps(x, interpolation_distance_km))
    #
    # # Compute speed and times for trajectory points
    # dfs['df_trajectory'] = dfs['df_trajectory'].apply(lambda x: compute_speed_vs_time(x))

    # Computes fuel flow
    # dfs['df_trajectory'] = dfs.apply(lambda row: fuel_flow(row['aircraft'], row['mass'], row['df_trajectory']), axis=1)

    # Add tact_id to trajectory dataframe
    # def inject_tact_id(row):
    #     row['df_trajectory']['tact_id'] = row['tact_id']
    #     return row

    # dfs = dfs.apply(inject_tact_id, axis=1)

    # # Extract trajectory dataframes for all rows
    # df_trajectory = pd.concat(list(dfs['df_trajectory']))

    # # Add pressure level
    # df_trajectory['pressure_Level'] = df_trajectory['FL'].apply(calculate_pressure).astype(int)

    #  Get metadata and save it
    # metadata_df = dfs[['origin', 'destination', 'ac_type', 'tact_id']]
    # metadata_df.to_csv('metadata.csv', index=False)

    # Save trajectory dataframe
    print('Trajectories saved in', output_path)
    output_path = Path(output_path)
    output_path.resolve().parents[0].mkdir(parents=True, exist_ok=True)
    df_trajs.to_csv(output_path, index=False)

    # # dfs.to_csv('./dfs.csv')
    # end_time = time.time()  # End timing
    #
    # print(f"Execution time: {end_time - start_time:.6f} seconds"


if __name__ == '__main__':

    compute_trajectories(allft_path="/home/earendil/Documents/Westminster/Libraries/test data",
                         flight_ids=['697364'], # '681253'],
                         output_path="test/trajectories.csv",
                         interpolation_distance_km=15)
