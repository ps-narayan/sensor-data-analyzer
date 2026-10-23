import tempfile
import unittest
from pathlib import Path

from analyze import load_csv, summarize, write_temperature_chart


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

    def test_chart_is_created_for_constant_time_and_temperature(self):
        self.csv_path.write_text("time_s,adc_count\n0,1000\n0,1000\n", encoding="utf-8")
        readings = load_csv(self.csv_path, adc_max=4095, vref=3.3)
        chart_path = Path(self.temp_dir.name) / "chart.svg"
        write_temperature_chart(readings, chart_path)
        chart = chart_path.read_text(encoding="utf-8")
        self.assertIn("<svg", chart)
        self.assertIn("polyline", chart)


if __name__ == "__main__":
    unittest.main()
