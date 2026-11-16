import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {title:"twinfixeno | Healthcare Digital Twin",description:"Privacy-first healthcare digital twin workspace"};
export default function RootLayout({children}:{children:React.ReactNode}) {
 return <html lang="en"><body>{children}</body></html>;
}
