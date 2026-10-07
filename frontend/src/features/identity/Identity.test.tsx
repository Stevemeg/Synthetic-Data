// @vitest-environment jsdom
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { IdentityProvider, EditorRoute } from "./Identity";
import { IdentityContext } from "./context";

const transport = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), defaults: { baseURL: "http://127.0.0.1:5000" } }));
vi.mock("../../api/client", () => ({ api: transport, configureIdentity: vi.fn(), errorMessage: () => "Platform unavailable" }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

test("a verified identity without membership can sign out", async () => {
  transport.get.mockResolvedValue({ data: { mode: "oidc", user: { id: "user-demo", display_name: "Demo researcher" }, organizations: [], csrf_token: "fixture-csrf" } });
  transport.post.mockResolvedValue({ data: { signed_out: true } });
  render(<MemoryRouter><IdentityProvider><p>Workspace content</p></IdentityProvider></MemoryRouter>);
  expect(await screen.findByText(/No organization membership/)).toBeTruthy();
  expect(screen.queryByText("Workspace content")).toBeNull();
  await userEvent.setup().click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("link", { name: "Sign in" })).toBeTruthy();
  expect(transport.post).toHaveBeenCalledWith("/api/v1/auth/logout");
});

test("viewer and missing identity fail closed for submission routes", () => {
  const value = { identity: null, organization: null, canEdit: false, isOwner: false, selectOrganization: () => {}, logout: async () => {} };
  render(<IdentityContext.Provider value={value}><EditorRoute><button>Submit generation</button></EditorRoute></IdentityContext.Provider>);
  expect(screen.queryByRole("button", { name: "Submit generation" })).toBeNull();
  expect(screen.getByText(/viewer role permits reading evidence/)).toBeTruthy();
});
