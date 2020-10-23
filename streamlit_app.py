import time
from itertools import cycle
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import pydeck as pdk
from math import sin, cos, sqrt, atan2, radians
from geopy.geocoders import Nominatim
import datetime
import random

# SETTING PAGE CONFIG TO WIDE MODE
st.beta_set_page_config(layout="wide")

# LOADING DATA
DATE_TIME = "date/time"
FILE = "Sampled.csv"

@st.cache()
def load_data():
    data = pd.read_csv(FILE)
    lowercase = lambda x: str(x).lower()
    data.rename(lowercase, axis="columns", inplace=True)
    data[DATE_TIME] = pd.to_datetime(data["pickup_datetime"])
    data["dropoff_datetime"] = pd.to_datetime(data["dropoff_datetime"])
    return data

data = load_data()
data = data.copy()

# CREATING FUNCTION FOR MAPS
# cite https://stackoverflow.com/questions/58548566/selecting-rows-in-geopandas-or-pandas-based-on-latitude-longitude-and-radius
@st.cache()
def get_distance(lon1, lat1, lon2, lat2):
    R = 6373.0
    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c * 1.15

# LAYING OUT THE LOCATION SECTION OF THE APP
row01, row02 = st.beta_columns([2,8])

with row01:
    st.title("NYC Taxi Viz")

st.markdown("### Examining the traffic flow of NYC Yellow Taxi for January 2016")

row1, row2 = st.beta_columns(2)
with row1:
    # FILTERING DATA BY HOUR SELECTED
    start_date = st.date_input('Date', datetime.date(2016, 1, 1))
    end_date = start_date + datetime.timedelta(days=1)

latitude = ""
longitude = ""
with row2:
    pickdrop = st.radio("Pickup/Dropoff", options=["Pickup", "Dropoff"], index=0)
    if pickdrop == "Pickup":
        latitude = 'pickup_latitude'
        longitude = 'pickup_longitude'
    else:
        latitude = 'dropoff_latitude'
        longitude = 'dropoff_longitude'

@st.cache()
def load_time(data, start_date, end_date):
    rst = data[(data[DATE_TIME] >= pd.to_datetime(start_date)) & (data[DATE_TIME] <= pd.to_datetime(end_date))]
    return rst

data = load_time(data, start_date, end_date)
data = data.copy()

# LAYING OUT THE LOCATION SECTION OF THE APP
row11, row12 = st.beta_columns(2)

# get the location lat and lon use geoapi
with row11:
    location = st.text_input("Location", "Manhattan")
with row12:
    radius = st.number_input("Radius (mile)", value=1.)

geolocator = Nominatim(user_agent="user_agent")
location = geolocator.geocode(location)
lon = location.longitude
lat = location.latitude

@st.cache()
def load_geo(data, lon, lat, radius, latitude, longitude):
    data['dist'] = list(
        map(lambda k: get_distance(data.loc[k][longitude], data.loc[k][latitude], lon, lat),
            data.index))
    # default is radius within 1 mile
    hold = data[data['dist'] < radius]
    if hold.shape[0] == 0:
        st.write("No_data")
        pass
    else:
        data = hold
    return data

data = load_geo(data, lon, lat, radius, latitude, longitude)
data = data.copy()

# get the velocity
def get_velocity(lon1, lat1, lon2, lat2, start, end):
    distance = get_distance(lon1, lat1, lon2, lat2)
    velocity = 1000 * distance / (end - start).total_seconds()
    return velocity

data['velo'] = list(map(lambda k: get_velocity(data.loc[k]['pickup_longitude'], data.loc[k]['pickup_latitude'],
                                               data.loc[k]['dropoff_longitude'], data.loc[k]['dropoff_latitude'],
                                               data.loc[k][DATE_TIME], data.loc[k]["dropoff_datetime"]), data.index))

st.write("Select time range")
row21,_, row22,_ = st.beta_columns([9,1,9,1])
with row21:
    start_hour = st.slider("From:", 0, 23)
with row22:
    end_hour = st.slider("To:", 0, 23, value=23)

if start_hour>end_hour: st.error("start hour need to be less than or equal to end hour")

hist = np.histogram(data[DATE_TIME].dt.hour, bins=25, range=(0, 25))[0]

chart_data = pd.DataFrame({"hour": range(25), "count": hist})
chart_data['start'] = start_hour
chart_data['end'] = end_hour
chart1 = alt.Chart(chart_data).mark_area(interpolate='step-after',)\
    .encode(x=alt.X("hour:O", scale=alt.Scale(nice=False)),y=alt.Y("count:Q"),tooltip=['hour', 'count'])\
    .configure_mark(opacity=0.5,color='red')
# chart2 = alt.Chart(chart_data).mark_rule().encode(x='start')
# c = alt.Chart(chart1 + chart2)
# chart2 = alt.Chart().mark_rule().encode(x='end')
st.altair_chart(chart1, use_container_width=True)

