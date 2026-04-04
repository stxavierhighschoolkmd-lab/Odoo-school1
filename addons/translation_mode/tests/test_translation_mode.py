from odoo.tests import tagged, TransactionCase
from odoo.tools.translate import LazyGettext, _, _lt


@tagged('post_install', '-at_install')
class TestTranslationMode(TransactionCase):
    def test_translation_mode_with_default_language(self):
        # No effect on translations missing from '.po' file
        self.assertEqual(_("test"), "test")
        self.assertEqual(_lt("test"), LazyGettext("test"))

        # No effect with default language
        self.assertEqual(_("translation mode test"), "translation mode test")
        self.assertEqual(str(_lt("translation mode test")), "translation mode test")

    def test_translation_mode_with_test_language(self):
        self.env.lang = 'test_fr'

        # No effect on translations missing from '.po' file
        self.assertEqual(_("test"), "test")
        self.assertEqual(_lt("test"), LazyGettext("test"))

        # Translations in '.po' file are wrapped
        self.assertEqual(_("translation mode test"), "_(translation_mode,1{translation mode test}[test du mode de traduction])")
        self.assertEqual(str(_lt("translation mode test")), "_(translation_mode,1{translation mode test}[test du mode de traduction])")
