from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image

from depth_scape.hidden_surface import (
    HiddenSurfaceConfig,
    HiddenSurfaceContractError,
    plan_hidden_surfaces,
)
from depth_scape.hidden_surface_artifacts import (
    HiddenSurfaceArtifactError,
    write_hidden_surface_artifacts,
)
from depth_scape.mesh import MeshBuildConfig, build_continuous_depth_mesh
from depth_scape.mesh_run import LoadedMeshRun
from depth_scape.mesh_visibility import MeshVisibilityConfig, MeshVisibilityPlan


def _visibility_plan() -> MeshVisibilityPlan:
    height, width = 3, 8
    positions = (-1.0, 0.0, 1.0)
    coverages = [np.ones((height, width), dtype=np.bool_) for _ in positions]
    depths = [np.full((height, width), 0.4, dtype=np.float32) for _ in positions]

    coverages[0][:, 0] = False
    coverages[0][:, 4] = False
    depths[0][:, 0] = -np.inf
    depths[0][:, 4] = -np.inf
    depths[0][:, 3] = 0.1
    depths[0][:, 5] = 0.8

    coverages[2][:, 3] = False
    coverages[2][:, 7] = False
    depths[2][:, 3] = -np.inf
    depths[2][:, 7] = -np.inf
    depths[2][:, 2] = 0.9
    depths[2][:, 4] = 0.2

    left_holes = ~coverages[0]
    right_holes = ~coverages[2]
    center = np.zeros((height, width, 3), dtype=np.uint8)
    return MeshVisibilityPlan(
        center_view=center,
        left_view=center.copy(),
        right_view=center.copy(),
        center_geometry_holes=np.zeros((height, width), dtype=np.bool_),
        left_view_holes=left_holes,
        right_view_holes=right_holes,
        all_view_holes=left_holes | right_holes,
        render_width=width,
        render_height=height,
        max_near_shift_pixels=2,
        camera_positions=positions,
        render_seconds=(0.0, 0.0, 0.0),
        sampled_coverages=tuple(coverages),
        sampled_depths=tuple(depths),
        default_view_pixel_identical=True,
    )


def _loaded_mesh() -> LoadedMeshRun:
    texture = np.zeros((3, 8, 3), dtype=np.uint8)
    depth = np.full((3, 8), 0.4, dtype=np.float32)
    result = build_continuous_depth_mesh(
        Image.fromarray(texture, mode="RGB"),
        depth,
        config=MeshBuildConfig(max_mesh_dimension=8),
    )
    return LoadedMeshRun(
        texture=texture,
        vertices=result.vertices,
        texture_coordinates=result.texture_coordinates,
        faces=result.faces,
        source_sha256="a" * 64,
        manifest_sha256="b" * 64,
        manifest_path=Path("mesh.json"),
        algorithm_id="continuous-depth-grid-cut",
        algorithm_version="0.1",
    )


