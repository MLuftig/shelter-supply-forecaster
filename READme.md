# Shelter Medical Supply Forecaster

A Monte Carlo simulation tool that estimates expected euthanasia-related
consumable usage for the coming week, adjusted for forecasted temperature,
comparing two independently-trained weather-mortality models side by side —
one built on real Austin Animal Center data, one on real Bloomington Animal
Care & Control data — against current stock on hand.

**Live app:** *([Shelter Medical Supply Forecaster](https://shelter-supply-forecaster.streamlit.app/))*

---

## Problem

Shelter medical supply ordering is typically reactive — staff notice stock
running low and order more, or worse, run out mid-week. Meanwhile, prior
work in this portfolio
([moon-phase & weather analysis](https://github.com/MLuftig/moon-phase-weather-shelter-analysis))
found that daily shelter mortality is not random noise: it's statistically
associated with weather, specifically temperature. That's a predictable
signal that a proactive ordering tool can actually use.

A natural follow-up question: is that relationship specific to Austin, or
does it hold at a different shelter, in a different climate, with a much
smaller and sparser dataset? This tool answers that directly by fitting the
same model independently on a second, unrelated shelter's real data and
comparing both, live, side by side.

## Solution

This project builds a weather-adjusted forecast of expected euthanasia case
volume for two shelters, breaks that volume down by species and breed group,
and converts it into expected consumable usage:

1. **Weather-mortality model** — a Negative Binomial regression of daily
   deaths on temperature, fit independently for each city. **Austin:**
   "feels-like" temperature, p < 0.001; barometric pressure tested and found
   **not significant** once temperature is controlled for (p = 0.412).
   **Bloomington:** average daily temperature (no true "feels-like" measure
   exists in this city's source weather data), p < 0.001; both barometric
   pressure (p = 0.327) and precipitation (p = 0.607) tested and found not
   significant once temperature is controlled for — independently
   replicating Austin's finding that pressure's apparent effect elsewhere in
   this portfolio is a temperature proxy, not an independent driver.
2. **Species/breed allocation** — expected total deaths are split into
   feline and canine breed-group categories using each shelter's own real
   historical proportions (restricted to cats and dogs, since that's this
   tool's scope).
3. **Weight-based dosing** — canine consumable dosing scales with each
   city's own estimated average weight per breed group; feline dosing is a
   flat per-case amount. See "Data & Assumptions" below for exactly what's
   real data versus domain-expert estimate, for both cities.
4. **Monte Carlo simulation** — thousands of randomized 7-day scenarios are
   run per city using each fitted mortality distribution, producing expected
   usage ranges rather than a single point estimate.
5. **Live forecast lookup** — enter a ZIP code and the app fetches a real
   7-day temperature forecast (via Open-Meteo) for that location, then runs
   both cities' models against those same conditions, so you can see how two
   differently-trained models respond to identical real-world weather.

## Cross-Shelter Finding

This tool sits alongside a separate finding from this portfolio's recidivism
work: a model predicting whether an *individual adopted animal* would be
returned, trained on Austin data, transferred only weakly to Bloomington —
the two shelters turned out to have substantially different underlying
drivers of return risk (age/species at Austin vs. length of stay at
Bloomington).

The weather-mortality relationship behind this tool tells a different story.
Restricted to Bloomington's verified data-coverage window (2017–2019, since
earlier years have near-zero shelter records and would have falsely read as
"zero deaths" rather than "no data"), the temperature effect on daily
shelter-wide mortality replicated independently and significantly, in the
same direction, despite a very different climate and a dataset roughly 1/7th
the density of Austin's (0.26 deaths/day vs. 1.73 deaths/day). Read together,
this suggests population-level environmental effects like heat stress may
generalize across shelters more reliably than individual-level behavioral
predictions do — a genuinely useful distinction when deciding whether a
model built at one shelter is worth trusting at another.

## Analysis Notebooks

*(Add links here once the derivation notebooks are uploaded to `src/`: the
original Austin mortality-temperature regression, and the corresponding
Bloomington day-level death/weather aggregation and regression, including
the data-coverage-window correction and the breed-weight derivation.)*

## Data & Assumptions

Being explicit about what's empirically verified versus estimated, since
mixing the two without labeling them was a real problem caught and
corrected earlier in this portfolio:

**Real, fitted from data (both cities):**
- The temperature coefficient and its significance
- The historical average temperature and its standard deviation
- The dispersion ratio (variance/mean) of daily mortality counts
- The species/breed-group proportions of historical deaths (cat vs. dog,
  and canine breed group breakdown)
- The breed *frequency* within each AKC group (used to weight the average
  weight estimate below)

**Domain-expert estimates, not measured data (both cities):**
- Per-breed reference body weights (neither shelter's records include
  animal weight, so a standard veterinary reference weight is assigned per
  breed, then frequency-weighted using real intake composition)
- The mL/kg dosing rate for euthanasia solution and propofol (defaults to
  standard practice; adjustable in the app)
- Flat per-case quantities (catheters, flush, body bags)

**Bloomington-specific notes:**
- Source weather data (NOAA LCD) has no "feels-like" field, unlike Austin's;
  average daily temperature is used as the closest available substitute.
- Source temperature data is in Celsius; converted to Fahrenheit-equivalent
  parameters so both cities share one consistent input scale in the app.
- The `snow` field in the raw weather data is unusable — every value is
  exactly 0, indicating the station never reported snow at all rather than
  genuinely snow-free days; it is excluded from the model rather than
  treated as real data.
- Several death-allocation categories (e.g. Toy, Non-Sporting) are based on
  very small counts (1–2 events) and carry meaningfully more uncertainty
  than Austin's larger-sample equivalents.

All estimated defaults are intentionally biased toward the higher end of
plausible ranges, since this tool is meant to support ordering decisions,
where over-estimating consumable need is a safer failure mode than
under-estimating it.

## How It Works

- Enter a ZIP code and fetch a live 7-day forecast, or enter temperatures
  manually
- Adjust dosing rates and flat per-case supply quantities to match your
  shelter's actual protocols
- Enter current stock on hand for each consumable
- The app simulates thousands of possible weeks for **both** Austin's and
  Bloomington's fitted models against the same forecasted conditions,
  converting expected cases into expected consumable usage for each
- Output: expected case volume, expected usage per consumable, and a
  surplus/shortage indicator against current stock, shown side by side for
  direct comparison

## Limitations

- This tool is scoped to cats and dogs only.
- Temperature explains only a small share of day-to-day mortality variance
  in both cities (Pseudo R² is low, consistent with the other weather-driven
  models in this portfolio) — this should be read as a **modest,
  directionally real risk adjustment**, not a precise forecast of exact case
  counts.
- Per-breed weight estimates are domain assumptions, not measured data, and
  should be adjusted if a given shelter's actual population differs
  meaningfully from either reference city's historical composition.
- **Neither model has been validated on any location other than its own home
  shelter.** Applying either model to an arbitrary ZIP code via the live
  forecast lookup is an extrapolation — useful for comparing how two real,
  differently-trained models respond to given conditions, not a validated
  prediction for that specific location's actual shelter.
- Bloomington's death-allocation and regression estimates are drawn from a
  meaningfully smaller, sparser dataset than Austin's; some category-level
  splits (see Data & Assumptions) should be treated as more approximate.

## Tech Stack

`Python`, `NumPy`, `SciPy` (distribution fitting, negative binomial
regression), `Requests` (ZIP geocoding and live forecast retrieval via
Zippopotam.us and Open-Meteo), `Streamlit` (deployment)

## Related Projects

- [Moon Phase & Weather Analysis](https://github.com/MLuftig/moon-phase-weather-shelter-analysis) — original discovery of the weather-mortality relationship, including the pressure/temperature confounding finding this tool is built on
- [Animal Shelter Recidivism Prediction](https://github.com/MLuftig/animal-shelter-recidivism-prediction) — companion project predicting individual animal return risk, including the same Austin/Bloomington cross-shelter comparison referenced above
- [Shelter Overflow Risk Forecaster](https://github.com/MLuftig/shelter-overflow-forecaster) — companion tool forecasting intake volume and kennel capacity risk
- [Shelter Return Risk Predictor](https://github.com/MLuftig/shelter-risk-predictor) — deployed app for the recidivism model
