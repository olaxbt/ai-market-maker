import { cookies } from "next/headers";

const COOKIE_NAME = "aimm_platform_token";

export async function setPlatformToken(token: string) {
  const jar = await cookies();
  jar.set(COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
}

export async function clearPlatformToken() {
  const jar = await cookies();
  jar.set(COOKIE_NAME, "", { httpOnly: true, path: "/", maxAge: 0 });
}

export async function getPlatformAuthHeader(): Promise<Record<string, string>> {
  const jar = await cookies();
  const tok = jar.get(COOKIE_NAME)?.value?.trim();
  return tok ? { authorization: `Bearer ${tok}` } : {};
}
