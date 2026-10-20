"""Post-competition local runner, prepared 2026-10-19.

Calculation cells are taken from Kevin's two archived notebooks. Original
notebooks remain unchanged. Upload/download and display-only cells are omitted.
Rebuilds operating costs from costs.xlsx, then integrates archived upstream
transaction and gate tables. It does not rebuild those upstream tables.
"""
from pathlib import Path
import json
import platform
import pandas as pd
import numpy as np
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/reproduced"
OUTPUT.mkdir(parents=True, exist_ok=True)
checks = []

def display(*args, **kwargs):
    """Notebook previews are omitted from the terminal run."""

def compare(table, reference):
    """Compare every field after CSV serialization; currency tolerance 1 cent."""
    destination = OUTPUT / reference.name
    table.to_csv(destination, index=False, encoding="utf-8-sig")
    actual = pd.read_csv(destination)
    expected = pd.read_csv(reference)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False,
                                  check_exact=False, rtol=1e-12, atol=0.01)
    checks.append({"reference": str(reference.relative_to(ROOT)),
                   "rows": len(actual), "status": "passed"})

# Operating costs: original calculation cells.


# Source: 01_operating_costs.ipynb, zero-based cell 0
import pandas as pd



# Source: 01_operating_costs.ipynb, zero-based cell 2

filename = ROOT / "data/raw/costs.xlsx"

costs_raw = pd.read_excel(filename, sheet_name="Costs")

print("rows, columns", costs_raw.shape)

display(costs_raw.head())


# Source: 01_operating_costs.ipynb, zero-based cell 3
# Keep the original data unchanged.
costs = costs_raw.copy()

print("Original shape:", costs_raw.shape)
print("Working shape:", costs.shape)


# Source: 01_operating_costs.ipynb, zero-based cell 4
# Count missing values in each column.
missing_counts = costs.isna().sum()

print("Missing values by column:")
display(missing_counts)


# Source: 01_operating_costs.ipynb, zero-based cell 5
costs.duplicated()


# Source: 01_operating_costs.ipynb, zero-based cell 6
costs["Cost_ID"].duplicated()


# Source: 01_operating_costs.ipynb, zero-based cell 7
# Count records for each cost category.
cost_type_counts = costs["Cost_Type"].value_counts(dropna=False)

print("Records by cost type:")
display(cost_type_counts)


# Source: 01_operating_costs.ipynb, zero-based cell 8
# Inspect the original route labels.
print("Original route label count:", costs["Route_ID"].nunique())

display(costs[["Route_ID"]].head(10))


# Source: 01_operating_costs.ipynb, zero-based cell 9
# Preserve the original route labels.
costs["Route_ID_Original"] = costs["Route_ID"]

# Convert route labels to uppercase and remove separators.
route_compact = (
    costs["Route_ID_Original"]
    .astype("string")
    .str.upper()
    .str.replace(r"[^A-Z]", "", regex=True))

display(
    pd.DataFrame({
        "OriginalRoute": costs["Route_ID_Original"],
        "CompactRoute": route_compact
    }).head(10))



# Source: 01_operating_costs.ipynb, zero-based cell 10
# Validate the six-letter route format.
valid_route = route_compact.str.fullmatch(r"[A-Z]{6}", na=False)

invalid_route_count = (~valid_route).sum()

print("Invalid route labels:", invalid_route_count)

if invalid_route_count > 0:
    display(
        costs.loc[
            ~valid_route,
            ["Cost_ID", "Route_ID_Original"]
        ].head(20))
    raise ValueError("Invalid route labels found. Review them before continuing.")


# Source: 01_operating_costs.ipynb, zero-based cell 11
# Standardize routes as departure-arrival.
costs["Route_ID"] = (
    route_compact.str[:3]
    + "-"
    + route_compact.str[3:])

print("Original route label count:",
      costs["Route_ID_Original"].nunique())

print("Standardized directional route count:",
      costs["Route_ID"].nunique())

display(
    costs[
        ["Cost_ID", "Route_ID_Original", "Route_ID"]
    ].head(10))


# Source: 01_operating_costs.ipynb, zero-based cell 12
# Confirm that route cleaning preserved all records and amounts.
assert len(costs) == len(costs_raw), "The row count changed."
assert costs["Amount"].equals(costs_raw["Amount"]), "The amounts changed."

print("Row count preserved:", len(costs))
print("Amount values unchanged: True")
print("Working columns:", costs.columns.tolist())


# Source: 01_operating_costs.ipynb, zero-based cell 13
# Convert dates and amounts to calculation-ready types.
parsed_dates = pd.to_datetime(costs["Cost_Date"], errors="coerce")
parsed_amounts = pd.to_numeric(costs["Amount"], errors="coerce")

print("Missing or invalid dates:", parsed_dates.isna().sum())
print("Missing or invalid amounts:", parsed_amounts.isna().sum())

assert parsed_dates.notna().all(), "Review missing or invalid dates."
assert parsed_amounts.notna().all(), "Review missing or invalid amounts."

costs["Cost_Date"] = parsed_dates
costs["Amount"] = parsed_amounts

print("\nDate range:")
print("Start:", costs["Cost_Date"].min())
print("End:", costs["Cost_Date"].max())

print("\nAmount range:")
print("Minimum:", costs["Amount"].min())
print("Maximum:", costs["Amount"].max())

print("\nNegative amounts:", (costs["Amount"] < 0).sum())
print("Zero amounts:", (costs["Amount"] == 0).sum())


# Source: 01_operating_costs.ipynb, zero-based cell 14
# Remove surrounding spaces from cost category labels.
costs["Cost_Type"] = costs["Cost_Type"].astype("string").str.strip()

expected_types = {"Crew", "Food", "Fuel", "Maintenance"}

print("Cost category counts:")
display(costs["Cost_Type"].value_counts(dropna=False))

assert costs["Cost_Type"].notna().all(), "Missing cost categories found."
assert set(costs["Cost_Type"].unique()) == expected_types, (
    "Unexpected cost categories found."
)

assert costs["Cost_ID"].notna().all(), "Missing Cost_ID values found."
assert costs["Cost_ID"].is_unique, "Duplicate Cost_ID values found."

print("Cost category and identifier checks passed.")


# Source: 01_operating_costs.ipynb, zero-based cell 15
# Validate each route-time combination before treating it as a flight.
flight_keys = ["Route_ID", "Cost_Date"]

flight_checks = (
    costs.groupby(flight_keys)
    .agg(
        RecordCount=("Cost_ID", "size"),
        CostTypeCount=("Cost_Type", "nunique"))
    .reset_index())

invalid_flights = flight_checks.loc[
    (flight_checks["RecordCount"] != 4)
    | (flight_checks["CostTypeCount"] != 4)]

print("Route-time combinations:", len(flight_checks))
print("Invalid combinations:", len(invalid_flights))

if not invalid_flights.empty:
    display(invalid_flights.head(20))
    raise ValueError("Review incomplete or duplicated flight cost records.")

print("All combinations contain four records and four cost categories.")


# Source: 01_operating_costs.ipynb, zero-based cell 16
# Reshape validated cost records into one row per inferred flight.
cost_columns = ["Crew", "Food", "Fuel", "Maintenance"]

flight_costs = (
    costs.pivot(
        index=flight_keys,
        columns="Cost_Type",
        values="Amount")
    .reset_index())

flight_costs.columns.name = None

# Calculate the total operating cost for each inferred flight.
flight_costs["OperatingCost"] = (
    flight_costs[cost_columns].sum(axis=1))

# Display flights in chronological order.
flight_costs = (
    flight_costs
    .sort_values(["Cost_Date", "Route_ID"])
    .reset_index(drop=True))

print("Inferred flight count:", len(flight_costs))
display(flight_costs.head())


# Source: 01_operating_costs.ipynb, zero-based cell 17
import numpy as np

