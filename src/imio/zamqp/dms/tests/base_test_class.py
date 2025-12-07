# -*- coding: utf-8 -*-
import unittest


class BaseTestClass(unittest.TestCase):
    """Common test methods for reuse in multiple test classes."""

    def check_categorized_element(self, obj, length=None, **kwargs):
        """Check that the categorized element is well created."""
        self.assertTrue(hasattr(obj, "categorized_elements"))
        if length is not None:
            self.assertEqual(len(obj.categorized_elements), length)
        values0 = obj.categorized_elements.itervalues().next()
        for key, value in kwargs.items():
            self.assertIn(key, values0)
            self.assertEqual(values0[key], value,
                             u"Mismatch for key '{}': '{}' <=> expected '{}'".format(key, values0[key], value))
