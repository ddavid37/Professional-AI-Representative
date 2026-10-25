import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const RESUME_FILE = "Daniel_David_CV_.pdf";
const GITHUB_RAW =
  "https://raw.githubusercontent.com/ddavid37/Professional-AI-Representative/main/knowledge/Daniel_David_CV_.pdf";

function pdfResponse(body: Uint8Array) {
  // Copy into a plain ArrayBuffer-backed view; Buffer is not a valid BodyInit type.
  return new NextResponse(new Uint8Array(body), {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `inline; filename="${RESUME_FILE}"`,
      "Cache-Control": "public, max-age=300",
    },
  });
}

export async function GET() {
  const candidates = [
    path.join(process.cwd(), "..", "knowledge", RESUME_FILE),
    path.join(process.cwd(), "knowledge", RESUME_FILE),
  ];

  for (const pdfPath of candidates) {
    try {
      return pdfResponse(await fs.promises.readFile(pdfPath));
    } catch {
      // Try next candidate, then GitHub.
    }
  }

  // Vercel frontend root is frontend/, so knowledge/ is not on disk.
  // Proxy the bytes — do not redirect. GitHub refuses iframe embedding.
  try {
    const remote = await fetch(GITHUB_RAW, { cache: "no-store" });
    if (!remote.ok) {
      return new NextResponse("Resume PDF not found.", { status: 404 });
    }
    return pdfResponse(Buffer.from(await remote.arrayBuffer()));
  } catch {
    return new NextResponse("Resume PDF not found.", { status: 404 });
  }
}
