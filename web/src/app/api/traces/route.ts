import { NextResponse } from "next/server";
import mockTraces from "@/data/mock-traces.json";

export async function GET() {
  return NextResponse.json(mockTraces);
}
