import statistics
import datetime
from collections import OrderedDict
from noaa_sdk import noaa
import pandas as pd
import numpy as np

def get_weather(zip_code, country='US'):
    n = noaa.NOAA(user_agent="Snow Day Predictor <hayden@haydenhousen.com>")

    weather_data = n.get_forecasts(zip_code, country)
    text_weather = n.get_forecasts(zip_code, country, data_type=None)

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

def pad(manipulate):
    if len(manipulate[0]) not in (24, 0):
        if type(manipulate[0][0]) is str or manipulate[0][0] is None:
            current_day_median = statistics.mode(manipulate[0])
        else:
            current_day_median = statistics.median(manipulate[0])
        for _ in range(24 - len(manipulate[0])):
            manipulate[0].insert(0, current_day_median)

def generate_hourly(weather_data, name):
    daily_values_lists = []
    if type(name) is dict and len(name) > 1:
        daily_values_lists = [[] for _ in name]
    previous_date = None

    for element in weather_data["values"]:
        time, duration = element["validTime"].split("/")
        # Skip current element if it lasts for more than a day
        if "D" in duration:
            continue

        duration = int(duration[2:3])  # select the number of hours in strings like "PT1H"
        current_datetime = datetime.datetime.fromisoformat(time)

        current_date = current_datetime.replace(minute=0, hour=0, second=0, microsecond=0)
        if current_date != previous_date:
            previous_date = current_date
            for duration_idx in range(duration):
                if type(name) is dict:
                    for idx, (element_name, item) in enumerate(name.items()):
                        if duration_idx == 0:
                            daily_values_lists[idx].append([element["value"][0][element_name]])
                        else:
                            daily_values_lists[idx][-1].append(element["value"][0][element_name])
                else:
                    if duration_idx == 0:
                        daily_values_lists.append([element["value"]])
                    else:
                        daily_values_lists[-1].append(element["value"])
        else:
            for _ in range(duration):
                if type(name) is dict:
                    for idx, (element_name, item) in enumerate(name.items()):
                        daily_values_lists[idx][-1].append(element["value"][0][element_name])
                else:
                    daily_values_lists[-1].append(element["value"])
    
    # Remove last day because it does not contain data for all hours
    if type(name) is dict:
        for idx, _ in enumerate(name):
            del daily_values_lists[idx][-1]
    else:
        del daily_values_lists[-1]
    
    # Pad the first day to 24 entries (hours) by adding the median to the beginning of the list
    if type(name) is dict:
        for idx, (element_name, item) in enumerate(name.items()):
            manipulate = daily_values_lists[idx]
            pad(manipulate)
    else:
        pad(daily_values_lists)
    
    # Make each element equal in length so it can be converted to numpy array and the axes
    # can be swapped. Inspired by https://stackoverflow.com/a/26224619.
    if type(name) is dict:
        for idx, _ in enumerate(name):
            length = max(map(len, daily_values_lists[idx]))
            daily_values_lists[idx] = [xi+[None]*(length-len(xi)) for xi in daily_values_lists[idx]]

    # Swap last two (or only two) axes to convert from a list of days to a list of values
    # where each value is a list of the values for each day.
    daily_values_lists = np.swapaxes(np.array(daily_values_lists), -2, -1)

    if type(name) is dict:
        daily_values_lists = [("{} Hour {}".format(_name, i), x) for name_idx, _name in enumerate(name.values()) for i, x in enumerate(daily_values_lists[name_idx])]
    else:
        daily_values_lists = [("{} Hour {}".format(name, i), x) for i, x in enumerate(daily_values_lists)]

    return daily_values_lists

def generate_text_descriptions(text_weather):
    final_dict = OrderedDict()
    for forecast_period in text_weather:
        final_dict[forecast_period["name"]] = {
            "name": forecast_period["name"],
            "shortForecast": forecast_period["shortForecast"],
            "detailedForecast": forecast_period["detailedForecast"]
        }

    return final_dict

def push_date_to_weekday(date):
    while date.weekday() == 5 or date.weekday() == 6:
        date = date + datetime.timedelta(1)
    return date

def create_weekdates():
    today = datetime.datetime.today()
    if today.hour >= 12:
        today = today + datetime.timedelta(1)

    today = push_date_to_weekday(today)
    tomorrow = today + datetime.timedelta(1)
    tomorrow = push_date_to_weekday(tomorrow)
    third_day = tomorrow + datetime.timedelta(1)
    third_day = push_date_to_weekday(third_day)

    dates = [today.strftime('%A'), tomorrow.strftime('%A'), third_day.strftime('%A')]
    return dates

