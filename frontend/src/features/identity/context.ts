import { createContext, useContext } from "react";
export type Role = "OWNER" | "EDITOR" | "VIEWER";
export type Organization = { id: string; name: string; role: Role; retention?: Record<string, string> };
export type Identity = { mode: "development" | "oidc"; user: { id: string; display_name: string; email: string | null } | null;
  organizations: Organization[]; csrf_token: string | null };
type IdentityContextValue = { identity: Identity | null; organization: Organization | null; selectOrganization: (id: string) => void;
  logout: () => Promise<void>; canEdit: boolean; isOwner: boolean };
// Standalone components are also used in focused tests; the application always installs the provider.
export const IdentityContext = createContext<IdentityContextValue>({ identity: null, organization: null, selectOrganization: () => {},
  logout: async () => {}, canEdit: false, isOwner: false });
export const useIdentity = () => useContext(IdentityContext);
