import statistics
import datetime
import re
from collections import OrderedDict
from noaa_sdk import noaa
import pandas as pd
import numpy as np

def get_weather(zip_code, country='US', return_result_object=False):
    n = noaa.NOAA(user_agent="Snow Day Predictor <hayden@haydenhousen.com>")

    forecast_response = n.get_forecasts(zip_code, country, data_type=["grid", None], return_result_object=return_result_object)
    
    if return_result_object:
        (weather_data, text_weather), result_object = forecast_response
    else:
        weather_data, text_weather = forecast_response

    # text_weather = n.get_forecasts(zip_code, country, data_type=None)

    if return_result_object:
        return weather_data, text_weather, result_object
    return weather_data, text_weather


def avg(list_to_average):
    return sum(list_to_average) / len(list_to_average)

def combine_based_on_date(weather_data, combine_func=sum, return_dates=False):
    daily_values_lists = []
    dates = []
    previous_date = None

    for x in weather_data["values"]:
        current_date = datetime.datetime.fromisoformat(x["validTime"].split("/")[0])
        # Remove the time from the date
        current_date = current_date.replace(minute=0, hour=0, second=0, microsecond=0)
        if current_date != previous_date:
            previous_date = current_date
            daily_values_lists.append([x["value"]])
            dates.append(current_date)
        else:
            daily_values_lists[-1].append(x["value"])

    daily_values = [combine_func(x) for x in daily_values_lists]
    
    if return_dates:
        return daily_values, dates

    return daily_values

def get_values_list(weather_data):
    return [x["value"] for x in weather_data["values"]]

def get_date_details(date):
    # Inspired by fastai: https://github.com/fastai/fastai/blob/54a9e3cf4fd0fa11fc2453a5389cc9263f6f0d77/fastai/tabular/transform.py#L55
    date = pd.to_datetime(date)
    date_dict = {}
    attr = ['Year', 'Month', 'Week', 'Day', 'Dayofweek', 'Dayofyear', 'Is_month_end', 'Is_month_start', 
            'Is_quarter_end', 'Is_quarter_start', 'Is_year_end', 'Is_year_start']
    for n in attr:
        date_dict[n] = getattr(date, n.lower())
    return date_dict

def pad(manipulate, index=0):
    if len(manipulate[index]) not in (24, 0):
        if type(manipulate[index][0]) is str or manipulate[index][0] is None:
            current_day_median = statistics.mode(manipulate[index])
        else:
            current_day_median = statistics.median(manipulate[index])
        for _ in range(24 - len(manipulate[index])):
            manipulate[index].insert(0, current_day_median)