@st.cache()
def load_hour(data, start_hour, end_hour):
    return data[(data[DATE_TIME].dt.hour >= start_hour) & (data[DATE_TIME].dt.hour <= end_hour)]

data = load_hour(data, start_hour, end_hour)
data = data.copy()

st.markdown("### Current period and location has " + str(data.shape[0]) + " records\n")

hour_text = st.empty()
map = st.empty()
st.sidebar.markdown('### Map Options')
layer_names = [layer_name for layer_name in ["Scatter", "Heatmap", "Path"] if st.sidebar.checkbox(layer_name, False)]

st.sidebar.markdown("**In Path Map, a more efficient ride is green while a less efficient ride is red**")
st.sidebar.markdown("efficiency = great circle distance between pickup and dropoff / trip duration")

st.sidebar.markdown("### Animation Choices")
animations = {"None": None, "Non-cumulative": 1.5, "Cumulative": 1.5}
animate = st.sidebar.radio("For better experience, change back to 'none' animation before other operations", options=list(animations.keys()), index=0)
animation_speed = animations[animate]

def fmap(data, lat, lon, zoom, layer_names, latitude, longitude):
    all_layers = {

       "Scatter": pdk.Layer(
            'ScatterplotLayer',
            data=data,
            get_position=[longitude, latitude],
            auto_highlight=True,
            get_radius=50,
            get_fill_color='[180, 0, 200, 1000]',
            pickable=True), 

        "Heatmap": pdk.Layer(
            "HeatmapLayer",
            data=data,
            opacity=0.9,
            get_position=[longitude, latitude],
            aggregation='"SUM"',
        ),

        "Path": pdk.Layer(
            "ArcLayer",
            data=data,
            get_source_position=["pickup_longitude", "pickup_latitude"],
            get_target_position=["dropoff_longitude", "dropoff_latitude"],
            get_source_color="[255- velo*255/12, velo*255/12, 10]",
            get_target_color="[255- velo*255/12 , velo*255/12, 10]",
            auto_highlight=True,
            width_scale=0.00001,
            get_width="outbound",
            width_min_pixels=3,
            width_max_pixels=30,
        ),

    }

    layer = [all_layers[layer_name] for layer_name in layer_names]

    map.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v9",
        initial_view_state={
            "latitude": lat,
            "longitude": lon,
            "zoom": zoom,
            "pitch": 50,
        },
        layers=layer
    ))

timewindow = range(30)
timestep = datetime.timedelta(hours = end_hour-start_hour+1) / 30
if "Path" in layer_names:
    zoom_level = 11
else:
    if radius <=0.5:
        zoom_level = 15
    elif radius >0.5 and radius <= 1.5 :
        zoom_level = 14
    elif radius >1.5 and radius < 3:
        zoom_level = 13
    elif radius >=3 and radius < 5:
        zoom_level = 12
    elif radius >=5 and radius < 10:
        zoom_level = 11
    else:
        zoom_level = 10
midpoint = (np.average(data[latitude]), np.average(data[longitude]))

if animate == "Non-cumulative":
    for i in cycle(timewindow):
        start_time = datetime.datetime(2016,1,1,start_hour,0,0) + i * timestep
        end_time = datetime.datetime(2016,1,1,start_hour,0,0) + (i+1) * timestep
        hour_text.write("**Between " + str(start_time.time()) + " and " + str(end_time.time()) + "**")
        selected_data = data[(data[DATE_TIME].dt.time >= start_time.time()) & (data[DATE_TIME].dt.time < end_time.time())]
        fmap(selected_data, midpoint[0], midpoint[1], zoom_level, layer_names, latitude, longitude)
        time.sleep(animation_speed)
elif animate == "Cumulative":
    for i in cycle(timewindow):
        start_time = datetime.datetime(2016,1,1,start_hour,0,0)
        end_time = datetime.datetime(2016,1,1,start_hour,0,0) + (i+1) * timestep
        hour_text.write("**Between " + str(start_time.time()) + " and " + str(end_time.time()) + "**")
        selected_data = data[(data[DATE_TIME].dt.time >= start_time.time()) & (data[DATE_TIME].dt.time < end_time.time())]
        fmap(selected_data, midpoint[0], midpoint[1], zoom_level, layer_names, latitude, longitude)
        time.sleep(animation_speed)
else:
    start_time = datetime.datetime(2016, 1, 1, start_hour, 0, 0)
    end_time = datetime.datetime(2016, 1, 1, end_hour, 59, 59)
    hour_text.write("**Between " + str(start_time.time()) + " and " + str(end_time.time()) + "**")
    fmap(data, midpoint[0], midpoint[1], zoom_level, layer_names, latitude, longitude)