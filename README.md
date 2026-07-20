# Shelter Medical Supply Forecaster

A Monte Carlo simulation tool that estimates expected euthanasia-related
consumable usage for the coming week, adjusted for forecasted temperature,
and compares that estimate against current stock on hand.

**Live app:** *(add your Streamlit deployment URL here once deployed)*

---

## Problem

Shelter medical supply ordering is typically reactive — staff notice stock
running low and order more, or worse, run out mid-week. Meanwhile, prior
work in this portfolio
([moon-phase & weather analysis](https://github.com/MLuftig/moon-phase-weather-shelter-analysis))
found that daily shelter mortality is not random noise: it's statistically
associated with weather, specifically temperature. That's a predictable
signal that a proactive ordering tool can actually use.

## Solution

This project builds a weather-adjusted forecast of expected euthanasia case
volume, breaks that volume down by species and breed group, and converts it
into expected consumable usage:

1. **Weather-mortality model** — a Negative Binomial regression of daily
   deaths on "feels-like" temperature (with an explicitly estimated
   dispersion parameter). Barometric pressure was also tested, since it was
   the original hypothesis from the moon-phase project, but was found **not
   significant** once temperature is controlled for (p = 0.412) — pressure's
   apparent univariate effect on mortality was a proxy for temperature, not
   an independent driver. This tool uses the real, verified relationship:
   temperature only.
2. **Species/breed allocation** — expected total deaths are split into
   feline and canine breed-group categories using real historical
   proportions from Austin Animal Center outcome records (restricted to
   cats and dogs, since that's this tool's scope).
3. **Weight-based dosing** — canine consumable dosing scales with an
   estimated average weight per breed group; feline dosing is a flat
   per-case amount. See "Data & Assumptions" below for exactly what's real
   data versus domain-expert estimate.
4. **Monte Carlo simulation** — thousands of randomized 7-day scenarios are
   run using the fitted mortality distribution, producing expected usage
   ranges rather than a single point estimate.

## Analysis Notebooks

*(Add links here once the derivation notebooks are uploaded to `src/`,
matching the pattern used in the other two portfolio apps — e.g. the
mortality-temperature regression and the death-allocation/weight-table
computation.)*

## Data & Assumptions

Being explicit about what's empirically verified versus estimated, since
mixing the two without labeling them was a real problem caught and
corrected earlier in this portfolio:

**Real, fitted from data:**
- The temperature coefficient and its significance (p < 0.001)
- The historical average temperature and its standard deviation
- The dispersion ratio (variance/mean) of daily mortality counts
- The species/breed-group proportions of historical deaths (cat vs. dog,
  and canine breed group breakdown)
- The breed *frequency* within each AKC group (used to weight the average
  weight estimate below)

**Domain-expert estimates, not measured data:**
- Per-breed reference body weights (Austin's records don't include animal
  weight, so a standard veterinary reference weight is assigned per breed,
  then frequency-weighted using real intake composition)
- The mL/kg dosing rate for euthanasia solution and propofol (defaults to
  standard practice; adjustable in the app)
- Flat per-case quantities (catheters, flush, body bags)

All estimated defaults are intentionally biased toward the higher end of
plausible ranges, since this tool is meant to support ordering decisions,
where over-estimating consumable need is a safer failure mode than
under-estimating it.

## How It Works

- Enter the forecasted "feels-like" high temperature for each of the next 7 days
- Adjust dosing rates and flat per-case supply quantities to match your
  shelter's actual protocols
- Enter current stock on hand for each consumable
- The app simulates thousands of possible weeks using the fitted mortality
  distribution and real species/breed allocation, converting expected cases
  into expected consumable usage
- Output: expected case volume, expected usage per consumable, and a
  surplus/shortage indicator against current stock

## Limitations

- This tool is scoped to cats and dogs only.
- Temperature explains only a small share of day-to-day mortality variance
  (Pseudo R² is low, consistent with the other weather-driven models in this
  portfolio) — this should be read as a **modest, directionally real risk
  adjustment**, not a precise forecast of exact case counts.
- Per-breed weight estimates are domain assumptions, not measured data, and
  should be adjusted if your shelter's actual population differs
  meaningfully from Austin's historical composition.

## Tech Stack

`Python`, `NumPy`, `SciPy` (distribution fitting, negative binomial
regression), `Streamlit` (deployment)

## Related Projects

- [Moon Phase & Weather Analysis](https://github.com/MLuftig/moon-phase-weather-shelter-analysis) — original discovery of the weather-mortality relationship, including the pressure/temperature confounding finding this tool is built on
- [Shelter Overflow Risk Forecaster](https://github.com/MLuftig/shelter-overflow-forecaster) — companion tool forecasting intake volume and kennel capacity risk
- [Shelter Return Risk Predictor](https://github.com/MLuftig/shelter-risk-predictor) — companion tool predicting individual animal return risk
