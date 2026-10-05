"use client";

import { Login } from "@/components/Login";
import { Workspace } from "@/components/Workspace";
import { useSession } from "@/lib/session";

export default function Home() {
  const { token, ready } = useSession();
  if (!ready) return null;
  return token ? <Workspace /> : <Login />;
}
