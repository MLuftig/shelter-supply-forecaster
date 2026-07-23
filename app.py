import streamlit as st
import numpy as np
import pandas as pd
import altair as alt
from scipy import stats

# ============================================================
# Page config
# ============================================================
st.set_page_config(page_title="Shelter Medical Supply Forecaster", page_icon="🐾")

# ============================================================
# Hardcoded params, derived from real Austin Animal Center data
# (see src/ notebooks for full derivation)
# ============================================================

# --- Mortality-temperature model ---
# NegativeBinomial regression of daily deaths on standardized feels-like
# temperature. Pressure was tested and found NOT significant once temperature
# is controlled for (p=0.412) -- this is a temperature-only model, and that's
# a deliberate, verified choice, not a simplification.
mean_deaths = 1.729
dispersion_ratio_mortality = 1.861  # variance/mean from real data
coef_feels_like_z = 0.1081  # from NB regression, p < 0.001
feels_like_std = 16.17  # historical std dev of feels-like temp, used to convert z-scores
historical_avg_feels_like = 69.25

# --- Species/breed allocation of deaths, from real historical outcome data ---
# (cat/dog deaths only -- this tool is scoped to cats and dogs)
DEATH_ALLOCATION = {
    "Feline": 0.566,
    "Canine - Terrier": 0.149,
    "Canine - Toy": 0.064,
    "Canine - Mixed Breed": 0.052,
    "Canine - Herding": 0.049,
    "Canine - Sporting": 0.045,
    "Canine - Working": 0.038,
    "Canine - Non-Sporting": 0.020,
    "Canine - Hound": 0.017,
}

# --- Weight table, kg. Feline is a flat dose, not weight-based. ---
# Canine weights are real-Austin-breed-frequency-weighted averages against
# standard veterinary reference weights per breed -- see src/ notebooks.
# These are estimates, not measured data (Austin's records don't include
# animal weight), and are intentionally biased toward the higher end of
# each group's typical range, per the "over-order rather than under-order"
# design principle for a consumables planning tool.
CANINE_WEIGHTS_KG = {
    "Canine - Toy": 3.6,
    "Canine - Hound": 14.1,
    "Canine - Non-Sporting": 16.8,
    "Canine - Terrier": 19.8,
    "Canine - Herding": 26.8,
    "Canine - Sporting": 28.1,
    "Canine - Working": 33.1,
    "Canine - Mixed Breed": 20.4,
}


# ============================================================
# Core model functions
# ============================================================
def adjusted_mortality_mean(forecast_feels_like):
    """Weather-adjusted expected daily deaths, based on forecasted temperature."""
    temp_diff = forecast_feels_like - historical_avg_feels_like  # positive = warmer than average
    z_equivalent = temp_diff / feels_like_std
    multiplier = np.exp(coef_feels_like_z * z_equivalent)
    return mean_deaths * multiplier


def nb_params_from_mean(mean, dispersion_ratio):
    var = mean * dispersion_ratio
    p = mean / var
    n = mean * p / (1 - p)
    return n, p


def canine_euth_dose_ml(weight_kg, base_ml, base_weight_kg, ml_per_10lb):
    """Tiered euthanasia dosing: flat base dose up to base_weight_kg,
    then +ml_per_10lb for every additional 10 lbs of body weight above that."""
    if weight_kg <= base_weight_kg:
        return base_ml
    extra_kg = weight_kg - base_weight_kg
    extra_lb = extra_kg * 2.20462
    return base_ml + (extra_lb / 10.0) * ml_per_10lb


def simulate_forecast_week(temps, rng):
    """Simulate one 7-day scenario, returning total deaths by category."""
    category_totals = {cat: 0 for cat in DEATH_ALLOCATION}
    for day_temp in temps:
        adj_mean = adjusted_mortality_mean(day_temp)
        n_day, p_day = nb_params_from_mean(adj_mean, dispersion_ratio_mortality)
        total_deaths_today = stats.nbinom.rvs(n_day, p_day, random_state=rng)

        # Allocate today's deaths across categories using real historical proportions
        if total_deaths_today > 0:
            cats = list(DEATH_ALLOCATION.keys())
            probs = list(DEATH_ALLOCATION.values())
            assignments = rng.choice(cats, size=total_deaths_today, p=probs)
            for cat in assignments:
                category_totals[cat] += 1

    return category_totals


# ============================================================
# Streamlit UI
# ============================================================
st.title("🐾 Shelter Medical Supply Forecaster")
st.write(
    "Estimate expected euthanasia-related consumable usage for the coming week, "
    "adjusted for forecasted temperature. Built on a Negative Binomial regression "
    "of real Austin Animal Center mortality data (temperature is the verified "
    "driver -- barometric pressure was tested and found not significant once "
    "temperature is controlled for)."
)

st.subheader("7-Day Temperature Forecast")
st.caption(
    "Enter the expected 'feels-like' high temperature (°F) for each of the next 7 days. "
    "Warmer weather is associated with higher shelter mortality in this dataset."
)

cols = st.columns(7)
temps = []
for i, col in enumerate(cols):
    with col:
        t = st.number_input(f"Day {i+1}", min_value=-20, max_value=120, value=70, step=1, key=f"temp_{i}")
        temps.append(t)

st.subheader("Dosing Defaults")
st.caption("Adjust these to match your protocols. Defaults reflect standard practice and real Austin breed-frequency-weighted average weights.")

