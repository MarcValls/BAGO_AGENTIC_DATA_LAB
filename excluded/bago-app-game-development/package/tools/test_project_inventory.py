"""Regression tests for bounded project inventory traversal."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import project_inventory


class ProjectInventoryTests(unittest.TestCase):
    def test_inventory_cap_boundaries(self):
        for count in (0, 2, 3, 4):
            with self.subTest(count=count), TemporaryDirectory() as directory:
                root = Path(directory)
                for index in range(count):
                    (root / f"{index}.txt").touch()
                with patch.object(project_inventory, "MAX_FILES", 3):
                    result = project_inventory.inspect(root)
                self.assertEqual(result["files_seen"], min(count, 3))
                self.assertEqual(result["truncated"], count > 3)

    def test_truncation_is_independent_of_symlink_filtering(self):
        for count in (3, 4):
            with self.subTest(count=count), TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                names = ["0-link.txt", "package.json", "requirements.txt", "z.txt"]
                (root / "package.json").write_text('{"react": "*"}', encoding="utf-8")
                (root / "requirements.txt").write_text("flask", encoding="utf-8")
                with (
                    patch.object(project_inventory, "MAX_FILES", 3),
                    patch.object(project_inventory.os, "walk", return_value=[
                        (str(root), [], names[:count]),
                    ]),
                    patch.object(Path, "is_symlink", autospec=True,
                                 side_effect=lambda path: path.name == "0-link.txt"),
                ):
                    result = project_inventory.inspect(root)
                self.assertEqual(result["files_seen"], 2)
                self.assertEqual(result["truncated"], count > 3)
                self.assertEqual(
                    {item["name"] for item in result["detections"]},
                    {"JavaScript/TypeScript", "React", "Python", "Flask"},
                )


if __name__ == "__main__":
    unittest.main()