def process_text_descriptions(text_descriptions, days_to_keep=None):
    if days_to_keep is None:
        days_to_keep = create_weekdates()

    check_if_contains_weekday = datetime.datetime.today().strftime('%A') == days_to_keep[0]

    weekdays = [datetime.date(2001, 1, i).strftime('%A').lower() for i in range(1, 8)]
    
    # keys_to_remove = []
    final_list = []
    index = -1
    prev_period_name = "aaaa"
    for period_name, data in text_descriptions.items():
        contains_weekday = any([weekday in period_name.lower() for weekday in weekdays])
        period_name_in_any_days_to_keep = any([day.lower() in period_name.lower() for day in days_to_keep])
        
        if check_if_contains_weekday:
            remove_period = contains_weekday and not period_name_in_any_days_to_keep
        else:
            remove_period = not period_name_in_any_days_to_keep

        if remove_period:
            # keys_to_remove.append(period_name)
            continue
        elif contains_weekday and period_name[:4] != prev_period_name[:4]:
            index += 1
            prev_period_name = period_name
        
        try:
            final_list[index].append(data)
        except IndexError:
            final_list.append([data])

    # [text_descriptions.pop(k, None) for k in keys_to_remove]
    return final_list


# period_text_descriptions = generate_text_descriptions(text_weather)
# period_text_descriptions = process_text_descriptions(period_text_descriptions)

# daily_precipitation, dates = combine_based_on_date(weather_data["quantitativePrecipitation"], return_dates=True)
# daily_snowfall = combine_based_on_date(weather_data["snowfallAmount"])
# daily_snowlevel = combine_based_on_date(weather_data["snowLevel"])
# daily_maxtemp = get_values_list(weather_data["maxTemperature"])
# daily_mintemp = get_values_list(weather_data["minTemperature"])
# daily_avgtemp = combine_based_on_date(weather_data["temperature"], combine_func=avg)
# hourly_temp = generate_hourly(weather_data["temperature"], name="Air Temperature")
# hourly_snow_depth = generate_hourly(weather_data["snowLevel"], name="Snow Depth")
# hourly_snow_accumulation = generate_hourly(weather_data["snowfallAmount"], name="Snow Accumulation")
# hourly_liquid_precipitation = generate_hourly(weather_data["quantitativePrecipitation"], name="Liquid Precipitation")
# hourly_observation_data = generate_hourly(weather_data["weather"], name={"coverage": "Coverage", "weather": "Present Weather Observation Descriptor", "intensity": "Present Weather Observation Intensity"})

# all_date_details = [get_date_details(date) for date in dates]
# # Next line inspired by https://stackoverflow.com/a/33046935
# all_date_details_dict = {k: [dic[k] for dic in all_date_details] for k in all_date_details[0]}

# model_inputs = {
#     "PRCP": daily_precipitation,
#     "SNOW": daily_snowfall,
#     "SNWD": daily_snowlevel,
#     "TMAX": [x*10 for x in daily_maxtemp],  # tenths of degrees C
#     "TMIN": [x*10 for x in daily_mintemp],  # tenths of degrees C
#     "TAVG": [x*10 for x in daily_avgtemp],  # tenths of degrees C
#     **all_date_details_dict,
#     **dict(hourly_temp),
#     **dict(hourly_snow_depth),
#     **dict(hourly_snow_accumulation),
#     **dict(hourly_liquid_precipitation),
#     **dict(hourly_observation_data),
# }

# model_inputs = {key: model_inputs[key] for key in USED_FEATURES_LIST}

# input(model_inputs)

# PRCP: quantitativePrecipitation - 6 hour intervals combined
# SNOW: snowfallAmount - 6 hour intervals combined
# SNWD: snowLevel - 6 hour intervals combined
# TMAX: maxTemperature
# TMIN: minTemperature
# TAVG: temperature - 1 hour intervals averaged
# WT18: weather - snow_showers, snow - longest time period in current date that is not null
# WT22: weather - ice_fog freezing_fog - same as above
# WT04: weather - ice_pellets - same as above
# WT01: weather - fog - same as above
# WT17 - weather - freezing_rain - same as above
