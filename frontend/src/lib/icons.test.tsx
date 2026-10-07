// Unit tests for the hand-drawn icon set in `icons.tsx`.
//
// The module's whole point is a closed, finite set of components that all
// share one visual contract (24x24 viewBox, currentColor stroke, no fill,
// decorative by default) and scale uniformly via `size`. These tests exercise
// that contract through rendering and DOM assertions rather than the private
// `paths` map, and check the "closed set" guarantee the file's own comment
// calls out: a name that is not in `ICON_NAMES` is not a usable icon.
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ICON_NAMES, Icons } from "./icons";

describe("ICON_NAMES / Icons", () => {
  it("lists a non-empty, finite set of icon names", () => {
    expect(ICON_NAMES.length).toBeGreaterThan(0);
  });

  it("exposes exactly one component per name in ICON_NAMES, and nothing else", () => {
    expect(Object.keys(Icons).sort()).toEqual([...ICON_NAMES].sort());
  });

  it("has no undefined or non-function entries for any listed name", () => {
    for (const name of ICON_NAMES) {
      expect(typeof Icons[name]).toBe("function");
    }
  });

  it("treats a name outside the set as absent rather than a blank icon", () => {
    expect(Icons["NotARealIcon"]).toBeUndefined();
  });
});

describe("rendering any icon in the set", () => {
  it("renders an svg element for every listed name", () => {
    for (const name of ICON_NAMES) {
      const Icon = Icons[name];
      const { container, unmount } = render(<Icon />);
      expect(container.querySelector("svg")).not.toBeNull();
      unmount();
    }
  });

  it("shares one 24x24 viewBox and stroke-based style across the whole set", () => {
    for (const name of ICON_NAMES) {
      const Icon = Icons[name];
      const { container, unmount } = render(<Icon />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("viewBox", "0 0 24 24");
      expect(svg).toHaveAttribute("fill", "none");
      expect(svg).toHaveAttribute("stroke", "currentColor");
      unmount();
    }
  });

  it("gives each icon distinct markup (they are not all the same path)", () => {
    const { container: plusContainer } = render(<Icons.Plus />);
    const { container: xContainer } = render(<Icons.X />);
    expect(plusContainer.querySelector("svg")?.innerHTML).not.toEqual(
      xContainer.querySelector("svg")?.innerHTML
    );
  });
});

describe("size prop", () => {
  it("defaults to a 16px square", () => {
    const { container } = render(<Icons.Check />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "16");
    expect(svg).toHaveAttribute("height", "16");
  });

  it("scales both width and height when size is set", () => {
    const { container } = render(<Icons.Check size={32} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "32");
    expect(svg).toHaveAttribute("height", "32");
  });
});

describe("decorative by default", () => {
  it("marks the svg aria-hidden so screen readers skip it", () => {
    const { container } = render(<Icons.Bell />);
    expect(container.querySelector("svg")).toHaveAttribute(
      "aria-hidden",
      "true"
    );
  });
});

describe("forwarding arbitrary svg/html props", () => {
  it("passes through className and a click handler the way a caller would use them", () => {
    const onClick = vi.fn();
    const { container } = render(
      <Icons.Trash className="text-red-500" onClick={onClick} />
    );
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("text-red-500");
    fireEvent.click(svg as Element);
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe("the fixed visual contract cannot be overridden by caller props", () => {
  // The <svg> spreads `...props` first and then re-states width, height,
  // fill, stroke and aria-hidden explicitly, so a caller passing those same
  // attributes does not get to silently change the icon set's look. That
  // ordering is the part a careless edit (e.g. moving the spread last) would
  // break without any visible sign in isolation -- this pins it down.
  it("ignores a caller-supplied width/height/fill/stroke/aria-hidden in favour of the fixed ones", () => {
    const { container } = render(
      <Icons.Plus
        width={999}
        height={999}
        fill="red"
        stroke="blue"
        aria-hidden="false"
      />
    );
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "16");
    expect(svg).toHaveAttribute("height", "16");
    expect(svg).toHaveAttribute("fill", "none");
    expect(svg).toHaveAttribute("stroke", "currentColor");
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });
});
