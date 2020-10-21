

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import pydeck as pdk
from math import sin, cos, sqrt, atan2,radians
from geopy.geocoders import Nominatim
import datetime
# SETTING PAGE CONFIG TO WIDE MODE
st.beta_set_page_config(layout="wide")

# LOADING DATA
DATE_TIME = "date/time"


@st.cache(persist=True)
def load_data(file, nrows):
    data = pd.read_csv(file, nrows=nrows)
    lowercase = lambda x: str(x).lower()
    data.rename(lowercase, axis="columns", inplace=True)
    data[DATE_TIME] = pd.to_datetime(data["pickup_datetime"])
    data["dropoff_datetime"]= pd.to_datetime(data["dropoff_datetime"])
    return data
data = load_data("sampletrain.csv", 1000000)



# CREATING FUNCTION FOR MAPS
#cite https://stackoverflow.com/questions/58548566/selecting-rows-in-geopandas-or-pandas-based-on-latitude-longitude-and-radius
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

#get the
def get_velocity(lon1, lat1, lon2, lat2, start,end):
    distance = get_distance(lon1, lat1, lon2, lat2)
    velocity = 1000*distance/(end-start).total_seconds()
    return velocity



#show drop map 
def fmap(data, lat, lon, zoom):

    st.write(pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v9",
        initial_view_state={
            "latitude": lat,
            "longitude": lon,
            "zoom": zoom,
            "pitch": 50,
        },
            layers = layer


    ))

# LAYING OUT THE TOP SECTION OF THE APP
row1_1, row1_2 = st.beta_columns((2,3))

with row1_1:
    st.title("NYC Taxi")
    hour_selected = st.slider("Select hour of pickup", 0, 23)

with row1_2:
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
end_date = st.date_input('End date', datetime.date(2016,1,7))
if start_date < end_date:
    st.success('Start date: `%s`\n\nEnd date:`%s`' % (start_date, end_date))
else:
    st.error('Error: End date must fall after start date.')


# FILTERING DATA BY HOUR SELECTED
data = data[data[DATE_TIME].dt.hour == hour_selected]
data = data[(data[DATE_TIME]>=pd.to_datetime(start_date)) & (data[DATE_TIME]<=pd.to_datetime(end_date))]


#get the location lat and lon use geoapi 
location  = st.text_input("Location", "Manhattan")
radius = st.number_input("Radius(Km)", value=1.)

geolocator = Nominatim(user_agent="user_agent")
location = geolocator.geocode(location)
lon= location.longitude
lat = location.latitude
data['dist']=list(map(lambda k: get_distance(data.loc[k]['pickup_longitude'],data.loc[k]['pickup_latitude'],lon,lat), data.index))

#default is radius within 1km 
hold  = data[data['dist'] < radius]

if hold.shape[0] == 0:
    st.write("No_data")
    pass
else:
    data = hold
st.write(data.shape)

#velocity here 
data['velo']  = list(map(lambda k: get_velocity(data.loc[k]['pickup_longitude'],data.loc[k]['pickup_latitude'],data.loc[k]['dropoff_longitude'],data.loc[k]['dropoff_latitude'],data.loc[k][DATE_TIME],data.loc[k]["dropoff_datetime"]),data.index))
st.write("velocity")
st.write(data['velo'])
all_layers = {
        "Hexagon": pdk.Layer(
            "HexagonLayer",
            data=data,
            get_position=["pickup_longitude","pickup_latitude"],
            radius=100,
            elevation_scale=4,
            elevation_range=[0, 1000],
            extruded=True,
        ),
        "Heatmap":  pdk.Layer(
            "HeatmapLayer",
            data = data,
            opacity=0.9,
            get_position=["pickup_longitude","pickup_latitude"],
            aggregation='"MEAN"',
            ),
 
        "show drop off":   pdk.Layer(
            "ArcLayer",
            data=data,
            get_source_position=["pickup_longitude","pickup_latitude"],
            get_target_position=["dropoff_longitude","dropoff_latitude"],
            get_source_color=[200, 30, 0, 160],
            get_target_color=[200, 30, 0, 160],
            auto_highlight=True,
            width_scale=0.00001,
            get_width="outbound",
            width_min_pixels=3,
            width_max_pixels=30,
        ),

    }
st.sidebar.markdown('### Map Layers')
layer =  [layer for layer_name, layer in all_layers.items() if st.sidebar.checkbox(layer_name, False)]


zoom_level = 12
midpoint = (np.average(data["pickup_latitude"]), np.average(data["pickup_longitude"]))

st.write("**All New York City from %i:00 and %i:00**" % (hour_selected, (hour_selected + 1) % 24))
fmap(data, midpoint[0], midpoint[1], 12)





# FILTERING DATA FOR THE HISTOGRAM
filtered = data[
    (data[DATE_TIME].dt.hour >= hour_selected) & (data[DATE_TIME].dt.hour < (hour_selected + 1))
    ]

hist = np.histogram(filtered[DATE_TIME].dt.minute, bins=60, range=(0, 60))[0]

chart_data = pd.DataFrame({"minute": range(60), "pickups": hist})

# LAYING OUT THE HISTOGRAM SECTION

st.write("")

st.write("**Breakdown of rides per minute between %i:00 and %i:00**" % (hour_selected, (hour_selected + 1) % 24))

st.altair_chart(alt.Chart(chart_data)
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