def generate_hourly(weather_data, name, scaling_factor=None):
    daily_values_lists = []
    if type(name) is dict and len(name) > 1:
        daily_values_lists = [[] for _ in name]
    previous_date = None

    if not weather_data["values"]:
        return [("{} Hour {}".format(name, i), [0] * 7) for i in range(24)]

    for element in weather_data["values"]:
        time, duration = element["validTime"].split("/")
        # If current element lasts for more than a day then convert days to hours for `duration`
        days_search = re.search(r'P(.*?)D', duration)
        if days_search:  # P5DT6H
            days = int(days_search.group(1))
            hours_search = re.search(r'T(.*?)H', duration)
            if hours_search:
                hours = int(hours_search.group(1))
            else:
                hours = 0
            duration = days * 24 + hours
        else:  # PT4H
            duration = int(re.search(r'T(.*?)H', duration).group(1))  # select the number of hours in strings like "PT1H"
        current_datetime = datetime.datetime.fromisoformat(time)

        current_date = current_datetime.replace(minute=0, hour=0, second=0, microsecond=0)
        if current_date != previous_date:
            previous_date = current_date
            for duration_idx in range(duration):
                if type(name) is dict:
                    for idx, (element_name, item) in enumerate(name.items()):
                        if duration_idx == 0 or duration_idx % 24 == 0:
                            daily_values_lists[idx].append([element["value"][0][element_name]])
                        else:
                            daily_values_lists[idx][-1].append(element["value"][0][element_name])
                else:
                    if duration_idx == 0 or duration_idx % 24 == 0:
                        daily_values_lists.append([element["value"]])
                    else:
                        daily_values_lists[-1].append(element["value"])
        else:
            for _ in range(duration):
                if type(name) is dict:
                    if len(daily_values_lists[0][-1]) == 24:
                        for idx, _ in enumerate(daily_values_lists):
                            daily_values_lists[idx].append([])
                    for idx, (element_name, item) in enumerate(name.items()):
                        daily_values_lists[idx][-1].append(element["value"][0][element_name])
                else:
                    if len(daily_values_lists[-1]) == 24:
                        daily_values_lists.append([])
                    daily_values_lists[-1].append(element["value"])
    
    # Apply scaling factor if it is set
    if scaling_factor:
        daily_values_lists = [[value * scaling_factor for value in values] for values in daily_values_lists]

    # Remove last day because it does not contain data for all hours
    if type(name) is dict:
        for idx, _ in enumerate(name):
            del daily_values_lists[idx][-1]
    # else:
    #     del daily_values_lists[-1]
    
    # Pad the first and last days to 24 entries (hours) by adding the median to the
    # beginning of the list,
    if type(name) is dict:
        for idx, (element_name, item) in enumerate(name.items()):
            manipulate = daily_values_lists[idx]
            pad(manipulate)
            pad(manipulate, -1)
    else:
        pad(daily_values_lists)
        pad(daily_values_lists, -1)
    
    # Make each element equal in length so it can be converted to numpy array and the axes
    # can be swapped. Inspired by https://stackoverflow.com/a/26224619.
    if type(name) is dict:
        for idx, _ in enumerate(name):
            length = max(map(len, daily_values_lists[idx]))
            daily_values_lists[idx] = [xi+[None]*(length-len(xi)) for xi in daily_values_lists[idx]]
    else:
        length = max(map(len, daily_values_lists))
        daily_values_lists = [xi+[None]*(length-len(xi)) for xi in daily_values_lists]

    # Swap last two (or only two) axes to convert from a list of days to a list of values
    # where each value is a list of the values for each day.
    daily_values_lists = np.swapaxes(np.array(daily_values_lists), -2, -1)

    if type(name) is dict:
        daily_values_lists = [("{} Hour {}".format(_name, i), x) for name_idx, _name in enumerate(name.values()) for i, x in enumerate(daily_values_lists[name_idx])]
    else:
        daily_values_lists = [("{} Hour {}".format(name, i), list(x)) for i, x in enumerate(daily_values_lists)]

    return daily_values_lists

def generate_text_descriptions(text_weather):
    final_dict = OrderedDict()
    for forecast_period in text_weather:
        final_dict[forecast_period["name"]] = {
            "name": forecast_period["name"],
            "shortForecast": forecast_period["shortForecast"],
            "detailedForecast": forecast_period["detailedForecast"],
            "startTime": forecast_period["startTime"]
        }

    return final_dict

def push_date_to_weekday(date):
    while date.weekday() == 5 or date.weekday() == 6:
        date = date + datetime.timedelta(1)
    return date

def create_weekdates(return_weekday_names=True, utc=False, return_offsets=False):
    if utc:
        today = datetime.datetime.now(datetime.timezone.utc)
    else:
        today = datetime.datetime.today()
    
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if today.hour >= 12:
        today = today + datetime.timedelta(1)

    today = push_date_to_weekday(today)
    tomorrow = today + datetime.timedelta(1)
    tomorrow = push_date_to_weekday(tomorrow)
    third_day = tomorrow + datetime.timedelta(1)
    third_day = push_date_to_weekday(third_day)

    dates = [today, tomorrow, third_day]

    if return_offsets:
        today = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        offsets = [(date - today).days for date in dates]

    if return_weekday_names:
        dates = [date.strftime('%A') for date in dates]

    if return_offsets:
        return dates, offsets

    return dates

