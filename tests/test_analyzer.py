import tempfile
import unittest
from pathlib import Path

from analyze import load_csv, summarize, write_report, write_temperature_chart


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp_dir.cleanup)
        self.csv_path = Path(self.temp_dir.name) / "readings.csv"

    def test_load_and_convert_adc_readings(self):
        self.csv_path.write_text("time_s,adc_count\n0,0\n1,2048\n", encoding="utf-8")
        readings = load_csv(self.csv_path, adc_max=4095, vref=3.3)
        self.assertAlmostEqual(readings[0].voltage_v, 0)
        self.assertAlmostEqual(readings[1].voltage_v, 2048 / 4095 * 3.3)
        self.assertAlmostEqual(readings[1].temperature_c, (2048 / 4095 * 3.3 - 0.5) * 100)

    def test_summary_and_threshold_count(self):
        self.csv_path.write_text("time_s,adc_count\n0,870\n1,1059\n", encoding="utf-8")
        readings = load_csv(self.csv_path, adc_max=4095, vref=3.3)
        result = summarize(readings, high_temp_c=30)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["duration_s"], 1)
        self.assertEqual(result["high_temp_count"], 1)

    def test_invalid_csv_values_are_rejected(self):
        cases = (
            "time_s,adc_count\n0,4096\n",
            "time_s,adc_count\n2,10\n1,11\n",
            "time_s,adc_count\n0,1.5\n",
            "time_s,adc_count\n0,not-a-number\n",
        )
        for content in cases:
            with self.subTest(content=content):
                self.csv_path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_csv(self.csv_path, adc_max=4095, vref=3.3)

    def test_non_finite_temperature_conversion_is_rejected(self):
        self.csv_path.write_text("time_s,adc_count\n0,1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "non-finite value"):
            load_csv(self.csv_path, adc_max=1, vref=1e308)

    def test_non_finite_temperature_threshold_is_rejected(self):
        self.csv_path.write_text("time_s,adc_count\n0,870\n", encoding="utf-8")
        readings = load_csv(self.csv_path, adc_max=4095, vref=3.3)
        with self.assertRaisesRegex(ValueError, "threshold must be finite"):
            summarize(readings, high_temp_c=float("inf"))

    def test_chart_is_created_for_constant_time_and_temperature(self):
        self.csv_path.write_text("time_s,adc_count\n0,1000\n0,1000\n", encoding="utf-8")
        readings = load_csv(self.csv_path, adc_max=4095, vref=3.3)
        chart_path = Path(self.temp_dir.name) / "chart.svg"
        write_temperature_chart(readings, chart_path)
        chart = chart_path.read_text(encoding="utf-8")
        self.assertIn("<svg", chart)
        self.assertIn("polyline", chart)

    def test_report_includes_summary_and_threshold_count(self):
        self.csv_path.write_text("time_s,adc_count\n0,870\n1,1059\n", encoding="utf-8")
        readings = load_csv(self.csv_path, adc_max=4095, vref=3.3)
        summary = summarize(readings, high_temp_c=30)
        report_path = Path(self.temp_dir.name) / "report.md"

        write_report(summary, report_path, high_temp_c=30)

        report = report_path.read_text(encoding="utf-8")
        self.assertIn("Readings: **2**", report)
        self.assertIn("Readings above **30.00 °C**: 1", report)
        self.assertIn("temperature_chart.svg", report)

    def test_empty_chart_input_is_rejected(self):
        chart_path = Path(self.temp_dir.name) / "empty.svg"
        with self.assertRaisesRegex(ValueError, "At least one reading"):
            write_temperature_chart([], chart_path)


if __name__ == "__main__":
    unittest.main()
