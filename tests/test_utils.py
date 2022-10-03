import pytest
import utils

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
])
def test_decimal_numbers(input, expected):
    assert utils.numberToStrCSV(input) == expected.replace('\xa0', utils.thousands_separator)
