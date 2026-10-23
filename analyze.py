"""Turn ADC samples into voltage, TMP36 temperature, and a small report."""
from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

TMP36_ZERO_V = 0.5
TMP36_C_PER_V = 100.0


@dataclass(frozen=True)
class Reading:
    time_s: float
    adc_count: int
    voltage_v: float
    temperature_c: float


def load_csv(path: Path, adc_max: int, vref: float) -> list[Reading]:
    """Read time/count samples and convert them with the TMP36 transfer curve."""
    if adc_max <= 0:
        raise ValueError("ADC maximum count must be greater than zero.")
    if not math.isfinite(vref) or vref <= 0:
        raise ValueError("Reference voltage must be finite and greater than zero.")

    readings: list[Reading] = []
    previous_time = -math.inf
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            required = {"time_s", "adc_count"}
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise ValueError("CSV must contain the columns: time_s, adc_count.")
            for line_number, row in enumerate(reader, start=2):
                try:
                    time_s = float(row["time_s"])
                    raw_count = float(row["adc_count"])
                except (TypeError, ValueError) as error:
                    raise ValueError(f"Line {line_number}: time_s and adc_count must be numbers.") from error
                if not math.isfinite(time_s) or time_s < 0:
                    raise ValueError(f"Line {line_number}: time_s must be finite and non-negative.")
                if time_s < previous_time:
                    raise ValueError(f"Line {line_number}: time_s must be in chronological order.")
                if not math.isfinite(raw_count) or not raw_count.is_integer():
                    raise ValueError(f"Line {line_number}: adc_count must be a whole number.")
                adc_count = int(raw_count)
                if not 0 <= adc_count <= adc_max:
                    raise ValueError(f"Line {line_number}: adc_count must be between 0 and {adc_max}.")

                voltage = adc_count / adc_max * vref
                temperature = (voltage - TMP36_ZERO_V) * TMP36_C_PER_V
                if not math.isfinite(voltage) or not math.isfinite(temperature):
                    raise ValueError(f"Line {line_number}: conversion produced a non-finite value.")
                readings.append(Reading(time_s, adc_count, voltage, temperature))
                previous_time = time_s
    except OSError as error:
        raise ValueError(f"Could not read '{path}': {error}") from error

    if not readings:
        raise ValueError("CSV contains no readings.")
    return readings


def summarize(readings: list[Reading], high_temp_c: float | None = None) -> dict[str, float | int | None]:
    """Summarize the readings, optionally counting values over a threshold."""
    if not readings:
        raise ValueError("At least one reading is required.")
    if high_temp_c is not None and not math.isfinite(high_temp_c):
        raise ValueError("Temperature threshold must be finite.")

    voltages = [reading.voltage_v for reading in readings]
    temperatures = [reading.temperature_c for reading in readings]
    return {
        "count": len(readings),
        "duration_s": readings[-1].time_s - readings[0].time_s,
        "voltage_min": min(voltages),
        "voltage_average": sum(voltages) / len(voltages),
        "voltage_max": max(voltages),
        "temperature_min": min(temperatures),
        "temperature_average": sum(temperatures) / len(temperatures),
        "temperature_max": max(temperatures),
        "high_temp_count": (
            sum(temperature > high_temp_c for temperature in temperatures)
            if high_temp_c is not None
            else None
        ),
    }


