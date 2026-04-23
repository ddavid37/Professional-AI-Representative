import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  const resumeFileName = "Daniel_David_Resume_April_26_.pdf";
  const fallbackUrl =
    "https://raw.githubusercontent.com/ddavid37/Professional-AI-Representative/main/knowledge/Daniel_David_Resume_April_26_.pdf";

  const candidates = [
    path.join(process.cwd(), "..", "knowledge", resumeFileName),
    path.join(process.cwd(), "knowledge", resumeFileName),
  ];

  for (const pdfPath of candidates) {
    try {
      const fileBuffer = await fs.promises.readFile(pdfPath);
      return new NextResponse(fileBuffer, {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": `inline; filename="${resumeFileName}"`,
        },
      });
    } catch {
      // Try next candidate.
    }
  }

  // Production fallback for environments where knowledge/ is not bundled.
  return NextResponse.redirect(fallbackUrl, 307);
}