# Reconcile totals before and after reshaping.
source_total = costs["Amount"].sum()
flight_total = flight_costs["OperatingCost"].sum()
difference = flight_total - source_total

print(f"Source operating cost: {source_total:,.2f}")
print(f"Flight table operating cost: {flight_total:,.2f}")
print(f"Difference: {difference:,.6f}")

assert np.isclose(
    source_total,
    flight_total,
    rtol=0,
    atol=0.01
), "Operating cost totals do not reconcile."

assert len(flight_costs) * 4 == len(costs), (
    "The record count does not match four records per flight."
)

print("Reconciliation checks passed.")


# Source: 01_operating_costs.ipynb, zero-based cell 18
# Add calendar month and departure airport.
flight_costs["Month"] = (
    flight_costs["Cost_Date"].dt.to_period("M").astype(str)
)

flight_costs["DepartureAirport"] = (
    flight_costs["Route_ID"].str[:3]
)

# The fiscal year starts on September 1.
fiscal_start_year = (
    flight_costs["Cost_Date"].dt.year
    - (flight_costs["Cost_Date"].dt.month < 9).astype(int)
)

flight_costs["FY"] = (
    "FY"
    + fiscal_start_year.astype(str)
    + "-"
    + ((fiscal_start_year + 1) % 100).astype(str).str.zfill(2)
)

display(
    flight_costs[
        ["Cost_Date", "Month", "FY", "Route_ID", "DepartureAirport"]
    ].head()
)

print("Fiscal year flight counts:")
display(flight_costs["FY"].value_counts().sort_index())

print("First month:", flight_costs["Month"].min())
print("Last month:", flight_costs["Month"].max())
print("Observed month count:", flight_costs["Month"].nunique())


# Source: 01_operating_costs.ipynb, zero-based cell 19
# Summarize costs and flight counts by month and directional route.
route_monthly_costs = (
    flight_costs.groupby(
        ["Month", "FY", "Route_ID", "DepartureAirport"],
        as_index=False
    )
    .agg(
        CrewCost=("Crew", "sum"),
        FoodCost=("Food", "sum"),
        FuelCost=("Fuel", "sum"),
        MaintenanceCost=("Maintenance", "sum"),
        OperatingCost=("OperatingCost", "sum"),
        FlightCount=("OperatingCost", "size")))

# Calculate average operating cost per flight.
route_monthly_costs["CostPerFlight"] = (
    route_monthly_costs["OperatingCost"]
    / route_monthly_costs["FlightCount"])

route_monthly_costs = (
    route_monthly_costs
    .sort_values(["Month", "Route_ID"])
    .reset_index(drop=True))

display(route_monthly_costs.head(10).round(2))

print("Summary rows:", len(route_monthly_costs))


# Source: 01_operating_costs.ipynb, zero-based cell 20
# Inspect monthly results for one directional route.
example_route = route_monthly_costs.loc[
    route_monthly_costs["Route_ID"] == "YVR-YLW",
    [
        "Month",
        "CrewCost",
        "FoodCost",
        "FuelCost",
        "MaintenanceCost",
        "OperatingCost",
        "FlightCount",
        "CostPerFlight"]]

display(example_route.head(6).round(2))



# Source: 01_operating_costs.ipynb, zero-based cell 21
# Summarize company operating costs by fiscal year.
annual_costs = (
    flight_costs.groupby("FY", as_index=False)
    .agg(
        CrewCost=("Crew", "sum"),
        FoodCost=("Food", "sum"),
        FuelCost=("Fuel", "sum"),
        MaintenanceCost=("Maintenance", "sum"),
        OperatingCost=("OperatingCost", "sum"),
        FlightCount=("OperatingCost", "size")
    )
    .sort_values("FY")
    .reset_index(drop=True)
)

annual_costs["CostPerFlight"] = (
    annual_costs["OperatingCost"]
    / annual_costs["FlightCount"]
)

display(annual_costs.round(2))


# Source: 01_operating_costs.ipynb, zero-based cell 22
# Verify that aggregation preserved total costs and flight counts.
assert np.isclose(
    route_monthly_costs["OperatingCost"].sum(),
    flight_costs["OperatingCost"].sum(),
    rtol=0,
    atol=0.01
), "Monthly route cost totals do not reconcile."

assert (
    route_monthly_costs["FlightCount"].sum() == len(flight_costs)
), "Monthly route flight counts do not reconcile."

assert np.isclose(
    annual_costs["OperatingCost"].sum(),
    flight_costs["OperatingCost"].sum(),
    rtol=0,
    atol=0.01
), "Annual cost totals do not reconcile."

assert (
    annual_costs["FlightCount"].sum() == len(flight_costs)
), "Annual flight counts do not reconcile."

assert not route_monthly_costs.duplicated(
    ["Month", "Route_ID"]
).any(), "Duplicate month-route combinations found."

print("All summary checks passed.")


# Source: 01_operating_costs.ipynb, zero-based cell 23
# Compare the two fiscal years.
annual_indexed = annual_costs.set_index("FY")

previous = annual_indexed.loc["FY2024-25"]
current = annual_indexed.loc["FY2025-26"]

metrics = [
    "CrewCost",
    "FoodCost",
    "FuelCost",
    "MaintenanceCost",
    "OperatingCost",
    "FlightCount",
    "CostPerFlight"
]

annual_comparison = pd.DataFrame({
    "PreviousYear": previous[metrics],
    "CurrentYear": current[metrics]
})

annual_comparison["Change"] = (
    annual_comparison["CurrentYear"]
    - annual_comparison["PreviousYear"]
)

annual_comparison["GrowthPct"] = (
    annual_comparison["Change"]
    / annual_comparison["PreviousYear"]
    * 100
)

annual_comparison.index.name = "Metric"

display(annual_comparison.round(2))


# Source: 01_operating_costs.ipynb, zero-based cell 24
# Summarize company operating costs by month.
monthly_costs = (
    flight_costs.groupby(["Month", "FY"], as_index=False)
    .agg(
        CrewCost=("Crew", "sum"),
        FoodCost=("Food", "sum"),
        FuelCost=("Fuel", "sum"),
        MaintenanceCost=("Maintenance", "sum"),
        OperatingCost=("OperatingCost", "sum"),
        FlightCount=("OperatingCost", "size")
    )
    .sort_values("Month")
    .reset_index(drop=True)
)

monthly_costs["CostPerFlight"] = (
    monthly_costs["OperatingCost"]
    / monthly_costs["FlightCount"]
)

assert np.isclose(
    monthly_costs["OperatingCost"].sum(),
    flight_costs["OperatingCost"].sum(),
    rtol=0,
    atol=0.01
), "Monthly operating costs do not reconcile."

assert monthly_costs["FlightCount"].sum() == len(flight_costs), (
    "Monthly flight counts do not reconcile."
)

print("Observed months:", len(monthly_costs))
display(monthly_costs.round(2))


# Source: 01_operating_costs.ipynb, zero-based cell 25
# Display floating-point values with separators and two decimal places.
pd.options.display.float_format = "{:,.2f}".format

display(annual_comparison)


# Source: 01_operating_costs.ipynb, zero-based cell 27
# Select the four operating cost categories.
category_names = [
    "CrewCost",
    "FoodCost",
    "FuelCost",
    "MaintenanceCost"
]

cost_increase_breakdown = (
    annual_comparison.loc[category_names, ["Change", "GrowthPct"]]
    .copy()
)

# Calculate each category's share of the total cost increase.
total_cost_increase = annual_comparison.loc[
    "OperatingCost", "Change"
]

assert total_cost_increase > 0, "Total operating costs did not increase."

cost_increase_breakdown["ShareOfIncreasePct"] = (
    cost_increase_breakdown["Change"]
    / total_cost_increase
    * 100
)

cost_increase_breakdown = (
    cost_increase_breakdown
    .sort_values("Change", ascending=False)
)