class HiddenSurfaceTests(unittest.TestCase):
    def test_maps_only_depth_consistent_interior_holes_to_one_request_grid(self) -> None:
        plan = plan_hidden_surfaces(_visibility_plan())

        expected_request = np.zeros((3, 8), dtype=np.bool_)
        expected_request[:, 3:5] = True
        np.testing.assert_array_equal(plan.request_mask, expected_request)
        self.assertEqual(plan.required_generated_channels, ("rgb", "relative_depth"))
        np.testing.assert_allclose(plan.relative_depth_hint[:, 3], 0.2)
        np.testing.assert_allclose(plan.relative_depth_hint[:, 4], 0.1)
        np.testing.assert_allclose(plan.max_relative_depth_exclusive[:, 3], 0.9)
        np.testing.assert_allclose(plan.max_relative_depth_exclusive[:, 4], 0.8)
        self.assertTrue(np.isnan(plan.relative_depth_hint[:, :3]).all())
        self.assertTrue((plan.request_observation_count[expected_request] == 1).all())

        expected_mapped = np.zeros((3, 8), dtype=np.bool_)
        expected_mapped[:, 3:5] = True
        expected_unresolved = np.zeros((3, 8), dtype=np.bool_)
        expected_unresolved[:, 0] = True
        expected_unresolved[:, 7] = True
        np.testing.assert_array_equal(plan.all_mapped_view_holes, expected_mapped)
        np.testing.assert_array_equal(plan.all_border_view_holes, expected_unresolved)
        self.assertFalse(plan.all_ambiguous_depth_view_holes.any())
        np.testing.assert_array_equal(plan.all_unresolved_view_holes, expected_unresolved)
        self.assertFalse(plan.mapped_view_holes[1].any())
        self.assertFalse(plan.unresolved_view_holes[1].any())

    def test_leaves_wrong_depth_order_and_small_jumps_unresolved(self) -> None:
        visibility = _visibility_plan()
        wrong_depths = list(visibility.sampled_depths)
        wrong_right = wrong_depths[2].copy()
        wrong_right[:, 2] = 0.2
        wrong_right[:, 4] = 0.9
        wrong_depths[2] = wrong_right

        plan = plan_hidden_surfaces(
            replace(visibility, sampled_depths=tuple(wrong_depths)),
            config=HiddenSurfaceConfig(min_depth_separation=0.75),
        )

        self.assertFalse(plan.request_mask.any())
        expected_ambiguous = visibility.all_view_holes.copy()
        expected_ambiguous[:, 0] = False
        expected_ambiguous[:, 7] = False
        np.testing.assert_array_equal(
            plan.all_ambiguous_depth_view_holes,
            expected_ambiguous,
        )
        np.testing.assert_array_equal(
            plan.all_unresolved_view_holes,
            visibility.all_view_holes,
        )

    def test_rejects_invalid_config_and_misaligned_view_arrays(self) -> None:
        visibility = _visibility_plan()
        invalid_configs = (
            HiddenSurfaceConfig(min_depth_separation=0.0),
            HiddenSurfaceConfig(min_depth_separation=1.1),
            HiddenSurfaceConfig(max_request_pixels=0),
        )
        for config in invalid_configs:
            with self.subTest(config=config), self.assertRaises(HiddenSurfaceContractError):
                plan_hidden_surfaces(visibility, config=config)

        with self.assertRaises(HiddenSurfaceContractError):
            plan_hidden_surfaces(replace(visibility, sampled_depths=visibility.sampled_depths[:2]))

    def test_writes_coupled_request_contract_without_generated_content(self) -> None:
        visibility = _visibility_plan()
        plan = plan_hidden_surfaces(visibility)
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            artifacts = write_hidden_surface_artifacts(
                output_dir=output_dir,
                mesh=_loaded_mesh(),
                visibility=visibility,
                visibility_config=MeshVisibilityConfig(),
                plan=plan,
                config=HiddenSurfaceConfig(),
                elapsed_seconds=0.1,
                overwrite=False,
            )

            with Image.open(artifacts.request_mask) as opened:
                saved_mask = np.asarray(opened).copy() == 255
            np.testing.assert_array_equal(saved_mask, plan.request_mask)
            saved_hint = np.load(artifacts.relative_depth_hint, allow_pickle=False)
            np.testing.assert_array_equal(saved_hint, plan.relative_depth_hint)
            manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["generationRequest"]["requiredChannels"],
                ["rgb", "relative_depth"],
            )
            self.assertFalse(manifest["source"]["observedRgbModified"])
            self.assertEqual(manifest["result"]["requestPixels"], 6)
            self.assertIn("does not contain either", manifest["warnings"][0])

            with self.assertRaises(HiddenSurfaceArtifactError):
                write_hidden_surface_artifacts(
                    output_dir=output_dir,
                    mesh=_loaded_mesh(),
                    visibility=visibility,
                    visibility_config=MeshVisibilityConfig(),
                    plan=plan,
                    config=HiddenSurfaceConfig(),
                    elapsed_seconds=0.1,
                    overwrite=False,
                )


if __name__ == "__main__":
    unittest.main()