col1, col2 = st.columns(2)
with col1:
    st.caption("Canine euthanasia dosing: flat base dose up to a weight threshold, then +X mL per additional 10 lbs.  This is intentially a slightly high estimate for ordering purposes. Propofol usage is assumed to match euthanasia solution volume.")
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
    with st.spinner("Running Monte Carlo simulation..."):
        rng = np.random.default_rng()
        results = [simulate_forecast_week(temps, rng) for _ in range(n_simulations)]

        avg_totals = {cat: np.mean([r[cat] for r in results]) for cat in DEATH_ALLOCATION}
        total_expected = sum(avg_totals.values())

        expected_euth_ml = (
            avg_totals["Feline"] * feline_euth_ml
            + sum(
                avg_totals[cat] * canine_euth_dose_ml(
                    CANINE_WEIGHTS_KG[cat], euth_base_ml, euth_base_weight_kg, euth_ml_per_10lb
                )
                for cat in CANINE_WEIGHTS_KG
            )
        )
        expected_propofol_ml = expected_euth_ml
        expected_catheters = total_expected * catheters_per_case
        expected_flush_ml = total_expected * flush_ml_per_case
        expected_bags = total_expected * bags_per_case

    st.subheader("Expected Weekly Usage")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Expected cases", f"{total_expected:.1f}")
    col_b.metric("Euthanasia solution", f"{expected_euth_ml:.0f} mL",
                 delta=f"{stock_euth_ml - expected_euth_ml:.0f} mL remaining" if stock_euth_ml >= expected_euth_ml else f"⚠️ {expected_euth_ml - stock_euth_ml:.0f} mL short",
                 delta_color="normal" if stock_euth_ml >= expected_euth_ml else "inverse")
    col_c.metric("Propofol", f"{expected_propofol_ml:.0f} mL",
                 delta=f"{stock_propofol_ml - expected_propofol_ml:.0f} mL remaining" if stock_propofol_ml >= expected_propofol_ml else f"⚠️ {expected_propofol_ml - stock_propofol_ml:.0f} mL short",
                 delta_color="normal" if stock_propofol_ml >= expected_propofol_ml else "inverse")

    col_d, col_e, col_f = st.columns(3)
    col_d.metric("Catheters", f"{expected_catheters:.0f}",
                 delta=f"{stock_catheters - expected_catheters:.0f} remaining" if stock_catheters >= expected_catheters else f"⚠️ {expected_catheters - stock_catheters:.0f} short",
                 delta_color="normal" if stock_catheters >= expected_catheters else "inverse")
    col_e.metric("Flush", f"{expected_flush_ml:.0f} mL",
                 delta=f"{stock_flush_ml - expected_flush_ml:.0f} mL remaining" if stock_flush_ml >= expected_flush_ml else f"⚠️ {expected_flush_ml - stock_flush_ml:.0f} mL short",
                 delta_color="normal" if stock_flush_ml >= expected_flush_ml else "inverse")
    col_f.metric("Body bags", f"{expected_bags:.0f}",
                 delta=f"{stock_bags - expected_bags:.0f} remaining" if stock_bags >= expected_bags else f"⚠️ {expected_bags - stock_bags:.0f} short",
                 delta_color="normal" if stock_bags >= expected_bags else "inverse")

    st.subheader("Expected Cases by Category")
    category_df = pd.DataFrame({
        "Category": list(avg_totals.keys()),
        "Expected cases (7-day total)": list(avg_totals.values()),
    })
    category_chart = alt.Chart(category_df).mark_bar().encode(
        x=alt.X("Category", sort=None, title="Category"),
        y=alt.Y("Expected cases (7-day total)", title="Expected cases (7-day total)"),
    )
    st.altair_chart(category_chart, use_container_width=True)

    st.subheader("Expected Cases by Species")
    canine_total = sum(avg_totals[cat] for cat in CANINE_WEIGHTS_KG)
    feline_total = avg_totals["Feline"]
    species_df = pd.DataFrame({
        "Species": ["Canine", "Feline"],
        "Expected cases (7-day total)": [canine_total, feline_total],
    })
    species_chart = alt.Chart(species_df).mark_bar().encode(
        x=alt.X("Species", sort=None, title="Species"),
        y=alt.Y("Expected cases (7-day total)", title="Expected cases (7-day total)"),
    )
    st.altair_chart(species_chart, use_container_width=True)

st.divider()
with st.expander("About this model"):
    st.write(
        """
        This tool combines three pieces of analysis, all derived from real
        Austin Animal Center shelter data:

        1. **Weather-mortality model** — a Negative Binomial regression found
           that "feels-like" temperature, not barometric pressure, is the real
           driver of daily shelter mortality (temperature: p < 0.001; pressure:
           not significant once temperature is included, p = 0.412). Warmer
           weather is associated with more deaths in this dataset.
        2. **Species/breed allocation** — expected total deaths are split
           across categories using real historical proportions from Austin's
           outcome records, restricted to cats and dogs.
        3. **Weight-based dosing** — canine weight defaults are real
           Austin-breed-frequency-weighted averages against standard
           veterinary reference weights (Austin's data doesn't record actual
           animal weight, so per-breed reference weights are a domain
           estimate; the *frequency weighting* is real). Defaults are
           intentionally biased toward the higher end of each group's typical
           range, since this tool is meant to support ordering decisions,
           where over-estimating is safer than under-estimating.

        **Note:** this tool is scoped to cats and dogs only. All dosing
        defaults are adjustable to match your shelter's actual protocols.
        """
    )