# Confirm that the category increases equal the total increase.
assert np.isclose(
    cost_increase_breakdown["Change"].sum(),
    total_cost_increase,
    rtol=0,
    atol=0.01
), "Category increases do not reconcile."

display(cost_increase_breakdown.round(2))


# Source: 01_operating_costs.ipynb, zero-based cell 29
# Summarize operating costs by fiscal year and directional route.
route_annual_costs = (
    flight_costs.groupby(["FY", "Route_ID"], as_index=False)
    .agg(
        CrewCost=("Crew", "sum"),
        FoodCost=("Food", "sum"),
        FuelCost=("Fuel", "sum"),
        MaintenanceCost=("Maintenance", "sum"),
        OperatingCost=("OperatingCost", "sum"),
        FlightCount=("OperatingCost", "size"),
        ActiveMonths=("Month", "nunique")
    )
)

route_annual_costs["CostPerFlight"] = (
    route_annual_costs["OperatingCost"]
    / route_annual_costs["FlightCount"]
)

route_annual_costs = (
    route_annual_costs
    .sort_values(["FY", "Route_ID"])
    .reset_index(drop=True)
)

display(route_annual_costs.head(10))

# Reconcile route totals with company totals.
route_fy_totals = (
    route_annual_costs.groupby("FY")[
        ["OperatingCost", "FlightCount"]
    ]
    .sum()
    .sort_index()
)

company_fy_totals = (
    annual_costs.set_index("FY")[
        ["OperatingCost", "FlightCount"]
    ]
    .sort_index()
)

assert route_fy_totals.index.equals(company_fy_totals.index)

assert np.allclose(
    route_fy_totals["OperatingCost"],
    company_fy_totals["OperatingCost"],
    rtol=0,
    atol=0.01
), "Route costs do not reconcile with company costs."

assert route_fy_totals["FlightCount"].equals(
    company_fy_totals["FlightCount"]
), "Route flight counts do not reconcile."

print("Route annual reconciliation passed.")


# Source: 01_operating_costs.ipynb, zero-based cell 30
# Select the metrics needed for year-over-year comparison.
comparison_columns = [
    "Route_ID",
    "OperatingCost",
    "FlightCount",
    "CostPerFlight",
    "ActiveMonths"
]

previous_routes = route_annual_costs.loc[
    route_annual_costs["FY"] == "FY2024-25",
    comparison_columns
].copy()

current_routes = route_annual_costs.loc[
    route_annual_costs["FY"] == "FY2025-26",
    comparison_columns
].copy()

# Keep all routes, including those observed in only one fiscal year.
route_comparison = previous_routes.merge(
    current_routes,
    on="Route_ID",
    how="outer",
    suffixes=("_Previous", "_Current"),
    validate="one_to_one",
    indicator=True
)

print("Route coverage across fiscal years:")
display(route_comparison["_merge"].value_counts())

# Treat absent records as zero observed costs and flights.
# Average cost per flight remains undefined when no flights are observed.
for metric in ["OperatingCost", "FlightCount", "ActiveMonths"]:
    columns = [
        f"{metric}_Previous",
        f"{metric}_Current"
    ]
    route_comparison[columns] = (
        route_comparison[columns].fillna(0)
    )

for metric in ["FlightCount", "ActiveMonths"]:
    for period in ["Previous", "Current"]:
        column = f"{metric}_{period}"
        route_comparison[column] = (
            route_comparison[column].astype(int)
        )

display(route_comparison.head())


# Source: 01_operating_costs.ipynb, zero-based cell 31
# Calculate absolute changes.
route_comparison["CostChange"] = (
    route_comparison["OperatingCost_Current"]
    - route_comparison["OperatingCost_Previous"]
)

route_comparison["FlightChange"] = (
    route_comparison["FlightCount_Current"]
    - route_comparison["FlightCount_Previous"]
)

route_comparison["CostPerFlightChange"] = (
    route_comparison["CostPerFlight_Current"]
    - route_comparison["CostPerFlight_Previous"]
)

# Calculate growth rates only when the previous value is positive.
for metric, output_column in [
    ("OperatingCost", "CostGrowthPct"),
    ("FlightCount", "FlightGrowthPct"),
    ("CostPerFlight", "CostPerFlightGrowthPct")
]:
    previous_values = route_comparison[f"{metric}_Previous"]
    current_values = route_comparison[f"{metric}_Current"]

    valid_base = previous_values.where(previous_values > 0)

    route_comparison[output_column] = (
        (current_values - previous_values)
        / valid_base
        * 100
    )

# Reconcile the total route cost change.
assert np.isclose(
    route_comparison["CostChange"].sum(),
    total_cost_increase,
    rtol=0,
    atol=0.01
), "Route cost changes do not reconcile."

route_comparison = (
    route_comparison
    .sort_values("CostChange", ascending=False)
    .reset_index(drop=True)
)

result_columns = [
    "Route_ID",
    "ActiveMonths_Previous",
    "ActiveMonths_Current",
    "OperatingCost_Previous",
    "OperatingCost_Current",
    "CostChange",
    "FlightCount_Previous",
    "FlightCount_Current",
    "FlightChange",
    "CostPerFlight_Previous",
    "CostPerFlight_Current",
    "CostPerFlightGrowthPct"
]

display(route_comparison[result_columns].head(10).round(2))

print("Total route cost increase:",
      f"{route_comparison['CostChange'].sum():,.2f}")


# Source: 01_operating_costs.ipynb, zero-based cell 32
# Separate routes observed in both fiscal years from other routes.
has_both_years = (
    (route_comparison["FlightCount_Previous"] > 0)
    & (route_comparison["FlightCount_Current"] > 0)
)

route_decomposition = route_comparison.loc[
    has_both_years
].copy()

# Step 1: change flight counts while holding previous average costs.
route_decomposition["FlightCountEffect"] = (
    route_decomposition["FlightCount_Current"]
    - route_decomposition["FlightCount_Previous"]
) * route_decomposition["CostPerFlight_Previous"]

# Step 2: change average costs using current flight counts.
route_decomposition["AverageCostEffect"] = (
    route_decomposition["FlightCount_Current"]
    * (
        route_decomposition["CostPerFlight_Current"]
        - route_decomposition["CostPerFlight_Previous"]
    )
)

route_decomposition["ExplainedChange"] = (
    route_decomposition["FlightCountEffect"]
    + route_decomposition["AverageCostEffect"]
)

assert np.allclose(
    route_decomposition["ExplainedChange"],
    route_decomposition["CostChange"],
    rtol=0,
    atol=0.01
), "Route cost decomposition does not reconcile."

# Retain changes for routes without observations in both years.
other_routes = route_comparison.loc[~has_both_years].copy()

explained_total = (
    route_decomposition["ExplainedChange"].sum()
    + other_routes["CostChange"].sum()
)

assert np.isclose(
    explained_total,
    total_cost_increase,
    rtol=0,
    atol=0.01
), "Company cost decomposition does not reconcile."

print("Routes observed in both years:", len(route_decomposition))
print("Other routes:", len(other_routes))
print("Decomposition checks passed.")

display(
    route_decomposition[
        [
            "Route_ID",
            "ActiveMonths_Previous",
            "ActiveMonths_Current",
            "CostChange",
            "FlightCountEffect",
            "AverageCostEffect"
        ]
    ]
    .sort_values("CostChange", ascending=False)
    .head(10)
    .round(2)
)


# Source: 01_operating_costs.ipynb, zero-based cell 33
# Summarize the accounting decomposition across routes.
decomposition_summary = pd.DataFrame({
    "Component": [
        "Flight count changes at previous route costs",
        "Average cost changes at current flight counts",
        "Routes without observations in both years"
    ],
    "Amount": [
        route_decomposition["FlightCountEffect"].sum(),
        route_decomposition["AverageCostEffect"].sum(),
        other_routes["CostChange"].sum()
    ]
})

decomposition_summary["ShareOfNetIncreasePct"] = (
    decomposition_summary["Amount"]
    / total_cost_increase
    * 100
)

