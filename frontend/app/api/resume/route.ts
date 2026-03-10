import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  const pdfPath = path.join(
    process.cwd(),
    "..",
    "knowledge",
    "Daniel_David_Resume_March_26.pdf",
  );

  const fileBuffer = await fs.promises.readFile(pdfPath);

  return new NextResponse(fileBuffer, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": 'inline; filename="Daniel_David_Resume.pdf"',
    },
  });
}

