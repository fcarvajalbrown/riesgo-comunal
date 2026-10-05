import type { Metadata } from "next";
import { PublicPortal } from "@/components/public/PublicPortal";

export const metadata: Metadata = {
  title: "Riesgo en mi comuna",
  description: "Avisos y alertas oficiales vigentes y consulta de riesgo por dirección",
};

export default async function PublicPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <PublicPortal slug={slug} />;
}
