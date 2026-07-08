from odoo.tests import common, tagged

from ..models.phone_utils import normalize_phone


@tagged('post_install', '-at_install')
class TestPhoneUtils(common.TransactionCase):

    def test_international_plus(self):
        self.assertEqual(normalize_phone('+49 170 1234567'), '+491701234567')

    def test_double_zero_prefix(self):
        self.assertEqual(normalize_phone('0049 170 1234567'), '+491701234567')

    def test_national_with_leading_zero(self):
        self.assertEqual(normalize_phone('089 123456'), '+4989123456')

    def test_formatting_is_stripped(self):
        self.assertEqual(normalize_phone('(0170) 123-45 67'), '+491701234567')

    def test_anonymous_returns_none(self):
        self.assertIsNone(normalize_phone('anonymous'))
        self.assertIsNone(normalize_phone(''))
        self.assertIsNone(normalize_phone(None))

    def test_too_short_returns_none(self):
        self.assertIsNone(normalize_phone('123'))

    def test_suffix_is_stripped(self):
        self.assertEqual(normalize_phone('+491701234567@from-internal'), '+491701234567')

    def test_custom_country_prefix(self):
        self.assertEqual(normalize_phone('0701234567', default_country_prefix='43'),
                         '+43701234567')