display(decomposition_summary.round(2))

print("Total operating cost increase:",
      f"{total_cost_increase:,.2f}")


# Source: 01_operating_costs.ipynb, zero-based cell 35
# Count departures by month and airport for gate-rent allocation.
airport_monthly_departures = (
    flight_costs.groupby(
        ["Month", "FY", "DepartureAirport"],
        as_index=False
    )
    .agg(
        DepartureFlightCount=("OperatingCost", "size")
    )
    .sort_values(["Month", "DepartureAirport"])
    .reset_index(drop=True)
)

assert (
    airport_monthly_departures["DepartureFlightCount"].sum()
    == len(flight_costs)
), "Airport departure counts do not reconcile."

display(airport_monthly_departures.head(10))

print("Airport departure count check passed.")


cost_tables = {
    "flight_costs.csv": flight_costs,
    "route_monthly_costs.csv": route_monthly_costs,
    "airport_monthly_departures.csv": airport_monthly_departures,
    "monthly_costs.csv": monthly_costs,
    "annual_costs.csv": annual_costs,
    "annual_comparison.csv": annual_comparison.reset_index(),
    "route_annual_costs.csv": route_annual_costs,
    "route_comparison.csv": route_comparison,
    "cost_increase_breakdown.csv": cost_increase_breakdown.reset_index(),
    "route_decomposition.csv": route_decomposition,
    "decomposition_summary.csv": decomposition_summary,
}
for name, table in cost_tables.items():
    base = "data/processed" if name == "route_monthly_costs.csv" else "results/operating_costs"
    compare(table, ROOT / base / name)

# Integration: final restoration stage, followed by scenario analysis.


# Source: 02_team_integration.ipynb, zero-based cell 19
import io
import pandas as pd
import numpy as np

pd.options.display.float_format = "{:,.2f}".format

# Read committed upstream inputs; costs come from this fresh run.
def read_uploaded_csv(filename):
    base = OUTPUT if filename == "route_monthly_costs.csv" else ROOT / "data/processed"
    return pd.read_csv(base / filename, encoding="utf-8-sig")

cost_work = read_uploaded_csv("route_monthly_costs.csv")

transactions_audit = read_uploaded_csv(
    "transactions_deduplicated_audit.csv"
)

date_candidates = read_uploaded_csv(
    "transaction_date_candidates.csv"
)

gate_allocations = read_uploaded_csv(
    "NorthByte_Route_Gate_Rent_Allocations.csv"
)

gate_unallocated = read_uploaded_csv(
    "NorthByte_UnallocatedRent.csv"
)

gate_fiscal_summary = read_uploaded_csv(
    "NorthByte_Gate_Rent_FY_Summary.csv"
)

gate_reconciliation = read_uploaded_csv(
    "NorthByte_Gate_Rent_Reconciliation.csv"
)

# Check required fields.
required_columns = {
    "cost_work": {
        "Month", "Route_ID", "OperatingCost", "FlightCount"
    },
    "transactions_audit": {
        "Transaction_ID", "Route_ID", "Amount"
    },
    "date_candidates": {
        "Transaction_ID", "candidate_date",
        "candidate_fiscal_year"
    },
    "gate_allocations": {
        "Month", "Route_ID", "Scenario", "AllocatedGateRent"
    },
    "gate_unallocated": {
        "Month", "DepartureAirport", "Scenario", "UnallocatedRent"
    },
    "gate_fiscal_summary": {
        "FY", "Scenario", "TotalRent",
        "AllocatedGateRent", "UnallocatedRent"
    },
    "gate_reconciliation": {
        "Month", "DepartureAirport", "Scenario",
        "TotalRent", "AllocatedGateRent", "UnallocatedRent"
    }
}

for table_name, columns in required_columns.items():
    missing_columns = columns - set(globals()[table_name].columns)
    assert not missing_columns, (
        f"{table_name}: missing columns {missing_columns}"
    )

# Standardize directional route IDs.
def standardize_routes(series):
    codes = (
        series.astype("string")
        .str.upper()
        .str.replace(r"[^A-Z]", "", regex=True)
    )
    assert codes.notna().all(), "Missing route IDs."
    assert codes.str.fullmatch(r"[A-Z]{6}").all(), (
        "Invalid route IDs."
    )
    return codes.str[:3] + "-" + codes.str[3:]

for table in [cost_work, transactions_audit, gate_allocations]:
    table["Route_ID"] = standardize_routes(table["Route_ID"])

# Standardize month values.
for table in [
    cost_work,
    gate_allocations,
    gate_unallocated,
    gate_reconciliation
]:
    table["Month"] = (
        pd.to_datetime(table["Month"], errors="raise")
        .dt.to_period("M")
        .astype(str)
    )

# Validate numeric fields.
numeric_fields = {
    "cost_work": ["OperatingCost", "FlightCount"],
    "transactions_audit": ["Amount"],
    "gate_allocations": ["AllocatedGateRent"],
    "gate_unallocated": ["UnallocatedRent"],
    "gate_fiscal_summary": [
        "TotalRent", "AllocatedGateRent", "UnallocatedRent"
    ],
    "gate_reconciliation": [
        "TotalRent", "AllocatedGateRent", "UnallocatedRent"
    ]
}

for table_name, columns in numeric_fields.items():
    table = globals()[table_name]
    for column in columns:
        table[column] = pd.to_numeric(
            table[column], errors="raise"
        )
        assert np.isfinite(table[column]).all(), (
            f"{table_name}: invalid values in {column}"
        )

# Validate unique keys and source totals.
assert not cost_work.duplicated(["Month", "Route_ID"]).any()
assert transactions_audit["Transaction_ID"].notna().all()
assert transactions_audit["Transaction_ID"].is_unique

assert not gate_allocations.duplicated(
    ["Month", "Route_ID", "Scenario"]
).any()

assert not gate_fiscal_summary.duplicated(
    ["FY", "Scenario"]
).any()

assert not gate_reconciliation.duplicated(
    ["Month", "DepartureAirport", "Scenario"]
).any()

assert len(cost_work) == 1260
assert len(transactions_audit) == 558129
assert len(date_candidates) == 564189
assert len(gate_allocations) == 3780

assert np.isclose(
    cost_work["OperatingCost"].sum(),
    431362040.24,
    rtol=0,
    atol=0.01
), "Operating cost total does not match."

assert np.isclose(
    cost_work["FlightCount"].sum(),
    28801,
    rtol=0,
    atol=0
), "Flight count does not match."

assert np.isclose(
    transactions_audit["Amount"].sum(),
    370629024.85,
    rtol=0,
    atol=0.01
), "Net revenue total does not match."

assert np.allclose(
    gate_reconciliation["AllocatedGateRent"]
    + gate_reconciliation["UnallocatedRent"],
    gate_reconciliation["TotalRent"],
    rtol=0,
    atol=0.01
), "Gate rent reconciliation failed."

# Confirm that each rent scenario covers the cost route-months.
expected_keys = set(
    cost_work[["Month", "Route_ID"]]
    .itertuples(index=False, name=None)
)

assert set(gate_allocations["Scenario"]) == {
    "Low", "Base", "High"
}

for scenario, table in gate_allocations.groupby("Scenario"):
    actual_keys = set(
        table[["Month", "Route_ID"]]
        .itertuples(index=False, name=None)
    )
    assert actual_keys == expected_keys, (
        f"Route-month coverage mismatch: {scenario}"
    )

print("Data restoration checks passed.")
print(f"Cost route-months: {len(cost_work):,}")
print(f"Total flights: {cost_work['FlightCount'].sum():,.0f}")
print(
    "Total operating cost: "
    f"CAD {cost_work['OperatingCost'].sum():,.2f}"
)
print(f"Unique transactions: {len(transactions_audit):,}")
print(
    "Total net transaction revenue: "
    f"CAD {transactions_audit['Amount'].sum():,.2f}"
)
print(f"Gate allocation rows: {len(gate_allocations):,}")

