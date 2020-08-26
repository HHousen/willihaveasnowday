import datetime

used_features_list = ['Air Temperature Hour 23',
                      'Air Temperature Hour 14',
                      'Air Temperature Hour 13',
                      'Air Temperature Hour 22',
                      'Air Temperature Hour 0',
                      'Air Temperature Hour 12',
                      'Air Temperature Hour 15',
                      'Air Temperature Hour 1',
                      'Air Temperature Hour 16',
                      'Air Temperature Hour 11',
                      'Air Temperature Hour 21',
                      'Air Temperature Hour 2',
                      'Air Temperature Hour 18',
                      'Air Temperature Hour 17',
                      'Air Temperature Hour 20',
                      'Air Temperature Hour 19',
                      'Air Temperature Hour 3',
                      'Air Temperature Hour 10',
                      'Air Temperature Hour 9',
                      'Air Temperature Hour 8',
                      'Air Temperature Hour 7',
                      'Air Temperature Hour 5',
                      'Air Temperature Hour 6',
                      'Dayofyear',
                      'Week',
                      'Month',
                      'Number of Snowdays in Year',
                      'TMAX',
                      'SNOW',
                      'TMIN',
                      'SNWD',
                      'Air Temperature Hour 4',
                      'PRCP',
                      'Year',
                      'Day',
                      'Present Weather Observation Intensity Hour 4',
                      'WT18',
                      'Longitude',
                      'Elapsed',
                      'TAVG',
                      'Liquid Precipitation Hour 5',
                      'Liquid Precipitation Hour 23',
                      'WT01',
                      'Liquid Precipitation Hour 17',
                      'AWND',
                      'Liquid Precipitation Hour 4',
                      'Liquid Precipitation Hour 20',
                      'Snow Depth Hour 4',
                      'WT03',
                      'Liquid Precipitation Hour 2',
                      'Present Weather Observation Precipitation Hour 3',
                      'Present Weather Observation Intensity Hour 20',
                      'Latitude',
                      'Snow Depth Hour 5']


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
