import type { Metadata } from "next";
import { Archivo, Permanent_Marker } from "next/font/google";

import { APP_NAME } from "@/lib/wording";

import "./globals.css";

// Self-hosted at build time; its width axis gives the expanded cut of the display type.
const archivo = Archivo({
  subsets: ["latin"],
  axes: ["wdth"],
  display: "swap",
  variable: "--font-archivo",
});

// The hand that writes the box's first label (components/ProductBox.tsx); nowhere else.
const marker = Permanent_Marker({
  subsets: ["latin"],
  weight: "400",
  display: "swap",
  variable: "--font-marker",
});

export const metadata: Metadata = {
  title: APP_NAME,
  description: "What a durable product really costs over time, and a better option within budget.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${archivo.variable} ${marker.variable}`}>
      <body>{children}</body>
    </html>
  );
}
