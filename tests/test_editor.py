import unittest
from editor import auto_segments

class TestSegments(unittest.TestCase):
    def test_three_non_overlapping(self):
        cuts = auto_segments(600, 3, 70)
        self.assertEqual(len(cuts), 3)
        self.assertTrue(all(start >= 0 and start+duration <= 600 for start,duration in cuts))
        self.assertTrue(all(cuts[i][0]+cuts[i][1] <= cuts[i+1][0] for i in range(2)))
    def test_short(self):
        self.assertEqual(auto_segments(30,3,70), [(0.,10.),(10.,10.),(20.,10.)])

if __name__ == "__main__":
    unittest.main()
