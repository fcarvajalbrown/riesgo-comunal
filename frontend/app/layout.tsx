import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";

export const metadata: Metadata = {
  title: "Riesgo Comunal",
  description: "Plataforma municipal de información de riesgo de desastres",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
