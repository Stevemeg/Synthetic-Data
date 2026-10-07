// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { ActivityView } from "./Workspace";

afterEach(cleanup);

test("activity distinguishes authenticated people, workers and unauthenticated callers", () => {
  const common = { created_at: "2026-01-01T12:00:00Z", entity_id: "fixture-resource", entity_type: "PROJECT" };
  render(<ActivityView items={[
    { ...common, id: "user-event", event_type: "PROJECT_CREATED", actor: "user", user_id: "fixture-user", request_id: "fixture-request" },
    { ...common, id: "worker-event", event_type: "JOB_SUCCEEDED", actor: "worker" },
    { ...common, id: "anonymous-event", event_type: "PROJECT_CREATED", actor: "anonymous" },
  ]} />);
  expect(screen.getByText("Authenticated user")).toBeTruthy();
  expect(screen.getByText("Worker")).toBeTruthy();
  expect(screen.getByText("Unauthenticated caller")).toBeTruthy();
  expect(screen.queryByText("System")).toBeNull();
});