def process_text_descriptions(text_descriptions, days_to_keep=None):
    if days_to_keep is None:
        days_to_keep = create_weekdates(return_weekday_names=False, utc=True)

    text_descriptions = list(text_descriptions.items())

    final_list = []
    index = 0
    offset = 0
    for day in days_to_keep:
        text_descriptions = text_descriptions[offset:]
        offset = 0
        for idx, (period_name, data) in enumerate(text_descriptions):
            period_date = datetime.datetime.fromisoformat(data["startTime"])
            time_distance = (period_date - day).days
            
            if time_distance == 0:
                del data["startTime"]
                
                try:
                    final_list[index].append(data)
                except IndexError:
                    final_list.append([data])
                
                offset = idx + 1
            
            elif time_distance > 0:
                index += 1
                break
    
    return final_list

def translate_hourly_observation_data(hourly_observation_data):
    """Prepare the ``hourly_observation_data`` for input to ML model."""
    # Translators based on the NOAA degrib specification (https://www.weather.gov/mdl/degrib_ndfdwx)
    # and the ISD Format Document
    hourly_observation_data = dict(hourly_observation_data)
    intensity_translator = {None: 0, "very_light": 1, "light": 1, "moderate": 2, "heavy": 3}
    columns = ["Present Weather Observation Intensity Hour {}".format(x) for x in range(24)]
    for column in columns:
        hourly_observation_data[column] = [intensity_translator[x] if x in intensity_translator else np.nan for x in hourly_observation_data[column]]

    columns = ["Present Weather Observation Descriptor Hour {}".format(x) for x in range(24)]

    # Copy the list of descriptor data before translation so it can be used in
    # `translate_daily_weather_type_lists()`
    descriptor_data_decoded = {key: value for (key, value) in hourly_observation_data.items() if key in columns}

    precip_columns = ["Present Weather Observation Precipitation Hour {}".format(x) for x in range(24)]
    precip_translator = {None: 0, "drizzle": 1, "freezing_drizzle": 1, "rain": 2, "rain_showers": 2, "thunderstorms": 2, "freezing_rain": 2, "snow": 3, "snow_showers": 4, "ice_crystals": 5, "ice_pellets": 6}
    descriptor_translator = {None: 0, "blowing_dust": 5, "blowing_snow": 5, "snow_showers": 6, "rain_showers": 6, "thunderstorms": 7, "freezing_rain": 8, "freezing_drizzle": 8}
    for column, precip_column in zip(columns, precip_columns):
        # Create copy of Descriptor items
        hourly_observation_data[precip_column] = [precip_translator[x] if x in precip_translator else np.nan for x in hourly_observation_data[column]]
        hourly_observation_data[column] = [descriptor_translator[x] if x in descriptor_translator else np.nan for x in hourly_observation_data[column]]

    return hourly_observation_data, descriptor_data_decoded

def create_daily_weather_type_lists(descriptor_data_decoded):
    descriptor_data_decoded = dict(descriptor_data_decoded)
    all_daily_values_list = []
    
    only_precip_lists = [descriptor_data_decoded[x] for x in descriptor_data_decoded]
    
    num_days = min([len(x) for x in only_precip_lists])
    for day in range(num_days):
        daily_values_list = []

        for precip_column in descriptor_data_decoded:
            current_day_hour_info = descriptor_data_decoded[precip_column][day]
            daily_values_list.append(current_day_hour_info)

        all_daily_values_list.append(daily_values_list)
    
    return all_daily_values_list

