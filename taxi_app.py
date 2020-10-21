import time
from itertools import cycle
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import pydeck as pdk
from math import sin, cos, sqrt, atan2,radians
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
    st.write("Cache miss")
    data = pd.read_csv(FILE)
    lowercase = lambda x: str(x).lower()
    data.rename(lowercase, axis="columns", inplace=True)
    data[DATE_TIME] = pd.to_datetime(data["pickup_datetime"])
    return data
data = load_data()

data = data.copy()



# CREATING FUNCTION FOR MAPS
#cite https://stackoverflow.com/questions/58548566/selecting-rows-in-geopandas-or-pandas-based-on-latitude-longitude-and-radius
@st.cache()
def get_distance(lon1, lat1, lon2, lat2):
  R = 6373.0

  lat1 = radians(lat1)
  lon1 = radians(lon1)
  lat2 = radians(lat2)
  lon2 = radians(lon2)
  dlon = lon2 - lon1
  dlat = lat2 - lat1

  a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
  c = 2 * atan2(sqrt(a), sqrt(1 - a))

  return R * c




# LAYING OUT THE TOP SECTION OF THE APP
# row1_1, row1_2 = st.beta_columns((2,3))

# with row1_1:
st.title("NYC Taxi")


# with row1_2:
st.write(
"""
##
Examining how Uber pickups vary over time in New York City's and at its major regional airports.
By sliding the slider on the left you can view different slices of time and explore different transportation trends.
""")

#join 
today = datetime.date.today()
tomorrow = today + datetime.timedelta(days=1)
start_date = st.date_input('Start date', datetime.date(2016,1,1))
end_date = st.date_input('End date', datetime.date(2016,1,3))
if start_date < end_date:
    st.success('Start date: `%s`\n\nEnd date:`%s`' % (start_date, end_date))
else:
    st.error('Error: End date must fall after start date.')


# FILTERING DATA BY HOUR SELECTED
@st.cache()
def load_time(data, start_date, end_date):
    rst = data[(data[DATE_TIME]>=pd.to_datetime(start_date)) & (data[DATE_TIME]<=pd.to_datetime(end_date))]
    return rst
data = load_time(data, start_date, end_date)
data = data.copy()


#get the location lat and lon use geoapi 
location  = st.text_input("Location", "Manhattan")
radius = st.number_input("Radius(Km)", value=0.5)

geolocator = Nominatim(user_agent="user_agent")
location = geolocator.geocode(location)
lon= location.longitude
lat = location.latitude

# @st.cache(persist=True)
@st.cache()
def load_geo(data, lon, lat, radius):
    data['dist']=list(map(lambda k: get_distance(data.loc[k]['pickup_longitude'],data.loc[k]['pickup_latitude'],lon,lat), data.index))

    #default is radius within 1km
    hold  = data[data['dist'] < radius]

    if hold.shape[0] == 0:
        st.write("No_data")
        pass
    else:
        data = hold
    return data
data = load_geo(data, lon, lat, radius)
data = data.copy()

st.write(data.shape)

animations = {"None": None, "Slow": 5, "Fast": 1}
animate = st.radio("", options=list(animations.keys()), index=0)
animation_speed = animations[animate]

hour_slider = st.empty()
hour_text = st.empty()
map = st.empty()
st.sidebar.markdown('### Map Layers')
layer_names =  [layer_name for layer_name in ["Hexagon", "Heatmap", "show drop off"] if st.sidebar.checkbox(layer_name, False)]

def render_slider(hour):
    key = random.random() if animation_speed else None
    if animation_speed:
        hour_selected = hour_slider.slider("Select hour of pickup", 0, 23, hour, key=key)
    else:
        hour_selected = hour_slider.slider("Select hour of pickup", 0, 23)
    hour_text.write("**All New York City from %i:00 and %i:00**" % (hour_selected, (hour_selected + 1) % 24))
    return hour_selected

def fmap(data, lat, lon, zoom, layer_names):
    all_layers = {
        "Hexagon": pdk.Layer(
            "HexagonLayer",
            data=data,
            get_position=["pickup_longitude", "pickup_latitude"],
            radius=100,
            elevation_scale=4,
            elevation_range=[0, 1000],
            extruded=True,
        ),
        "Heatmap": pdk.Layer(
            "HeatmapLayer",
            data=data,
            opacity=0.9,
            get_position=["pickup_longitude", "pickup_latitude"],
            aggregation='"MEAN"',
        ),

        "show drop off": pdk.Layer(
            "ArcLayer",
            data=data,
            get_source_position=["pickup_longitude", "pickup_latitude"],
            get_target_position=["dropoff_longitude", "dropoff_latitude"],
            get_source_color=[200, 30, 0, 160],
            get_target_color=[200, 30, 0, 160],
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
            layers = layer
    ))

hist_text = st.empty()
histogram = st.empty()

def hist(data, hour_selected):
    # FILTERING DATA FOR THE HISTOGRAM
    filtered = data[
        (data[DATE_TIME].dt.hour >= hour_selected) & (data[DATE_TIME].dt.hour < (hour_selected + 1))
        ]

    hist = np.histogram(filtered[DATE_TIME].dt.minute, bins=60, range=(0, 60))[0]

    chart_data = pd.DataFrame({"minute": range(60), "pickups": hist})

    # LAYING OUT THE HISTOGRAM SECTION

    # st.write("")

    hist_text.write("**Breakdown of rides per minute between %i:00 and %i:00**" % (hour_selected, (hour_selected + 1) % 24))

    histogram.altair_chart(alt.Chart(chart_data)
        .mark_area(
            interpolate='step-after',
        ).encode(
            x=alt.X("minute:Q", scale=alt.Scale(nice=False)),
            y=alt.Y("pickups:Q"),
            tooltip=['minute', 'pickups']
        ).configure_mark(
            opacity=0.5,
            color='red'
        ), use_container_width=True)


hours = range(23)
zoom_level = 12
midpoint = (np.average(data["pickup_latitude"]), np.average(data["pickup_longitude"]))

if animation_speed:
    for hour in cycle(hours):
        time.sleep(animation_speed)
        h = render_slider(hour)
        selected_data = data[data[DATE_TIME].dt.hour == h]
        fmap(selected_data, midpoint[0], midpoint[1], 12, layer_names)
        hist(selected_data, h)
else:
    h = render_slider(-1)
    selected_data = data[data[DATE_TIME].dt.hour == h]
    fmap(selected_data, midpoint[0], midpoint[1], 12, layer_names)
    hist(selected_data, h)