print("\nFiscal-year gate rent summary:")
display(
    gate_fiscal_summary[
        [
            "FY", "Scenario", "TotalRent",
            "AllocatedGateRent", "UnallocatedRent"
        ]
    ].sort_values(["FY", "Scenario"]).reset_index(drop=True)
)


# Source: 02_team_integration.ipynb, zero-based cell 20
# Validate date candidates before rebuilding revenue bounds.
assert not date_candidates.duplicated(
    ["Transaction_ID", "candidate_date"]
).any()

assert set(date_candidates["Transaction_ID"]) == set(
    transactions_audit["Transaction_ID"]
)

# Keep each transaction once per possible fiscal year.
transaction_fy = (
    date_candidates[
        ["Transaction_ID", "candidate_fiscal_year"]
    ]
    .drop_duplicates()
    .rename(columns={"candidate_fiscal_year": "FY"})
    .copy()
)

assert transaction_fy["FY"].notna().all()
assert set(transaction_fy["FY"]) == {
    "FY2024-25", "FY2025-26"
}

transaction_fy["PossibleFYCount"] = (
    transaction_fy.groupby("Transaction_ID")["FY"]
    .transform("size")
)

assert transaction_fy["PossibleFYCount"].isin([1, 2]).all()

transaction_fy = transaction_fy.merge(
    transactions_audit[["Transaction_ID", "Route_ID", "Amount"]],
    on="Transaction_ID",
    how="left",
    validate="many_to_one"
)

fy_is_certain = transaction_fy["PossibleFYCount"].eq(1)

transaction_fy["NetRevenueLower"] = np.where(
    fy_is_certain,
    transaction_fy["Amount"],
    np.minimum(transaction_fy["Amount"], 0.0)
)

transaction_fy["NetRevenueUpper"] = np.where(
    fy_is_certain,
    transaction_fy["Amount"],
    np.maximum(transaction_fy["Amount"], 0.0)
)

route_fiscal_revenue_bounds = (
    transaction_fy.groupby(["FY", "Route_ID"], as_index=False)[
        ["NetRevenueLower", "NetRevenueUpper"]
    ].sum()
)

# Reconcile FY revenue bounds.
fiscal_revenue_bounds = (
    route_fiscal_revenue_bounds.groupby("FY")[
        ["NetRevenueLower", "NetRevenueUpper"]
    ].sum().sort_index()
)

assert np.allclose(
    fiscal_revenue_bounds.to_numpy(),
    [
        [179939246.53, 181375714.90],
        [189253309.95, 190689778.32]
    ],
    rtol=0,
    atol=0.01
), "Fiscal revenue bounds do not reconcile."

# Assign fiscal years from monthly dates.
def fiscal_year_from_month(month_series):
    dates = pd.to_datetime(
        month_series, format="%Y-%m", errors="raise"
    )
    start_year = dates.dt.year - (dates.dt.month < 9).astype(int)
    return (
        "FY" + start_year.astype(str)
        + "-" + ((start_year + 1) % 100).astype(str).str.zfill(2)
    )

cost_fiscal_work = cost_work.copy()
cost_fiscal_work["FY"] = fiscal_year_from_month(
    cost_fiscal_work["Month"]
)

gate_fiscal_work = gate_allocations.copy()
gate_fiscal_work["FY"] = fiscal_year_from_month(
    gate_fiscal_work["Month"]
)

# Summarize operating costs and flights by FY and route.
route_fiscal_costs = (
    cost_fiscal_work.groupby(["FY", "Route_ID"], as_index=False)[
        ["OperatingCost", "FlightCount"]
    ].sum()
)

# Summarize allocated rent by FY, route, and scenario.
route_fiscal_gates = (
    gate_fiscal_work.groupby(
        ["FY", "Route_ID", "Scenario"],
        as_index=False
    )["AllocatedGateRent"].sum()
)

# Merge revenue and operating costs.
route_fiscal_core = route_fiscal_revenue_bounds.merge(
    route_fiscal_costs,
    on=["FY", "Route_ID"],
    how="outer",
    validate="one_to_one",
    indicator=True
)

assert route_fiscal_core["_merge"].eq("both").all(), (
    "FY route revenue and cost coverage do not match."
)

route_fiscal_core = route_fiscal_core.drop(columns="_merge")

# Add the three alternative rent scenarios.
route_fiscal_results = route_fiscal_gates.merge(
    route_fiscal_core,
    on=["FY", "Route_ID"],
    how="outer",
    validate="many_to_one",
    indicator=True
)

assert route_fiscal_results["_merge"].eq("both").all(), (
    "FY route rent coverage does not match."
)

route_fiscal_results = route_fiscal_results.drop(columns="_merge")

route_fiscal_results["AfterGateResultLower"] = (
    route_fiscal_results["NetRevenueLower"]
    - route_fiscal_results["OperatingCost"]
    - route_fiscal_results["AllocatedGateRent"]
)

route_fiscal_results["AfterGateResultUpper"] = (
    route_fiscal_results["NetRevenueUpper"]
    - route_fiscal_results["OperatingCost"]
    - route_fiscal_results["AllocatedGateRent"]
)

# Build company results using TOTAL rent, including unallocated rent.
fiscal_costs = (
    route_fiscal_costs.groupby("FY", as_index=False)[
        ["OperatingCost", "FlightCount"]
    ].sum()
)

company_core = fiscal_revenue_bounds.reset_index().merge(
    fiscal_costs,
    on="FY",
    validate="one_to_one"
)

company_fiscal_results = gate_fiscal_summary[
    ["FY", "Scenario", "TotalRent", "AllocatedGateRent", "UnallocatedRent"]
].merge(
    company_core,
    on="FY",
    validate="many_to_one"
)

company_fiscal_results["AfterGateResultLower"] = (
    company_fiscal_results["NetRevenueLower"]
    - company_fiscal_results["OperatingCost"]
    - company_fiscal_results["TotalRent"]
)

company_fiscal_results["AfterGateResultUpper"] = (
    company_fiscal_results["NetRevenueUpper"]
    - company_fiscal_results["OperatingCost"]
    - company_fiscal_results["TotalRent"]
)

# Check that route results reconcile to company results.
route_totals = (
    route_fiscal_results.groupby(["FY", "Scenario"], as_index=False)[
        [
            "AllocatedGateRent",
            "AfterGateResultLower",
            "AfterGateResultUpper"
        ]
    ].sum()
)

reconciliation_check = company_fiscal_results.merge(
    route_totals,
    on=["FY", "Scenario"],
    validate="one_to_one",
    suffixes=("_Company", "_Routes")
)

assert np.allclose(
    reconciliation_check["AllocatedGateRent_Company"],
    reconciliation_check["AllocatedGateRent_Routes"],
    rtol=0,
    atol=0.01
)

for bound in ["Lower", "Upper"]:
    assert np.allclose(
        reconciliation_check[f"AfterGateResult{bound}_Routes"]
        - reconciliation_check["UnallocatedRent"],
        reconciliation_check[f"AfterGateResult{bound}_Company"],
        rtol=0,
        atol=0.01
    ), f"Company reconciliation failed: {bound}"

print("Fiscal integration checks passed.")

print("\nCompany fiscal-year results:")
display(
    company_fiscal_results[
        [
            "FY", "Scenario",
            "NetRevenueLower", "NetRevenueUpper",
            "OperatingCost", "TotalRent",
            "AfterGateResultLower", "AfterGateResultUpper"
        ]
    ].sort_values(["FY", "Scenario"]).reset_index(drop=True)
)

print("\nFY2025-26: lowest upper results under Base rent:")
display(
    route_fiscal_results.loc[
        route_fiscal_results["FY"].eq("FY2025-26")
        & route_fiscal_results["Scenario"].eq("Base"),
        [
            "Route_ID", "FlightCount",
            "NetRevenueLower", "NetRevenueUpper",
            "OperatingCost", "AllocatedGateRent",
            "AfterGateResultLower", "AfterGateResultUpper"
        ]
    ].sort_values("AfterGateResultUpper").head(10).reset_index(drop=True)
)


