# Glow DCC Backfill

A Home Assistant custom integration that retrieves yesterday's half-hour electricity consumption from Glowmarkt/Bright DCC data and calculates usage and cost by tariff period.

This integration is intended for users whose Bright/Glowmarkt DCC data arrives with a delay and who want a reliable "yesterday" cost breakdown.

## Features

- Logs in directly with a Bright/Glowmarkt account
- Automatically discovers the electricity consumption resource
- Fetches yesterday's half-hour electricity readings
- Supports 1, 2, or 3 daily tariff rates
- Calculates:
  - total kWh
  - total cost
  - cheap kWh/cost
  - standard kWh/cost
  - peak kWh/cost
  - number of half-hour slots received
  - latest slot

## Requirements

- Home Assistant
- A Bright/Glowmarkt account
- A smart meter linked to Bright/Glowmarkt
- DCC electricity consumption data available in Bright

You do not need the Hildebrand Glow DCC integration installed.

You do not need a Glow CAD.

## Installation through HACS custom repository

1. Open HACS
2. Go to Integrations
3. Open the three-dot menu
4. Choose Custom repositories
5. Add this repository URL
6. Category: Integration
7. Install Glow DCC Backfill
8. Restart Home Assistant

## Setup

After restart:

1. Go to Settings → Devices & Services
2. Add Integration
3. Search for Glow DCC Backfill
4. Enter your Bright email and password
5. Select your electricity resource if more than one is found
6. Choose how many tariff rates you have per day
7. Enter your tariff rates and time windows

## Tariff types

### 1 rate per day

Use this for a flat tariff.

### 2 rates per day

Use this for day/night or Economy 7 style tariffs.

### 3 rates per day

Use this for cheap/standard/peak tariffs.

## Acknowledgements

Special thanks to the creators and contributors of the original Hildebrand Glow DCC Home Assistant integration, including the HandyHat `ha-hildebrandglow-dcc` project.

That integration helped show how Bright/Glowmarkt accounts expose virtual entities and resources, including the `electricity.consumption` resource used by this project.

Glow DCC Backfill is a separate integration focused specifically on delayed/backfilled half-hour DCC electricity data and tariff-based cost calculation.

This project is not affiliated with Hildebrand, Glowmarkt, Bright, Home Assistant, or the original Hildebrand Glow DCC integration.

Use at your own risk.

## License

MIT License.