def translate_daily_weather_type_lists(days):
    average_weather_type_translator = {"fog": "WT01", "ice_fog": "WT01", "freezing_fog": "WT01", "thunderstorms": "WT03", "ice_pellets": "WT05", "haze": "WT08", "smoke": "WT08", "drizzle": "WT13", "rain": "WT16", "rain_showers": "WT16", "freezing_drizzle": "WT16", "freezing_rain": "WT16", "snow": "WT18", "snow_showers": "WT18", "ice_crystals": "WT18", "blowing_snow": "WT18"}
    average_weather_types = {"WT01": [], "WT03": [], "WT05": [], "WT08": [], "WT13": [], "WT16": [], "WT18": []}
    
    for daily_values_list in days:
        weather_types_found = []
        for x in daily_values_list:
            if x in average_weather_type_translator:
                to_append_key = average_weather_type_translator[x]
                weather_types_found.append(to_append_key)
        
        # Remove duplicates
        weather_types_found = set(weather_types_found)

        for weather_type in weather_types_found:
            average_weather_types[weather_type].append(1)
        not_found_weather_types = [x for x in average_weather_types if x not in weather_types_found]
        for weather_type in not_found_weather_types:
            average_weather_types[weather_type].append(0)

    return average_weather_types

def add_storm_times(row):
    storm_start = None
    storm_end = None
    no_storm = False
    last_storm_idx = None
    
    for idx, col in enumerate(row):
        if col == 0:
            no_storm = True
        if col > 0:
            last_storm_idx = idx
        if col > 0 and not storm_start and not storm_start == 0:
            storm_start = idx
        if (storm_start or storm_start == 0) and col == 0 and idx > last_storm_idx+1:
            storm_end = idx-1
            break
    
    if not storm_start and not storm_start == 0:
        if no_storm:
            return -1, -1
        else:
            return np.nan, np.nan
    
    if (storm_start or storm_start == 0) and (not storm_end):
        storm_end = 23
    
    return storm_start, storm_end

def make_times(num_days):
    today = datetime.datetime.today().replace(minute=0, hour=0, second=0, microsecond=0)
    return [int((today + datetime.timedelta(day)).timestamp()) for day in range(num_days)]