# Source: 02_team_integration.ipynb, zero-based cell 21
# Combine both directions into an airport pair.
pair_work = route_fiscal_results.copy()

pair_work["AirportPair"] = pair_work["Route_ID"].apply(
    lambda route: "-".join(sorted(route.split("-")))
)

pair_fiscal_results = (
    pair_work.groupby(
        ["FY", "Scenario", "AirportPair"],
        as_index=False
    )[
        [
            "FlightCount",
            "NetRevenueLower",
            "NetRevenueUpper",
            "OperatingCost",
            "AllocatedGateRent",
            "AfterGateResultLower",
            "AfterGateResultUpper"
        ]
    ].sum()
)

# Check that combining directions preserves all financial totals.
financial_columns = [
    "NetRevenueLower",
    "NetRevenueUpper",
    "OperatingCost",
    "AllocatedGateRent",
    "AfterGateResultLower",
    "AfterGateResultUpper"
]

direction_totals = (
    route_fiscal_results.groupby(["FY", "Scenario"])[
        financial_columns
    ].sum().sort_index()
)

pair_totals = (
    pair_fiscal_results.groupby(["FY", "Scenario"])[
        financial_columns
    ].sum().sort_index()
)

assert np.allclose(
    direction_totals.to_numpy(),
    pair_totals.to_numpy(),
    rtol=0,
    atol=0.01
), "Airport pair totals do not reconcile."

# Use all rent scenarios to classify each pair.
pair_sensitivity = (
    pair_fiscal_results.groupby(
        ["FY", "AirportPair"],
        as_index=False
    ).agg(
        WorstCaseResult=("AfterGateResultLower", "min"),
        BestCaseResult=("AfterGateResultUpper", "max"),
        ScenarioCount=("Scenario", "nunique")
    )
)

assert pair_sensitivity["ScenarioCount"].eq(3).all()

pair_sensitivity["ResultStatus"] = np.select(
    [
        pair_sensitivity["BestCaseResult"] < -0.01,
        pair_sensitivity["WorstCaseResult"] > 0.01
    ],
    [
        "Loss across all scenarios",
        "Profit across all scenarios"
    ],
    default="Break-even or scenario-sensitive"
)

# Prepare the current FY ranking under Base rent.
current_pair_results = (
    pair_fiscal_results.loc[
        pair_fiscal_results["FY"].eq("FY2025-26")
        & pair_fiscal_results["Scenario"].eq("Base")
    ]
    .merge(
        pair_sensitivity[
            [
                "FY", "AirportPair",
                "WorstCaseResult", "BestCaseResult", "ResultStatus"
            ]
        ],
        on=["FY", "AirportPair"],
        validate="one_to_one"
    )
    .sort_values("AfterGateResultUpper")
    .reset_index(drop=True)
)

assert len(current_pair_results) == 27

print("Airport pair checks passed.")
print(f"Current fiscal-year airport pairs: {len(current_pair_results)}")

print("\nCurrent FY status across all scenarios:")
display(
    current_pair_results["ResultStatus"]
    .value_counts()
    .rename_axis("ResultStatus")
    .to_frame("AirportPairCount")
)

print("\nFY2025-26: lowest upper results under Base rent:")
display(
    current_pair_results[
        [
            "AirportPair",
            "FlightCount",
            "NetRevenueLower",
            "NetRevenueUpper",
            "OperatingCost",
            "AllocatedGateRent",
            "AfterGateResultLower",
            "AfterGateResultUpper",
            "ResultStatus"
        ]
    ].head(10)
)


# Source: 02_team_integration.ipynb, zero-based cell 22
# Select the four pairs with the lowest upper results under Base rent.
priority_pairs = (
    current_pair_results.head(4)["AirportPair"].tolist()
)

priority_pair_comparison = (
    pair_fiscal_results.loc[
        pair_fiscal_results["Scenario"].eq("Base")
        & pair_fiscal_results["AirportPair"].isin(priority_pairs)
    ]
    .copy()
)

assert priority_pair_comparison["FlightCount"].gt(0).all()
assert len(priority_pair_comparison) == 8

# Calculate annual averages per recorded flight.
priority_pair_comparison["RevenuePerFlightLower"] = (
    priority_pair_comparison["NetRevenueLower"]
    / priority_pair_comparison["FlightCount"]
)

priority_pair_comparison["RevenuePerFlightUpper"] = (
    priority_pair_comparison["NetRevenueUpper"]
    / priority_pair_comparison["FlightCount"]
)

priority_pair_comparison["OperatingCostPerFlight"] = (
    priority_pair_comparison["OperatingCost"]
    / priority_pair_comparison["FlightCount"]
)

priority_pair_comparison["GateRentPerFlight"] = (
    priority_pair_comparison["AllocatedGateRent"]
    / priority_pair_comparison["FlightCount"]
)

priority_pair_comparison["ResultPerFlightLower"] = (
    priority_pair_comparison["AfterGateResultLower"]
    / priority_pair_comparison["FlightCount"]
)

priority_pair_comparison["ResultPerFlightUpper"] = (
    priority_pair_comparison["AfterGateResultUpper"]
    / priority_pair_comparison["FlightCount"]
)

priority_pair_comparison = (
    priority_pair_comparison.sort_values(["AirportPair", "FY"])
    .reset_index(drop=True)
)

print("Priority pair comparison under Base rent:")
display(
    priority_pair_comparison[
        [
            "AirportPair",
            "FY",
            "FlightCount",
            "NetRevenueLower",
            "NetRevenueUpper",
            "OperatingCost",
            "AllocatedGateRent",
            "AfterGateResultLower",
            "AfterGateResultUpper"
        ]
    ]
)

print("\nAnnual financial averages per recorded flight:")
display(
    priority_pair_comparison[
        [
            "AirportPair",
            "FY",
            "FlightCount",
            "RevenuePerFlightLower",
            "RevenuePerFlightUpper",
            "OperatingCostPerFlight",
            "GateRentPerFlight",
            "ResultPerFlightLower",
            "ResultPerFlightUpper"
        ]
    ].round(2)
)


# Source: 02_team_integration.ipynb, zero-based cell 23
# Compare the two fiscal years for the four priority airport pairs.
comparison_columns = [
    "AirportPair",
    "FlightCount",
    "NetRevenueLower",
    "NetRevenueUpper",
    "OperatingCost",
    "AllocatedGateRent",
    "AfterGateResultLower",
    "AfterGateResultUpper",
    "OperatingCostPerFlight"
]

previous = priority_pair_comparison.loc[
    priority_pair_comparison["FY"].eq("FY2024-25"),
    comparison_columns
]

current = priority_pair_comparison.loc[
    priority_pair_comparison["FY"].eq("FY2025-26"),
    comparison_columns
]

priority_pair_changes = previous.merge(
    current,
    on="AirportPair",
    validate="one_to_one",
    suffixes=("_Previous", "_Current")
)

priority_pair_changes["FlightIncrease"] = (
    priority_pair_changes["FlightCount_Current"]
    - priority_pair_changes["FlightCount_Previous"]
)

priority_pair_changes["FlightGrowthPct"] = (
    priority_pair_changes["FlightIncrease"]
    / priority_pair_changes["FlightCount_Previous"]
    * 100
)

# Conservative change bounds: current lower minus previous upper,
# and current upper minus previous lower.
priority_pair_changes["RevenueChangeLower"] = (
    priority_pair_changes["NetRevenueLower_Current"]
    - priority_pair_changes["NetRevenueUpper_Previous"]
)

priority_pair_changes["RevenueChangeUpper"] = (
    priority_pair_changes["NetRevenueUpper_Current"]
    - priority_pair_changes["NetRevenueLower_Previous"]
)

