import { describe, expect, it } from "vitest";
import { getDatePolicy, toApiDate } from "../src/utils/dates";

describe("date policy", () => {
  it("uses the latest seven days and limits selection to this and last month", () => {
    const policy = getDatePolicy(new Date(2026, 0, 4));

    expect(toApiDate(policy.initial.from!)).toBe("2025-12-29");
    expect(toApiDate(policy.initial.to!)).toBe("2026-01-04");
    expect(toApiDate(policy.min)).toBe("2025-12-01");
    expect(toApiDate(policy.max)).toBe("2026-01-31");
  });
});
