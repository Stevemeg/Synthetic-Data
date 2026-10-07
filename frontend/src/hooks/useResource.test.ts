// @vitest-environment jsdom
import { act, renderHook, cleanup } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { useResource } from "./useResource";
import { api } from "../api/client";
vi.mock("../api/client", () => ({
  api: { get: vi.fn() },
  errorMessage: () => "Platform temporarily unavailable",
}));
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});
test("polls with backoff and stops after a terminal response", async () => {
  vi.useFakeTimers();
  vi.mocked(api.get)
    .mockResolvedValueOnce({ data: { status: "QUEUED" } })
    .mockResolvedValueOnce({ data: { status: "RUNNING" } })
    .mockResolvedValueOnce({ data: { status: "SUCCEEDED" } });
  const { result } = renderHook(() =>
    useResource<{ status: string }>("/run", true),
  );
  await act(async () => {
    await Promise.resolve();
  });
  expect(result.current.data?.status).toBe("QUEUED");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3900);
  });
  expect(result.current.data?.status).toBe("RUNNING");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5100);
  });
  expect(result.current.data?.status).toBe("SUCCEEDED");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(60000);
  });
  expect(api.get).toHaveBeenCalledTimes(3);
});
test("recovers from a temporary failure and cancels pending polling on unmount", async () => {
  vi.useFakeTimers();
  vi.mocked(api.get)
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ data: { status: "RUNNING" } });
  const { result, unmount } = renderHook(() =>
    useResource<{ status: string }>("/run", true),
  );
  await act(async () => {
    await Promise.resolve();
  });
  expect(result.current.error).toMatch(/temporarily unavailable/);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(6000);
  });
  expect(result.current.error).toBe("");
  expect(result.current.data?.status).toBe("RUNNING");
  const signal = vi.mocked(api.get).mock.calls[0][1]?.signal;
  unmount();
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(60000);
  });
  expect(api.get).toHaveBeenCalledTimes(2);
});