def prepapre_model_inputs(weather_data, extra_info=None, truncate=True, used_features_list=None):
    daily_precipitation, dates = combine_based_on_date(weather_data["quantitativePrecipitation"], return_dates=True)
    daily_snowfall = combine_based_on_date(weather_data["snowfallAmount"])
    daily_snowlevel = combine_based_on_date(weather_data["snowLevel"])
    daily_maxtemp = get_values_list(weather_data["maxTemperature"])
    daily_mintemp = get_values_list(weather_data["minTemperature"])
    daily_avgtemp = combine_based_on_date(weather_data["temperature"], combine_func=avg)
    daily_avg_wind_speed = combine_based_on_date(weather_data["windSpeed"], combine_func=avg)
    hourly_temp = generate_hourly(weather_data["temperature"], name="Air Temperature", scaling_factor=10)  # model expects celsius (scale 10)
    hourly_snow_depth = generate_hourly(weather_data["snowLevel"], name="Snow Depth", scaling_factor=0.1)  # model expects cm (scale 1)
    hourly_snow_accumulation = generate_hourly(weather_data["snowfallAmount"], name="Snow Accumulation", scaling_factor=0.1)  # model expects cm (scale 1) but NOAA gives mm
    hourly_liquid_precipitation = generate_hourly(weather_data["quantitativePrecipitation"], name="Liquid Precipitation", scaling_factor=10)  # model expects mm (scale 10)
    hourly_observation_data = generate_hourly(weather_data["weather"], name={"weather": "Present Weather Observation Descriptor", "intensity": "Present Weather Observation Intensity"})

    # Convert `hourly_observation_data` from degrib text values
    # (https://www.weather.gov/mdl/degrib_ndfdwx) to ISD Present Weather Observation
    # (indication AU1) codes. Also create `descriptor_data_decoded`, which contains the
    # values with keys "Present Weather Observation Descriptor Hour 0-23" from
    # `hourly_observation_data` (these are the values of the "weather" key in NOAA's
    # API response)
    hourly_observation_data, descriptor_data_decoded = translate_hourly_observation_data(hourly_observation_data)

    # Reformat the `descriptor_data_decoded` from hour (rows) by day (columns) to
    # day (rows) by hour (columns).
    daily_weather_type_list = create_daily_weather_type_lists(descriptor_data_decoded)
    
    # Translate list of lists where each list contains the weather observations for the
    # coresponding day (for example list 0 is day 0) to dictionary with the weather type
    # keys ("WT01", "WT03", etc.) as keys and the values as lists. Each list contains
    # the values for one weather type but for all days. For instance, the value 0 of all
    # items in the dict coresponds to day 0. A value of 1 in a weather type for a day means
    # that that weather type was present on that day. A value of 0 means it was not present.
    daily_weather_types_final = translate_daily_weather_type_lists(daily_weather_type_list)
    
    # Create date details
    all_date_details = [get_date_details(date) for date in dates]
    # Next line inspired by https://stackoverflow.com/a/33046935
    all_date_details_dict = {k: [dic[k] for dic in all_date_details] for k in all_date_details[0]}

    # Create storm start and end times
    columns = ["Present Weather Observation Precipitation Hour {}".format(x) for x in range(24)]
    precip_columns = pd.DataFrame(hourly_observation_data)
    precip_columns = precip_columns[columns]
    storm_times = precip_columns.apply(add_storm_times, axis=1)
    storm_times = {"Storm Start Time": [x[0] for x in storm_times.values], "Storm End Time": [x[1] for x in storm_times.values]}

    model_inputs = {
        "Elapsed": make_times(7),
        "PRCP": [x*10 for x in daily_precipitation],  # tenths of mm
        "SNOW": daily_snowfall,  # model expects mm and NOAA gives mm
        "SNWD": daily_snowlevel,  # model expects mm
        "TMAX": [x*10 for x in daily_maxtemp],  # tenths of degrees C
        "TMIN": [x*10 for x in daily_mintemp],  # tenths of degrees C
        "TAVG": [x*10 for x in daily_avgtemp],  # tenths of degrees C
        "AWND": [(x/3.6)*10 for x in daily_avg_wind_speed],  # tenths of meters per second (convert from km/h to m/s then convert to tenths)
        **all_date_details_dict,
        **dict(hourly_temp),
        **dict(hourly_snow_depth),
        **dict(hourly_snow_accumulation),
        **dict(hourly_liquid_precipitation),
        **dict(hourly_observation_data),
        **dict(daily_weather_types_final),
        **dict(storm_times),
    }

    # Fill empty values (most likely will only will SNWD)
    model_inputs = {key: value if len(value) > 0 else [np.nan]*10 for (key, value) in model_inputs.items()}
    
    if extra_info:
        model_inputs = {**model_inputs, **extra_info}

    model_input_lengths = [x for key, value in model_inputs.items() if type(value) is list and (x := len(value)) != 0]

    min_num_days = min(model_input_lengths)

    if truncate:
        for key in model_inputs:
            if type(model_inputs[key]) is list:
                model_inputs[key] = model_inputs[key][:min_num_days]

    if used_features_list:
        model_inputs = {key: model_inputs[key] for key in used_features_list if key != "Number of Snowdays in Year"}
    
    return model_inputs

# import joblib
# import sys, os
# sys.path.insert(1, os.path.join(sys.path[0], '..'))
# from prediction_utils import used_features_list

# weather_data, text_weather, result_object = get_weather("12564", return_result_object=True)

# period_text_descriptions = generate_text_descriptions(text_weather)
# period_text_descriptions = process_text_descriptions(period_text_descriptions)

# extra_info = {"Latitude": result_object.lat, "Longitude": result_object.lng, "State": result_object.state}
# model_inputs = prepapre_model_inputs(weather_data, extra_info, used_features_list)

# model = joblib.load("/home/hhousen/Downloads/model2.joblib")
# print(model.classes_)

# model_inputs["Number of Snowdays in Year"] = [2] * len(model_inputs[used_features_list[0]])
# model_inputs = pd.DataFrame(model_inputs)[used_features_list]

# prediction_proba = model.predict_proba(model_inputs)

# print(prediction_proba[0][0])
