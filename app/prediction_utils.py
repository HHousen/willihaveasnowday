import datetime

used_features_list = ['Air Temperature Hour 13', 'Air Temperature Hour 22',
                      'Air Temperature Hour 12', 'Air Temperature Hour 21',
                      'Air Temperature Hour 11', 'SNWD', 'Air Temperature Hour 14',
                      'Air Temperature Hour 0', 'Air Temperature Hour 15',
                      'Air Temperature Hour 10', 'Air Temperature Hour 20',
                      'Air Temperature Hour 1', 'Air Temperature Hour 17',
                      'Air Temperature Hour 16', 'Air Temperature Hour 18',
                      'Air Temperature Hour 19', 'Air Temperature Hour 2',
                      'Air Temperature Hour 9', 'Air Temperature Hour 8',
                      'Air Temperature Hour 6', 'Air Temperature Hour 7',
                      'Air Temperature Hour 4', 'Air Temperature Hour 5', 'Dayofweek', 'Month',
                      'Year', 'Longitude', 'Number of Snowdays in Year', 'TAVG', 'TMAX', 'SNOW',
                      'Air Temperature Hour 3', 'TMIN',
                      'Present Weather Observation Precipitation Hour 23', 'Week',
                      'Present Weather Observation Intensity Hour 3', 'WT08', 'Dayofyear', 'AWND',
                      'Latitude', 'WT18', 'Liquid Precipitation Hour 4',
                      'Liquid Precipitation Hour 22', 'Liquid Precipitation Hour 16',
                      'Is_month_end', 'PRCP', 'Storm Start Time', 'Liquid Precipitation Hour 3',
                      'Liquid Precipitation Hour 19', 'Snow Depth Hour 3',
                      'Present Weather Observation Precipitation Hour 2', 'Is_month_start',
                      'Liquid Precipitation Hour 1',
                      'Present Weather Observation Intensity Hour 19', 'Storm End Time', 'WT05',
                      'Liquid Precipitation Hour 21', 'Snow Depth Hour 4',
                      'Liquid Precipitation Hour 20', 'WT01',
                      'Present Weather Observation Descriptor Hour 23',
                      'Present Weather Observation Precipitation Hour 16',
                      'Liquid Precipitation Hour 13',
                      'Present Weather Observation Precipitation Hour 22', 'State',
                      'Liquid Precipitation Hour 7', 'Liquid Precipitation Hour 6',
                      'Snow Accumulation Hour 18', 'WT03',
                      'Present Weather Observation Precipitation Hour 0',
                      'Liquid Precipitation Hour 9', 'Day',
                      'Present Weather Observation Precipitation Hour 1',
                      'Present Weather Observation Intensity Hour 20',
                      'Liquid Precipitation Hour 18',
                      'Present Weather Observation Intensity Hour 13',
                      'Present Weather Observation Precipitation Hour 21',
                      'Liquid Precipitation Hour 17',
                      'Present Weather Observation Descriptor Hour 1',
                      'Liquid Precipitation Hour 15', 'Liquid Precipitation Hour 2',
                      'Present Weather Observation Descriptor Hour 0',
                      'Present Weather Observation Intensity Hour 23',
                      'Liquid Precipitation Hour 14',
                      'Present Weather Observation Descriptor Hour 7',
                      'Present Weather Observation Descriptor Hour 14',
                      'Present Weather Observation Intensity Hour 15',
                      'Present Weather Observation Descriptor Hour 21',
                      'Present Weather Observation Descriptor Hour 18',
                      'Present Weather Observation Precipitation Hour 6',
                      'Present Weather Observation Descriptor Hour 20',
                      'Present Weather Observation Intensity Hour 8', 'Snow Depth Hour 16',
                      'Present Weather Observation Descriptor Hour 2']


def calculate_predication_date_offset():
    date = datetime.datetime.today()
    offset = 0
    weekend = date.weekday() == 5 or date.weekday() == 6
    if (not weekend) and date.hour >= 12:
        offset += 1
    while date.weekday() == 5 or date.weekday() == 6:
        date = date + datetime.timedelta(1)
        offset += 1

    return offset
