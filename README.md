# Sensor Data Analyzer

Analyze a small lab CSV of ADC readings, convert the counts into voltage and TMP36 temperature, and produce a Markdown summary plus a self-contained SVG chart. The project uses only Python's standard library.

## Requirements

- Python 3.10 or newer

## Quick start

```powershell
python analyze.py sample_data/temperature_readings.csv --output-dir results --high-temp-c 30
```

The command creates `results/report.md` and `results/temperature_chart.svg`. Open the SVG in any browser. Use `python analyze.py --help` to see calibration options.

## CSV format

The input needs two columns: `time_s` and `adc_count`. `time_s` is elapsed time in seconds. `adc_count` is the raw reading from a 12-bit ADC by default. The sample assumes a 3.3 V reference and a TMP36 temperature sensor.

```csv
time_s,adc_count
0,870
1,875
2,884
```

Change `--vref` and `--adc-max` to match your board. For an ADC with `n` bits, the maximum count is normally `2**n - 1`.

## What it reports

- Number of readings and capture duration
- Minimum, average, and maximum sensor voltage
- Minimum, average, and maximum estimated temperature
- Optional count of readings above a temperature threshold
- A temperature-over-time SVG plot with no plotting package required

## Calibration formulas

```text
voltage = adc_count / adc_max × reference_voltage
TMP36 temperature (°C) = (voltage - 0.5) × 100
```

These are educational calculations. Real ADCs and sensors have tolerances, and a different sensor requires a different conversion formula.

## Run the checks

```powershell
python -m unittest discover -s tests -v
```

## Project layout

```text
analyze.py                         CSV processing, report, chart, CLI
sample_data/temperature_readings.csv
tests/test_analyzer.py
```

## Learning goals

Practice reading CSV files, validating data, converting ADC values into physical units, summarizing measurements, writing a report, generating SVG, and testing each step.
