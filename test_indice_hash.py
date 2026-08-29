import os
import tempfile
import unittest

from indice_hash import StaticHashIndex, custom_hash, load_words


class StaticHashIndexTests(unittest.TestCase):
    def setUp(self):
        self.words = [f"word-{i}" for i in range(37)]
        self.index = StaticHashIndex(page_size=5, bucket_capacity=3)
        self.index.build(self.words)

    def test_nb_satisfies_rule(self):
        self.assertGreater(self.index.nb, self.index.nr / self.index.bucket_capacity)
        self.assertEqual(self.index.page_count, 8)

    def test_every_key_is_reachable(self):
        for word in self.words:
            result = self.index.search(word)
            self.assertTrue(result["found"], word)
            self.assertIn(word, result["page_records"])

    def test_collision_and_overflow_are_counted(self):
        self.assertGreater(self.index.collision_events, 0)
        self.assertGreater(self.index.overflow_bucket_count, 0)
        self.assertGreater(self.index.overflow_rate, 0)

    def test_scan_and_index_find_same_page(self):
        for word in (self.words[0], self.words[-1], "missing"):
            indexed = self.index.search(word)
            scanned = self.index.table_scan(word)
            self.assertEqual(indexed["found"], scanned["found"])
            self.assertEqual(indexed["page"], scanned["page"])

    def test_hash_is_deterministic_and_bounded_after_modulo(self):
        self.assertEqual(custom_hash("Davi"), custom_hash("davi"))
        for word in self.words:
            self.assertGreaterEqual(self.index.bucket_number(word), 0)
            self.assertLess(self.index.bucket_number(word), self.index.nb)

    def test_load_words_discards_empty_and_duplicate_lines(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as file:
            file.write("Alpha\n\nalpha\nBeta\n")
            path = file.name
        try:
            self.assertEqual(load_words(path), ["Alpha", "Beta"])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