priority_pair_changes["OperatingCostIncrease"] = (
    priority_pair_changes["OperatingCost_Current"]
    - priority_pair_changes["OperatingCost_Previous"]
)

priority_pair_changes["CostPerFlightGrowthPct"] = (
    priority_pair_changes["OperatingCostPerFlight_Current"]
    / priority_pair_changes["OperatingCostPerFlight_Previous"]
    - 1
) * 100

priority_pair_changes["AllocatedRentChange"] = (
    priority_pair_changes["AllocatedGateRent_Current"]
    - priority_pair_changes["AllocatedGateRent_Previous"]
)

# Positive values indicate a larger financial deficit.
priority_pair_changes["DeficitIncreaseLower"] = (
    priority_pair_changes["AfterGateResultLower_Previous"]
    - priority_pair_changes["AfterGateResultUpper_Current"]
)

priority_pair_changes["DeficitIncreaseUpper"] = (
    priority_pair_changes["AfterGateResultUpper_Previous"]
    - priority_pair_changes["AfterGateResultLower_Current"]
)

priority_pair_changes = priority_pair_changes.sort_values(
    "DeficitIncreaseLower",
    ascending=False
).reset_index(drop=True)

print("Priority airport pair changes under Base rent:")
display(
    priority_pair_changes[
        [
            "AirportPair",
            "FlightIncrease",
            "FlightGrowthPct",
            "RevenueChangeLower",
            "RevenueChangeUpper",
            "OperatingCostIncrease",
            "CostPerFlightGrowthPct",
            "AllocatedRentChange",
            "DeficitIncreaseLower",
            "DeficitIncreaseUpper"
        ]
    ].round(2)
)


# Source: 02_team_integration.ipynb, zero-based cell 30
# Prepare the current-year baseline for the four priority airport pairs.
action_baseline = current_pair_results.loc[
    current_pair_results["AirportPair"].isin(
        priority_pair_changes["AirportPair"]
    ),
    [
        "AirportPair",
        "FlightCount",
        "NetRevenueLower",
        "NetRevenueUpper",
        "OperatingCost",
        "AllocatedGateRent",
        "AfterGateResultLower",
        "AfterGateResultUpper"
    ]
].copy()

assert len(action_baseline) == 4
assert action_baseline["FlightCount"].gt(0).all()

action_baseline["OperatingCostPerFlight"] = (
    action_baseline["OperatingCost"]
    / action_baseline["FlightCount"]
)

action_baseline["RevenuePerFlightLower"] = (
    action_baseline["NetRevenueLower"]
    / action_baseline["FlightCount"]
)

action_baseline["RevenuePerFlightUpper"] = (
    action_baseline["NetRevenueUpper"]
    / action_baseline["FlightCount"]
)

# Screening threshold under an illustrative assumption:
# revenue lost per removed flight equals current annual average revenue.
# Gate rent remains unchanged.
action_baseline["AvoidableCostThresholdLowerPct"] = (
    action_baseline["RevenuePerFlightLower"]
    / action_baseline["OperatingCostPerFlight"]
    * 100
)

action_baseline["AvoidableCostThresholdUpperPct"] = (
    action_baseline["RevenuePerFlightUpper"]
    / action_baseline["OperatingCostPerFlight"]
    * 100
)

action_baseline = action_baseline.sort_values(
    "AfterGateResultUpper"
).reset_index(drop=True)

print("Frequency-adjustment screening baseline:")
display(
    action_baseline[
        [
            "AirportPair",
            "FlightCount",
            "OperatingCostPerFlight",
            "RevenuePerFlightLower",
            "RevenuePerFlightUpper",
            "AvoidableCostThresholdLowerPct",
            "AvoidableCostThresholdUpperPct"
        ]
    ].round(2)
)

print(
    "\nIllustrative screening only: "
    "annual average revenue is not matched flight revenue."
)
print(
    "Gate rent is assumed unchanged. "
    "Network effects and implementation costs are not included."
)


# Source: 02_team_integration.ipynb, zero-based cell 31
# Illustrative frequency-reduction sensitivity analysis.
reduction_target = 0.10
avoidable_cost_rates = [0.40, 0.60, 0.80]

scenario_rows = []

for _, row in action_baseline.iterrows():
    # Remove flights in pairs to preserve equal directional reductions.
    removed_flights = int(
        np.floor(row["FlightCount"] * reduction_target / 2) * 2
    )

    actual_reduction_rate = removed_flights / row["FlightCount"]

    revenue_lost_lower = (
        actual_reduction_rate * row["NetRevenueLower"]
    )

    revenue_lost_upper = (
        actual_reduction_rate * row["NetRevenueUpper"]
    )

    for avoidable_rate in avoidable_cost_rates:
        operating_cost_saved = (
            actual_reduction_rate
            * row["OperatingCost"]
            * avoidable_rate
        )

        scenario_rows.append({
            "AirportPair": row["AirportPair"],
            "RemovedFlights": removed_flights,
            "FlightReductionPct": actual_reduction_rate * 100,
            "AvoidableCostPct": avoidable_rate * 100,
            "OperatingCostSaved": operating_cost_saved,
            "RevenueLostLower": revenue_lost_lower,
            "RevenueLostUpper": revenue_lost_upper,
            "ImprovementLower": (
                operating_cost_saved - revenue_lost_upper
            ),
            "ImprovementUpper": (
                operating_cost_saved - revenue_lost_lower
            )
        })

frequency_scenarios = pd.DataFrame(scenario_rows)

frequency_scenarios["ScenarioStatus"] = np.select(
    [
        frequency_scenarios["ImprovementLower"] > 0.01,
        frequency_scenarios["ImprovementUpper"] < -0.01
    ],
    [
        "Improves across revenue bounds",
        "Worsens across revenue bounds"
    ],
    default="Break-even or date-sensitive"
)

frequency_scenario_totals = (
    frequency_scenarios.groupby(
        "AvoidableCostPct",
        as_index=False
    )[
        [
            "RemovedFlights",
            "OperatingCostSaved",
            "RevenueLostLower",
            "RevenueLostUpper",
            "ImprovementLower",
            "ImprovementUpper"
        ]
    ].sum()
)

print("Illustrative scenarios by airport pair:")
display(
    frequency_scenarios[
        [
            "AirportPair",
            "RemovedFlights",
            "FlightReductionPct",
            "AvoidableCostPct",
            "ImprovementLower",
            "ImprovementUpper",
            "ScenarioStatus"
        ]
    ].round(2)
)

print("\nCombined impact across the four airport pairs:")
display(frequency_scenario_totals.round(2))

print(
    "\nAssumptions: removed flights have annual average revenue "
    "and operating cost; gate rent is unchanged."
)
print(
    "Even flight counts support a paired-removal assumption, "
    "but do not establish a feasible timetable."
)
print(
    "Network effects, revenue recapture, implementation costs "
    "and customer impacts are excluded."
)


# Source: 02_team_integration.ipynb, zero-based cell 34
# Prepare monthly costs without changing the existing cost table.
category_work = cost_work.copy()

category_work["FY"] = fiscal_year_from_month(
    category_work["Month"]
)

category_work["AirportPair"] = category_work["Route_ID"].apply(
    lambda route: "-".join(sorted(route.split("-")))
)

cost_categories = [
    "FuelCost",
    "CrewCost",
    "MaintenanceCost",
    "FoodCost"
]

# Validate category amounts and reconcile them to operating costs.
for column in cost_categories:
    category_work[column] = pd.to_numeric(
        category_work[column],
        errors="raise"
    )
    assert np.isfinite(category_work[column]).all()

assert np.allclose(
    category_work[cost_categories].sum(axis=1),
    category_work["OperatingCost"],
    rtol=0,
    atol=0.02
), "Cost categories do not reconcile to operating costs."

