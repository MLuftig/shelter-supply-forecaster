import streamlit as st
import numpy as np
import requests
from scipy import stats

# ============================================================
# Page config
# ============================================================
st.set_page_config(page_title="Shelter Medical Supply Forecaster", page_icon="🐾", layout="wide")

# ============================================================
# City parameter sets, derived from real shelter data
# (see src/ notebooks for full derivation of both)
# ============================================================
CITY_PARAMS = {
    "Austin, TX": {
        "mean_deaths": 1.729,
        "dispersion_ratio_mortality": 1.861,
        "coef_temp_z": 0.1081,
        "temp_std": 16.17,
        "historical_avg_temp": 69.25,
        "death_allocation": {
            "Feline": 0.566,
            "Canine - Terrier": 0.149,
            "Canine - Toy": 0.064,
            "Canine - Mixed Breed": 0.052,
            "Canine - Herding": 0.049,
            "Canine - Sporting": 0.045,
            "Canine - Working": 0.038,
            "Canine - Non-Sporting": 0.020,
            "Canine - Hound": 0.017,
        },
        "canine_weights_kg": {
            "Canine - Toy": 3.6,
            "Canine - Hound": 14.1,
            "Canine - Non-Sporting": 16.8,
            "Canine - Terrier": 19.8,
            "Canine - Herding": 26.8,
            "Canine - Sporting": 28.1,
            "Canine - Working": 33.1,
            "Canine - Mixed Breed": 20.4,
        },
    },
    "Bloomington, IN": {
        "mean_deaths": 0.2627,
        "dispersion_ratio_mortality": 1.1402,
        "coef_temp_z": 0.3799,
        "temp_std": 18.59,       # converted from 10.33 degC; raw source data is Celsius, unlike Austin's Fahrenheit
        "historical_avg_temp": 55.98,  # converted from 13.32 degC
        "death_allocation": {
            "Feline": 0.736,
            "Canine - Terrier": 0.088,
            "Canine - Mixed Breed": 0.064,
            "Canine - Hound": 0.036,
            "Canine - Sporting": 0.024,
            "Canine - Herding": 0.024,
            "Canine - Working": 0.016,
            "Canine - Toy": 0.008,
            "Canine - Non-Sporting": 0.004,
        },
        "canine_weights_kg": {
            "Canine - Toy": 3.9,
            "Canine - Hound": 19.0,
            "Canine - Non-Sporting": 25.4,
            "Canine - Terrier": 22.5,
            "Canine - Herding": 26.5,
            "Canine - Sporting": 32.0,
            "Canine - Working": 37.7,
            "Canine - Mixed Breed": 24.2,
        },
    },
}


# ============================================================
# Core model functions
# ============================================================
def adjusted_mortality_mean(forecast_temp, params):
    """Weather-adjusted expected daily deaths, based on forecasted temperature
    and a given city's fitted parameters."""
    temp_diff = forecast_temp - params["historical_avg_temp"]
    z_equivalent = temp_diff / params["temp_std"]
    multiplier = np.exp(params["coef_temp_z"] * z_equivalent)
    return params["mean_deaths"] * multiplier


def nb_params_from_mean(mean, dispersion_ratio):
    var = mean * dispersion_ratio
    p = mean / var
    n = mean * p / (1 - p)
    return n, p


def simulate_forecast_week(temps, rng, params):
    """Simulate one 7-day scenario for a given city, returning total deaths by category."""
    death_allocation = params["death_allocation"]
    category_totals = {cat: 0 for cat in death_allocation}
    for day_temp in temps:
        adj_mean = adjusted_mortality_mean(day_temp, params)
        n_day, p_day = nb_params_from_mean(adj_mean, params["dispersion_ratio_mortality"])
        total_deaths_today = stats.nbinom.rvs(n_day, p_day, random_state=rng)

        if total_deaths_today > 0:
            cats = list(death_allocation.keys())
            probs = list(death_allocation.values())
            assignments = rng.choice(cats, size=total_deaths_today, p=probs)
            for cat in assignments:
                category_totals[cat] += 1

    return category_totals


def canine_euth_dose_ml(weight_kg, base_ml, base_weight_kg, ml_per_10lb):
    """Tiered euthanasia dosing: flat base dose up to base_weight_kg,
    then +ml_per_10lb for every additional 10 lbs of body weight above that."""
    if weight_kg <= base_weight_kg:
        return base_ml
    extra_kg = weight_kg - base_weight_kg
    extra_lb = extra_kg * 2.20462
    return base_ml + (extra_lb / 10.0) * ml_per_10lb


# ============================================================
# ZIP -> coordinates -> live 7-day forecast
# ============================================================
def fetch_location_from_zip(zip_code):
    """ZIP -> lat/lon/place name via Zippopotam.us (free, no API key)."""
    response = requests.get(f"http://api.zippopotam.us/us/{zip_code}", timeout=10)
    response.raise_for_status()
    data = response.json()
    place = data["places"][0]
    return {
        "lat": float(place["latitude"]),
        "lon": float(place["longitude"]),
        "name": f"{place['place name']}, {place['state abbreviation']}",
    }


