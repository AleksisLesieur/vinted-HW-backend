import unittest
import os
import tempfile
from datetime import datetime
import importlib.util

spec = importlib.util.spec_from_file_location("shipping_calculator", "shipping_discount_calculator.py")
shipping_calculator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shipping_calculator)

class TestShippingCalculator(unittest.TestCase):

    def setUp(self):
        self.test_file = tempfile.NamedTemporaryFile(delete=False, mode='w')
        
        self.test_input = [
            "2015-02-01 S MR",
            "2015-02-01 S LP",
            "2015-02-02 S MR",
            "2015-02-03 L LP",
            "2015-02-05 S LP",
            "2015-02-06 S MR",
            "2015-02-06 L LP",
            "2015-02-07 L MR",
            "2015-02-08 M MR",
            "2015-02-09 L LP",
            "2015-02-10 L LP",
            "2015-02-10 S MR",
            "2015-02-10 S MR",
            "2015-02-11 L LP",
            "2015-02-12 M MR",
            "2015-02-13 M LP",
            "2015-02-15 S MR",
            "2015-02-17 L LP",
            "2015-02-17 S MR",
            "2015-02-24 L LP",
            "2015-02-29 CUSPS",
            "2015-03-01 S MR"
        ]
        
        for line in self.test_input:
            self.test_file.write(line + "\n")
        self.test_file.close()
        
        self.expected_results = {
            "2015-02-01 S MR": (1.50, 0.50),
            "2015-02-01 S LP": (1.50, 0.00),
            "2015-02-02 S MR": (1.50, 0.50),
            "2015-02-03 L LP": (6.90, 0.00),
            "2015-02-05 S LP": (1.50, 0.00),
            "2015-02-06 S MR": (1.50, 0.50),
            "2015-02-06 L LP": (6.90, 0.00),
            "2015-02-07 L MR": (4.00, 0.00),
            "2015-02-08 M MR": (3.00, 0.00),
            "2015-02-09 L LP": (0.00, 6.90),
            "2015-02-10 L LP": (6.90, 0.00),
            "2015-02-10 S MR": (1.50, 0.50),
            "2015-02-10 S MR": (1.50, 0.50),
            "2015-02-11 L LP": (6.90, 0.00),
            "2015-02-12 M MR": (3.00, 0.00),
            "2015-02-13 M LP": (4.90, 0.00),
            "2015-02-15 S MR": (1.50, 0.50),
            "2015-02-17 L LP": (6.90, 0.00),
            "2015-02-17 S MR": (1.90, 0.10),
            "2015-02-24 L LP": (6.90, 0.00),
            "2015-03-01 S MR": (1.50, 0.50)
        }
        
        self.calculator = shipping_calculator.ShippingCalculator()

    def tearDown(self):
        os.unlink(self.test_file.name)

    def test_calculator_initialization(self):
        self.assertEqual(self.calculator.prices["LP"]["S"], 1.50)
        self.assertEqual(self.calculator.prices["MR"]["S"], 2.00)
        self.assertEqual(self.calculator.prices["LP"]["M"], 4.90)
        self.assertEqual(self.calculator.prices["MR"]["M"], 3.00)
        self.assertEqual(self.calculator.prices["LP"]["L"], 6.90)
        self.assertEqual(self.calculator.prices["MR"]["L"], 4.00)
        
        self.assertEqual(self.calculator.lowest_s_price, 1.50)

    def test_single_transaction_processing(self):
        line = "2015-02-01 S MR"
        date = datetime.strptime("2015-02-01", "%Y-%m-%d")
        result = self.calculator.process_transaction(line)
        expected = "2015-02-01 S MR 1.50 0.50"
        self.assertEqual(result, expected)
        
        self.calculator = shipping_calculator.ShippingCalculator()
        line = "2015-02-03 L LP"
        result = self.calculator.process_transaction(line)
        expected = "2015-02-03 L LP 6.90 -"
        self.assertEqual(result, expected)
        
        self.calculator = shipping_calculator.ShippingCalculator()
        line = "2015-02-29 CUSPS"
        result = self.calculator.process_transaction(line)
        expected = "2015-02-29 CUSPS Ignored"
        self.assertEqual(result, expected)

    def test_third_lp_l_free_rule(self):
        calculator = shipping_calculator.ShippingCalculator()
        
        result = calculator.process_transaction("2015-02-03 L LP")
        self.assertEqual(result, "2015-02-03 L LP 6.90 -")
        
        result = calculator.process_transaction("2015-02-06 L LP")
        self.assertEqual(result, "2015-02-06 L LP 6.90 -")
        
        result = calculator.process_transaction("2015-02-09 L LP")
        self.assertEqual(result, "2015-02-09 L LP 0.00 6.90")
        
        result = calculator.process_transaction("2015-02-10 L LP")
        self.assertEqual(result, "2015-02-10 L LP 6.90 -")

    def test_monthly_discount_cap(self):
        calculator = shipping_calculator.ShippingCalculator()
        
        for i in range(19):
            calculator.process_transaction(f"2015-02-{i+1:02d} S MR")
        
        total_discount = calculator.monthly_discounts["2015-02"]
        self.assertEqual(total_discount, 9.50)
        
        result = calculator.process_transaction("2015-02-20 S MR")
        
        total_discount = calculator.monthly_discounts["2015-02"]
        self.assertEqual(total_discount, 10.00)
        
        result = calculator.process_transaction("2015-02-21 S MR")
        self.assertEqual(result, "2015-02-21 S MR 2.00 -")

    def test_new_month_resets_cap(self):
        calculator = shipping_calculator.ShippingCalculator()
        
        for i in range(20):
            calculator.process_transaction(f"2015-02-{i+1:02d} S MR")
        
        self.assertEqual(calculator.monthly_discounts["2015-02"], 10.00)
        
        result = calculator.process_transaction("2015-03-01 S MR")
        self.assertEqual(result, "2015-03-01 S MR 1.50 0.50")
        
        self.assertEqual(calculator.monthly_discounts["2015-03"], 0.50)

    def test_calculator_directly(self):
        calculator = shipping_calculator.ShippingCalculator()
        
        results = []
        for line in self.test_input:
            result = calculator.process_transaction(line)
            results.append(result)
        
        for result in results:
            if "Ignored" in result:
                continue
                
            parts = result.split()
            original = " ".join(parts[:3])
            
            if original in self.expected_results:
                expected_price, expected_discount = self.expected_results[original]
                actual_price = float(parts[3])
                
                if parts[4] == "-":
                    actual_discount = 0.0
                else:
                    actual_discount = float(parts[4])
                
                self.assertAlmostEqual(actual_price, expected_price, places=2)
                self.assertAlmostEqual(actual_discount, expected_discount, places=2)

    def test_discount_calculation(self):
        calculator = shipping_calculator.ShippingCalculator()
        
        date = datetime.strptime("2015-01-01", "%Y-%m-%d")

        result = calculator.calculate_discount(date, "S", "MR")
        self.assertIsNotNone(result)
        base_price, discount, final_price = result
        self.assertEqual(base_price, 2.00)
        self.assertEqual(discount, 0.50)
        self.assertEqual(final_price, 1.50)
        
        month_key = calculator.get_month_key(date)

        result = calculator.calculate_discount(date, "L", "LP")
        self.assertEqual(calculator.monthly_lp_l_count[month_key], 1)
        base_price, discount, final_price = result
        self.assertEqual(discount, 0.0)

        result = calculator.calculate_discount(date, "L", "LP")
        self.assertEqual(calculator.monthly_lp_l_count[month_key], 2)
        base_price, discount, final_price = result
        self.assertEqual(discount, 0.0)

        result = calculator.calculate_discount(date, "L", "LP")
        self.assertEqual(calculator.monthly_lp_l_count[month_key], 3)
        base_price, discount, final_price = result
        self.assertEqual(discount, 6.90)
        self.assertEqual(final_price, 0.0)


if __name__ == "__main__":
    unittest.main()