def write_report(
    summary: dict[str, float | int | None], output_path: Path, high_temp_c: float | None
) -> None:
    """Write a Markdown summary beside the chart."""
    def fmt(key: str, digits: int = 3) -> str:
        return f"{float(summary[key]):.{digits}f}"

    alert = ""
    if high_temp_c is not None:
        count = int(summary["high_temp_count"] or 0)
        alert = f"\n- Readings above **{high_temp_c:.2f} °C**: {count}\n"

    content = f"""# Sensor Data Report

- Readings: **{summary['count']}**
- Capture duration: **{fmt('duration_s')} s**
- Voltage (min / average / max): **{fmt('voltage_min')} / {fmt('voltage_average')} / {fmt('voltage_max')} V**
- TMP36 temperature (min / average / max): **{fmt('temperature_min')} / {fmt('temperature_average')} / {fmt('temperature_max')} °C**{alert}

![Temperature over time](temperature_chart.svg)

## Conversion used

voltage = adc_count / adc_max × reference_voltage  
TMP36 temperature (°C) = (voltage - 0.5) × 100

This report uses the TMP36 model. Sensor tolerances and ADC calibration can affect real measurements.
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def write_temperature_chart(readings: list[Reading], output_path: Path) -> None:
    """Draw a temperature-over-time chart as a standalone SVG file."""
    if not readings:
        raise ValueError("At least one reading is needed to draw a chart.")

    width, height = 900, 500
    left, right, top, bottom = 82, 35, 42, 72
    plot_width, plot_height = width - left - right, height - top - bottom
    times = [reading.time_s for reading in readings]
    temperatures = [reading.temperature_c for reading in readings]
    x_min, x_max = min(times), max(times)
    y_min, y_max = min(temperatures), max(temperatures)
    if x_min == x_max:
        x_min, x_max = x_min - 0.5, x_max + 0.5
    if y_min == y_max:
        y_min, y_max = y_min - 0.5, y_max + 0.5
    y_pad = (y_max - y_min) * 0.08
    y_min, y_max = y_min - y_pad, y_max + y_pad

    def x_pixel(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_width

    def y_pixel(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    points = " ".join(
        f"{x_pixel(reading.time_s):.1f},{y_pixel(reading.temperature_c):.1f}" for reading in readings
    )
    grid: list[str] = []
    for index in range(5):
        fraction = index / 4
        y = top + fraction * plot_height
        value = y_max - fraction * (y_max - y_min)
        grid.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid" />'
            f'<text x="{left-12}" y="{y+5:.1f}" text-anchor="end" class="tick">{value:.1f}</text>'
        )
    for index in range(5):
        fraction = index / 4
        x = left + fraction * plot_width
        value = x_min + fraction * (x_max - x_min)
        grid.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height-bottom}" class="grid" />'
            f'<text x="{x:.1f}" y="{height-bottom+24}" text-anchor="middle" class="tick">{value:.1f}</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">TMP36 temperature over time</title>
<desc id="desc">Line chart of {len(readings)} temperature readings from {times[0]:.2f} to {times[-1]:.2f} seconds.</desc>
<style>
  text {{ font-family: Arial, sans-serif; fill: #243247; }}
  .title {{ font-size: 22px; font-weight: 700; }} .tick {{ font-size: 12px; fill: #56657a; }}
  .grid {{ stroke: #dce3ec; stroke-width: 1; }} .axis {{ stroke: #6b7788; stroke-width: 1.5; }}
  .line {{ fill: none; stroke: #087e8b; stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }}
</style>
<rect width="100%" height="100%" fill="#ffffff" />
<text x="{width/2}" y="28" text-anchor="middle" class="title">TMP36 Temperature Over Time</text>
{''.join(grid)}
<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" class="axis" />
<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" class="axis" />
<polyline points="{points}" class="line" />
<text x="{width/2}" y="{height-18}" text-anchor="middle">Time (s)</text>
<text x="20" y="{height/2}" text-anchor="middle" transform="rotate(-90 20 {height/2})">Temperature (°C)</text>
</svg>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert ADC counts into voltage and TMP36 temperature."
    )
    parser.add_argument("csv_file", type=Path, help="CSV with time_s and adc_count columns")
    parser.add_argument("--vref", type=float, default=3.3, help="ADC reference voltage (default: 3.3 V)")
    parser.add_argument("--adc-max", type=int, default=4095, help="maximum ADC count (default: 4095 for 12-bit)")
    parser.add_argument("--high-temp-c", type=float, help="count readings above this temperature in °C")
    parser.add_argument("--output-dir", type=Path, default=Path("results"), help="directory for report and SVG")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.high_temp_c is not None and not math.isfinite(args.high_temp_c):
        parser.error("--high-temp-c must be a finite number.")
    try:
        readings = load_csv(args.csv_file, args.adc_max, args.vref)
    except ValueError as error:
        parser.error(str(error))

    summary = summarize(readings, args.high_temp_c)
    chart_path = args.output_dir / "temperature_chart.svg"
    report_path = args.output_dir / "report.md"
    write_temperature_chart(readings, chart_path)
    write_report(summary, report_path, args.high_temp_c)
    print(f"Analyzed {summary['count']} readings over {float(summary['duration_s']):.2f} s.")
    print(f"Average temperature: {float(summary['temperature_average']):.2f} °C")
    if args.high_temp_c is not None:
        print(f"Readings above {args.high_temp_c:.2f} °C: {summary['high_temp_count']}")
    print(f"Report: {report_path}")
    print(f"Chart:  {chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