def fetch_7day_forecast(lat, lon):
    """Live 7-day daily-mean-temperature forecast via Open-Meteo (free, no API key)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_mean&temperature_unit=fahrenheit"
        f"&forecast_days=7&timezone=auto"
    )
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data["daily"]["time"], data["daily"]["temperature_2m_mean"]


# ============================================================
# Streamlit UI
# ============================================================
st.title("🐾 Shelter Medical Supply Forecaster")
st.write(
    "Estimate expected euthanasia-related consumable usage for the coming week, "
    "comparing two independently-trained weather-mortality models -- one built on "
    "real Austin Animal Center data, one on real Bloomington Animal Care & Control "
    "data. Both models found 'feels-like'/average temperature to be a significant, "
    "positive predictor of daily shelter mortality; barometric pressure and "
    "precipitation were tested in both cities and found not significant once "
    "temperature is controlled for."
)
st.info(
    "⚠️ **Note on scope:** both models were trained and validated only on their own "
    "home shelter's historical data. Applying either model to a third, unrelated "
    "ZIP code's weather is an extrapolation beyond what's been tested -- this tool "
    "is meant to compare how two real, differently-trained models respond to the "
    "same local conditions, not as a validated prediction for your specific shelter."
)

st.subheader("7-Day Temperature Forecast")
st.caption(
    "Enter a ZIP code to pull a live 7-day forecast, or adjust the daily average "
    "temperatures (°F) manually below."
)

col_zip, col_button = st.columns([2, 1])
with col_zip:
    zip_code = st.text_input("ZIP code", value="", max_chars=5, placeholder="e.g. 78701")
with col_button:
    st.write("")
    st.write("")
    fetch_clicked = st.button("Fetch live forecast", type="secondary")

if fetch_clicked and zip_code:
    try:
        location = fetch_location_from_zip(zip_code)
        dates, temps_fetched = fetch_7day_forecast(location["lat"], location["lon"])
        for i, t in enumerate(temps_fetched):
            st.session_state[f"temp_{i}"] = round(t)
        st.session_state["fetched_location"] = location["name"]
        st.session_state["fetched_dates"] = dates
        st.success(f"Loaded live 7-day forecast for {location['name']}.")
    except Exception as e:
        st.error(f"Couldn't fetch forecast for that ZIP code: {e}. Enter temperatures manually below.")

if "fetched_location" in st.session_state:
    st.caption(f"📍 Showing forecast for **{st.session_state['fetched_location']}**")

cols = st.columns(7)
temps = []
for i, col in enumerate(cols):
    with col:
        label = f"Day {i+1}"
        if "fetched_dates" in st.session_state:
            label = st.session_state["fetched_dates"][i]
        t = st.number_input(label, min_value=-20, max_value=120, step=1, key=f"temp_{i}", value=st.session_state.get(f"temp_{i}", 70))
        temps.append(t)

st.subheader("Dosing Defaults")
st.caption("Adjust these to match your protocols. Defaults reflect standard practice; canine dosing scales with each city's own breed-frequency-weighted average weights.")

col1, col2 = st.columns(2)
with col1:
    st.caption("Canine euthanasia dosing: flat base dose up to a weight threshold, then +X mL per additional 10 lbs. Propofol usage is assumed to match euthanasia solution volume.")
    euth_base_ml = st.number_input("Base dose (mL, up to threshold)", min_value=0.5, value=3.0, step=0.5)
    euth_base_weight_kg = st.number_input("Weight threshold (kg)", min_value=1.0, value=15.0, step=0.5)
    euth_ml_per_10lb = st.number_input("Additional mL per 10 lbs over threshold", min_value=0.0, value=1.0, step=0.5)
with col2:
    feline_euth_ml = st.number_input("Euthanasia solution, feline (flat mL/case)", min_value=0.5, value=3.0, step=0.5)

st.subheader("Flat Per-Case Supplies")
col3, col4, col5 = st.columns(3)
with col3:
    catheters_per_case = st.number_input("IV catheters per case", min_value=0.0, value=1.0, step=1.0)
with col4:
    flush_ml_per_case = st.number_input("Flush (mL/case)", min_value=0.0, value=10.0, step=1.0)
with col5:
    bags_per_case = st.number_input("Body bags per case", min_value=0.0, value=1.0, step=1.0)

st.subheader("Current Stock on Hand")
st.caption("Applied against both cities' forecasts below for comparison.")
col6, col7 = st.columns(2)
with col6:
    stock_euth_ml = st.number_input("Euthanasia solution in stock (mL)", min_value=0, value=500, step=10)
    stock_propofol_ml = st.number_input("Propofol in stock (mL)", min_value=0, value=500, step=10)
    stock_catheters = st.number_input("Catheters in stock", min_value=0, value=50, step=5)
with col7:
    stock_flush_ml = st.number_input("Flush in stock (mL)", min_value=0, value=1000, step=50)
    stock_bags = st.number_input("Body bags in stock", min_value=0, value=50, step=5)

n_simulations = st.slider("Number of simulations", 100, 5000, 1000, step=100)

if st.button("Run Forecast", type="primary"):
    city_columns = st.columns(2)

    for city_col, (city_name, params) in zip(city_columns, CITY_PARAMS.items()):
        with city_col:
            st.markdown(f"### {city_name}")
            with st.spinner(f"Running Monte Carlo simulation ({city_name})..."):
                rng = np.random.default_rng()
                results = [simulate_forecast_week(temps, rng, params) for _ in range(n_simulations)]

                death_allocation = params["death_allocation"]
                canine_weights = params["canine_weights_kg"]
                avg_totals = {cat: np.mean([r[cat] for r in results]) for cat in death_allocation}
                total_expected = sum(avg_totals.values())

                expected_euth_ml = (
                    avg_totals["Feline"] * feline_euth_ml
                    + sum(
                        avg_totals[cat] * canine_euth_dose_ml(
                            canine_weights[cat], euth_base_ml, euth_base_weight_kg, euth_ml_per_10lb
                        )
                        for cat in canine_weights
                    )
                )
                expected_propofol_ml = expected_euth_ml
                expected_catheters = total_expected * catheters_per_case
                expected_flush_ml = total_expected * flush_ml_per_case
                expected_bags = total_expected * bags_per_case

            st.metric("Expected cases (7-day total)", f"{total_expected:.1f}")

            m1, m2 = st.columns(2)
            m1.metric("Euthanasia solution", f"{expected_euth_ml:.0f} mL",
                       delta=f"{stock_euth_ml - expected_euth_ml:.0f} mL remaining" if stock_euth_ml >= expected_euth_ml else f"⚠️ {expected_euth_ml - stock_euth_ml:.0f} mL short",
                       delta_color="normal" if stock_euth_ml >= expected_euth_ml else "inverse")
            m2.metric("Propofol", f"{expected_propofol_ml:.0f} mL",
                       delta=f"{stock_propofol_ml - expected_propofol_ml:.0f} mL remaining" if stock_propofol_ml >= expected_propofol_ml else f"⚠️ {expected_propofol_ml - stock_propofol_ml:.0f} mL short",
                       delta_color="normal" if stock_propofol_ml >= expected_propofol_ml else "inverse")

            m3, m4, m5 = st.columns(3)
            m3.metric("Catheters", f"{expected_catheters:.0f}",
                       delta=f"{stock_catheters - expected_catheters:.0f} remaining" if stock_catheters >= expected_catheters else f"⚠️ {expected_catheters - stock_catheters:.0f} short",
                       delta_color="normal" if stock_catheters >= expected_catheters else "inverse")
            m4.metric("Flush", f"{expected_flush_ml:.0f} mL",
                       delta=f"{stock_flush_ml - expected_flush_ml:.0f} mL remaining" if stock_flush_ml >= expected_flush_ml else f"⚠️ {expected_flush_ml - stock_flush_ml:.0f} mL short",
                       delta_color="normal" if stock_flush_ml >= expected_flush_ml else "inverse")
            m5.metric("Body bags", f"{expected_bags:.0f}",
                       delta=f"{stock_bags - expected_bags:.0f} remaining" if stock_bags >= expected_bags else f"⚠️ {expected_bags - stock_bags:.0f} short",
                       delta_color="normal" if stock_bags >= expected_bags else "inverse")

            st.caption("Expected cases by category (7-day total)")
            st.bar_chart(avg_totals)

st.divider()
with st.expander("About this model"):
    st.write(
        """
        This tool compares two independently-trained models, each combining three
        pieces of analysis derived from real shelter data:

        1. **Weather-mortality model** — a Negative Binomial regression on each
           city's own daily mortality and weather records. Both cities found
           temperature to be a significant, positive predictor of daily shelter
           deaths (Austin: p < 0.001; Bloomington: p < 0.001), while barometric
           pressure and precipitation were tested and found not significant in
           either city once temperature is controlled for. Bloomington's source
           weather data does not include a true "feels-like" measure (unlike
           Austin's), so average daily temperature is used as the closest
           available substitute.
        2. **Species/breed allocation** — expected total deaths are split across
           categories using each shelter's own real historical proportions,
           restricted to cats and dogs.
        3. **Weight-based dosing** — canine weight defaults are each city's own
           real breed-frequency-weighted averages against standard veterinary
           reference weights (neither shelter's data records actual animal
           weight, so per-breed reference weights are a domain estimate; the
           frequency weighting itself is real). Defaults are intentionally
           biased toward the higher end of each group's typical range, since
           this tool is meant to support ordering decisions, where
           over-estimating is safer than under-estimating.

        **Cross-shelter note:** a separate analysis found that a recidivism
        (adoption-return) model trained on Austin data transferred only weakly
        to Bloomington, with the two shelters showing substantially different
        underlying risk drivers. This weather-mortality relationship, by
        contrast, replicated independently and significantly in both cities —
        suggesting population-level environmental effects like heat stress may
        generalize across shelters more reliably than individual-level
        behavioral predictions do.

        **Note:** this tool is scoped to cats and dogs only. All dosing
        defaults are adjustable to match your shelter's actual protocols.
        """
    )
