from django.test import SimpleTestCase

from documents.services.chunking import chunk_pages

LONG_TEXT = " ".join(f"Sentence number {i} is here." for i in range(200))


class ChunkPagesTests(SimpleTestCase):
    def test_short_page_becomes_one_chunk(self):
        chunks = chunk_pages([(1, "Office hours are on Monday.")])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].page_number, 1)
        self.assertEqual(chunks[0].text, "Office hours are on Monday.")

    def test_whitespace_is_normalized(self):
        chunks = chunk_pages([(1, "Line one.\n\n   Line   two.")])
        self.assertEqual(chunks[0].text, "Line one. Line two.")

    def test_empty_page_produces_no_chunks(self):
        self.assertEqual(chunk_pages([(1, "   ")]), [])

    def test_chunks_respect_size_and_keep_page_number(self):
        chunks = chunk_pages([(3, LONG_TEXT)], chunk_size=200, overlap=50)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.text), 200)
            self.assertEqual(chunk.page_number, 3)

    def test_consecutive_chunks_overlap(self):
        chunks = chunk_pages([(1, LONG_TEXT)], chunk_size=200, overlap=50)
        for current, following in zip(chunks, chunks[1:]):
            self.assertIn(following.text[:20], current.text)

    def test_no_sentence_is_lost(self):
        chunks = chunk_pages([(1, LONG_TEXT)], chunk_size=200, overlap=50)
        for i in range(200):
            sentence = f"Sentence number {i} is here."
            self.assertTrue(
                any(sentence in chunk.text for chunk in chunks),
                f"Missing: {sentence}",
            )

    def test_text_without_spaces_still_finishes(self):
        chunks = chunk_pages([(1, "x" * 2000)], chunk_size=500, overlap=100)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk.text) <= 500 for chunk in chunks))

    def test_chunks_never_cross_pages(self):
        chunks = chunk_pages([(1, "Alpha text."), (2, "Beta text.")])
        self.assertEqual(
            [(chunk.page_number, chunk.text) for chunk in chunks],
            [(1, "Alpha text."), (2, "Beta text.")],
        )