# Summarize the four priority pairs by fiscal year.
priority_cost_summary = (
    category_work.loc[
        category_work["AirportPair"].isin(
            action_baseline["AirportPair"]
        )
    ]
    .groupby(["AirportPair", "FY"], as_index=False)[
        cost_categories + ["OperatingCost", "FlightCount"]
    ]
    .sum()
)

assert len(priority_cost_summary) == 8
assert priority_cost_summary["FlightCount"].gt(0).all()

previous_costs = (
    priority_cost_summary.loc[
        priority_cost_summary["FY"].eq("FY2024-25")
    ].set_index("AirportPair")
)

current_costs = (
    priority_cost_summary.loc[
        priority_cost_summary["FY"].eq("FY2025-26")
    ].set_index("AirportPair")
)

category_rows = []

for pair in action_baseline["AirportPair"]:
    previous = previous_costs.loc[pair]
    current = current_costs.loc[pair]

    total_cost_increase = (
        current["OperatingCost"] - previous["OperatingCost"]
    )

    assert total_cost_increase > 0

    for category in cost_categories:
        previous_per_flight = (
            previous[category] / previous["FlightCount"]
        )
        current_per_flight = (
            current[category] / current["FlightCount"]
        )

        increase = current[category] - previous[category]

        category_rows.append({
            "AirportPair": pair,
            "CostCategory": category,
            "PreviousCost": previous[category],
            "CurrentCost": current[category],
            "CostIncrease": increase,
            "ShareOfPairCostIncreasePct": (
                increase / total_cost_increase * 100
            ),
            "PreviousCostPerFlight": previous_per_flight,
            "CurrentCostPerFlight": current_per_flight,
            "CostPerFlightGrowthPct": (
                current_per_flight / previous_per_flight - 1
            ) * 100
        })

priority_cost_category_changes = pd.DataFrame(category_rows)

# Check category increases against the earlier pair comparison.
category_increase_check = (
    priority_cost_category_changes.groupby("AirportPair")[
        "CostIncrease"
    ].sum().sort_index()
)

expected_increase = (
    priority_pair_changes.set_index("AirportPair")[
        "OperatingCostIncrease"
    ].sort_index()
)

assert np.allclose(
    category_increase_check.to_numpy(),
    expected_increase.to_numpy(),
    rtol=0,
    atol=0.02
), "Category increases do not match the earlier analysis."

# Summarize category increases across all four pairs.
priority_category_totals = (
    priority_cost_category_changes.groupby(
        "CostCategory",
        as_index=False
    )[["PreviousCost", "CurrentCost", "CostIncrease"]]
    .sum()
    .sort_values("CostIncrease", ascending=False)
    .reset_index(drop=True)
)

priority_category_totals["ShareOfTotalIncreasePct"] = (
    priority_category_totals["CostIncrease"]
    / priority_category_totals["CostIncrease"].sum()
    * 100
)

print("Priority cost category checks passed.")

print("\nCombined cost increases across the four priority pairs:")
display(priority_category_totals.round(2))

print("\nCategory increases by airport pair:")
display(
    priority_cost_category_changes[
        [
            "AirportPair",
            "CostCategory",
            "CostIncrease",
            "ShareOfPairCostIncreasePct"
        ]
    ].round(2)
)

print("\nAverage category costs per recorded flight:")
display(
    priority_cost_category_changes[
        [
            "AirportPair",
            "CostCategory",
            "PreviousCostPerFlight",
            "CurrentCostPerFlight",
            "CostPerFlightGrowthPct"
        ]
    ].round(2)
)

# Save the new analysis.
output_directory = Path("/content/integration_outputs")
output_directory.mkdir(parents=True, exist_ok=True)

priority_cost_category_changes.to_csv(
    output_directory / "priority_cost_category_changes.csv",
    index=False,
    encoding="utf-8-sig"
)

priority_category_totals.to_csv(
    output_directory / "priority_cost_category_totals.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\nTwo cost analysis CSV files saved.")


# Source: 02_team_integration.ipynb, zero-based cell 35
# Identify pairs with positive results across all tested scenarios.
positive_pair_results = (
    current_pair_results.loc[
        current_pair_results["ResultStatus"].eq(
            "Profit across all scenarios"
        )
    ]
    .copy()
    .sort_values("AfterGateResultLower", ascending=False)
    .reset_index(drop=True)
)

assert len(positive_pair_results) == 12

print("FY2025-26 positive airport pairs under Base rent:")
display(
    positive_pair_results[
        [
            "AirportPair",
            "FlightCount",
            "NetRevenueLower",
            "NetRevenueUpper",
            "OperatingCost",
            "AllocatedGateRent",
            "AfterGateResultLower",
            "AfterGateResultUpper"
        ]
    ].round(2)
)

# Summarize positive and negative groups without netting them together.
network_group_summary = (
    current_pair_results.groupby(
        "ResultStatus",
        as_index=False
    ).agg(
        AirportPairCount=("AirportPair", "size"),
        FlightCount=("FlightCount", "sum"),
        AfterGateResultLower=("AfterGateResultLower", "sum"),
        AfterGateResultUpper=("AfterGateResultUpper", "sum")
    )
)

# Check that group results reconcile to the company Base scenario.
company_base = company_fiscal_results.loc[
    company_fiscal_results["FY"].eq("FY2025-26")
    & company_fiscal_results["Scenario"].eq("Base")
]

assert len(company_base) == 1

for bound in ["Lower", "Upper"]:
    assert np.isclose(
        network_group_summary[f"AfterGateResult{bound}"].sum()
        - company_base["UnallocatedRent"].iloc[0],
        company_base[f"AfterGateResult{bound}"].iloc[0],
        rtol=0,
        atol=0.01
    ), f"Network group reconciliation failed: {bound}"

print("\nNetwork group financial results under Base rent:")
display(network_group_summary.round(2))

positive_pair_results.to_csv(
    output_directory / "positive_airport_pair_results.csv",
    index=False,
    encoding="utf-8-sig"
)

network_group_summary.to_csv(
    output_directory / "network_group_summary.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\nNetwork analysis checks passed. Two CSV files saved.")



integration_tables = {
    "company_fiscal_results.csv": company_fiscal_results,
    "route_fiscal_results.csv": route_fiscal_results,
    "pair_fiscal_results.csv": pair_fiscal_results,
    "pair_sensitivity.csv": pair_sensitivity,
    "current_pair_results.csv": current_pair_results,
    "priority_pair_comparison.csv": priority_pair_comparison,
    "priority_pair_changes.csv": priority_pair_changes,
    "route_fiscal_revenue_bounds.csv": route_fiscal_revenue_bounds,
    "frequency_adjustment_baseline.csv": action_baseline,
    "frequency_adjustment_scenarios.csv": frequency_scenarios,
    "frequency_adjustment_totals.csv": frequency_scenario_totals,
    "priority_cost_category_changes.csv": priority_cost_category_changes,
    "priority_cost_category_totals.csv": priority_category_totals,
    "positive_airport_pair_results.csv": positive_pair_results,
    "network_group_summary.csv": network_group_summary,
}
for name, table in integration_tables.items():
    compare(table, ROOT / "results/integration" / name)

report = {
    "scope": "Raw costs to cost summaries; archived upstream revenue/gate inputs to integrated results",
    "upstream_transaction_and_gate_rebuild": "not performed",
    "environment": {"python": platform.python_version(), "pandas": pd.__version__,
                    "numpy": np.__version__, "openpyxl": openpyxl.__version__},
    "tables_compared": len(checks), "checks": checks,
    "inferred_flights": int(cost_work["FlightCount"].sum()),
    "operating_cost_cad": float(cost_work["OperatingCost"].sum()),
    "unique_transactions": len(transactions_audit),
    "net_transaction_revenue_cad": float(transactions_audit["Amount"].sum()),
}
(OUTPUT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"\nPASS: {len(checks)} complete output tables match the competition archive.")
print(f"Report: {OUTPUT / 'validation.json'}")
