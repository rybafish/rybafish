import pytest
import utils

utils.initLocale()

@pytest.mark.parametrize("input, expected", [
    (123, '123'),
    (1234, '1 234'),
    (1234567890, '1 234 567 890'),
    (1.25, '1'),
])
def test_integer_numbers(input, expected):
    assert utils.numberToStr(input) == expected.replace('\xa0', utils.thousands_separator)

@pytest.mark.parametrize("input, expected", [
    (123, '123'),
    (1.25, '1.25'),
    (1024.123, '1 024.123'),
    (1024.123000, '1 024.123'),
    (1024.123999, '1 024.123999'),
    (1024.1239993, '1 024.123999'),
    (1024.1239999, '1 024.124'),
    (-1024.1239999, '-1 024.124'),
    (3366788625, '3 366 788 625'),
    (-3366788625, '-3 366 788 625'),
    (1000010001.001, '1 000 010 001.001'),
    (-1000010001.001, '-1 000 010 001.001'),
])
def test_decimal_numbers(input, expected):
    assert utils.numberToStrCSV(input) == expected.replace('\xa0', utils.thousands_separator)

@pytest.mark.parametrize("input, expected", [
    (123, '123.00'),
#    (1.12345, '1.12'),
#    (1.789, '1.79'),
#    (1024, '1 024.00'),
#    (1024.0001, '1 024.00'),
#    (1024.123456, '1 024.12'),
#    (-1024.123456, '-1 024.12'),
])
def test_decimal_rounding(input, expected):
    assert utils.numberToStr(input, 2) == expected.replace('\xa0', utils.thousands_separator)

@pytest.mark.parametrize("input, expected", [
    (123, '123'),
    (1.25, '1.25'),
    (1024, '1024'),
    (1234567890, '1234567890'),
    (1024.123, '1024.123'),
    (1024.123000, '1024.123'),
    (1024.123456, '1024.123456'),
    (-1024.123456, '-1024.123456'),
])
def test_cvs_numbers(input, expected):
    assert utils.numberToStrCSV(input, False) == expected
