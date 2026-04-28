import { describe, expect, it } from "vitest";
import {
  amountUnitToIntervalSec,
  formatIntervalHuman,
  intervalSecToAmountUnit,
} from "./backtestInterval";

describe("backtestInterval", () => {
  it("round-trips common presets", () => {
    expect(intervalSecToAmountUnit(300)).toEqual({ amount: "5", unit: "min" });
    expect(amountUnitToIntervalSec(5, "min")).toBe(300);
    expect(intervalSecToAmountUnit(86400)).toEqual({ amount: "1", unit: "day" });
    expect(amountUnitToIntervalSec(2, "hr")).toBe(7200);
  });

  it("uses seconds when not divisible by minute", () => {
    expect(intervalSecToAmountUnit(90)).toEqual({ amount: "90", unit: "sec" });
  });

  it("formats human interval labels", () => {
    expect(formatIntervalHuman(86400)).toBe("1 day");
    expect(formatIntervalHuman(300)).toBe("5 minutes");
    expect(formatIntervalHuman(90)).toBe("90 seconds");
  });
});
