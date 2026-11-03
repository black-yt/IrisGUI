import unittest

from scripts.grid_coordinates import GridCoordinateMap, GridTransform


class ContinuousGridTests(unittest.TestCase):
    def global_map(self, width=1000, height=1000):
        return GridCoordinateMap(transforms={"G": GridTransform(100, width, height)})

    def local_map(self):
        return GridCoordinateMap(transforms={"L": GridTransform(
            step=20, width=400, height=400,
            offset_x=300, offset_y=500,
            anchor_x=200, anchor_y=200, anchor_col=10, anchor_row=10,
        )})

    def test_global_decimal_column_and_row(self):
        points = self.global_map()
        for point_id, expected in [
            ("G-01.10-08", (110, 800)),
            ("G-01-08.32", (100, 832)),
            ("G-01.10-08.32", (110, 832)),
            ("G-1.1-8.32", (110, 832)),
        ]:
            with self.subTest(point_id=point_id):
                self.assertEqual(points.resolve(point_id), expected)

    def test_local_decimals_are_grid_fractions_relative_to_mouse_anchor(self):
        points = self.local_map()
        self.assertEqual(points.resolve("L-10-10.32"), (500, 706))
        self.assertEqual(points.resolve("L-09.75-10.25"), (495, 705))
        self.assertEqual(points.resolve("L-10.05-10"), (501, 700))

    def test_half_pixel_rounds_up_consistently(self):
        self.assertEqual(self.local_map().resolve("L-10.025-10.075"), (501, 702))

    def test_clipped_local_view_keeps_anchor_and_allows_partial_edge_cells(self):
        points = GridCoordinateMap(transforms={"L": GridTransform(
            step=20, width=349, height=251,
            anchor_x=149, anchor_y=51, anchor_col=10, anchor_row=10,
        )})
        for point_id, expected in [
            ("L-10-10.32", (149, 57)),
            ("L-02.55-07.45", (0, 0)),
            ("L-19.95-19.95", (348, 250)),
            ("L-20.00-20.00", (348, 250)),
        ]:
            with self.subTest(point_id=point_id):
                self.assertEqual(points.resolve(point_id), expected)
        for point_id in ("L-02.54-10", "L-10-07.44", "L-20.01-10", "L-10-20.01"):
            with self.subTest(point_id=point_id), self.assertRaisesRegex(ValueError, "outside"):
                points.resolve(point_id)

    def test_last_partial_global_cell_uses_true_spacing(self):
        points = self.global_map(width=350, height=250)
        self.assertEqual(points.resolve("G-03.49-02.49"), (349, 249))
        self.assertEqual(points.resolve("G-03.50-02.50"), (349, 249))
        with self.assertRaisesRegex(ValueError, "outside"):
            points.resolve("G-03.51-02")

    def test_decimals_near_clamped_boundary_do_not_interpolate_clamped_points(self):
        points = GridCoordinateMap(
            {"G-00-00": (0, 0), "G-01-00": (99, 0)},
            transforms={"G": GridTransform(100, 100, 100)},
        )
        self.assertEqual(points.resolve("G-00.90-00"), (90, 0))
        self.assertEqual(points.resolve("G-01.00-00"), points.resolve("G-01-00"))

    def test_merge_preserves_both_view_geometries_and_integer_keys(self):
        global_points = self.global_map()
        global_points["G-01-08"] = (100, 800)
        points = global_points.merged(self.local_map())
        self.assertEqual(points["G-01-08"], (100, 800))
        self.assertEqual(points.resolve("G-01.10-08"), (110, 800))
        self.assertEqual(points.resolve("L-10-10.32"), (500, 706))

    def test_rejects_malformed_or_out_of_view_ids(self):
        points = self.global_map()
        for point_id in (
            "G--1-0", "G-1--1", "G-NaN-0", "G-inf-0", "G-1e2-0",
            "G-1.-0", "G-.5-0", "G-0-0-extra", "X-1-1", "G-1-1\n", None,
            "G-10.01-0", "G-0-10.01", "L-10-10.32",
        ):
            with self.subTest(point_id=point_id), self.assertRaises(ValueError):
                points.resolve(point_id)


if __name__ == "__main__":
    unittest.main()
