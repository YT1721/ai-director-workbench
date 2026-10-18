import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VersionRail } from "./VersionRail";
import type { AssetVersion } from "../../types/assets";

describe("VersionRail", () => {
  it("allows a locked version to be unlocked before replacing it", () => {
    const lockedVersion: AssetVersion = {
      id: "version-1",
      version_number: 1,
      asset_path: "scene.png",
      asset_url: "/local-assets/P001/scene.png",
      status: "locked",
      created_at: "2026-07-29T00:00:00Z",
    };
    const onTransition = vi.fn();

    render(
      <VersionRail
        versions={[lockedVersion]}
        kind="scene"
        assetName="训练场"
        onTransition={onTransition}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "解锁" }));

    expect(onTransition).toHaveBeenCalledWith("scene", "version-1", "unlock");
  });
});
