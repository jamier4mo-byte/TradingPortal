/** Browser image pipeline (F10): any pasted, dropped or picked image → WebP full (~1920px long edge)
 *  plus a 400px thumbnail, made in the browser so the server never re-encodes. Also reads a
 *  capture time from EXIF (JPEG APP1 or PNG eXIf), a macOS screenshot name, or last-modified. */

export const FULL_EDGE = 1920;
export const THUMB_EDGE = 400;

export interface PreparedImage {
  full: Blob;
  thumb: Blob;
  width: number;
  height: number;
  capturedAt: Date | null;
  timeSource: "exif" | "name" | "mtime" | "none";
  name: string;
}

async function decode(blob: Blob): Promise<ImageBitmap | HTMLImageElement> {
  if (typeof createImageBitmap === "function") {
    try {
      return await createImageBitmap(blob);
    } catch {
      /* fall through to <img> */
    }
  }
  const url = URL.createObjectURL(blob);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function sizeOf(src: ImageBitmap | HTMLImageElement): { w: number; h: number } {
  return "naturalWidth" in src ? { w: src.naturalWidth, h: src.naturalHeight } : { w: src.width, h: src.height };
}

async function encode(src: ImageBitmap | HTMLImageElement, edge: number, quality: number): Promise<{ blob: Blob; w: number; h: number }> {
  const { w, h } = sizeOf(src);
  const scale = Math.min(1, edge / Math.max(w, h));
  const tw = Math.max(1, Math.round(w * scale));
  const th = Math.max(1, Math.round(h * scale));
  const canvas: OffscreenCanvas | HTMLCanvasElement =
    typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(tw, th) : Object.assign(document.createElement("canvas"), { width: tw, height: th });
  const ctx = canvas.getContext("2d") as OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D | null;
  if (!ctx) throw new Error("No canvas");
  ctx.drawImage(src, 0, 0, tw, th);
  let blob: Blob;
  if ("convertToBlob" in canvas) {
    blob = await canvas.convertToBlob({ type: "image/webp", quality });
  } else {
    blob = await new Promise<Blob>((resolve, reject) =>
      (canvas as HTMLCanvasElement).toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/webp", quality),
    );
  }
  return { blob, w: tw, h: th };
}

export async function prepareImage(file: File | Blob, name = (file as File).name ?? "pasted.png"): Promise<PreparedImage> {
  const buf = await file.slice(0, 256 * 1024).arrayBuffer();
  const exif = readExifDate(new DataView(buf));
  const fromName = timeFromName(name);
  const mtime = "lastModified" in file && (file as File).lastModified ? new Date((file as File).lastModified) : null;
  const src = await decode(file);
  const full = await encode(src, FULL_EDGE, 0.82);
  const thumb = await encode(src, THUMB_EDGE, 0.78);
  if ("close" in src) src.close();
  const capturedAt = exif ?? fromName ?? mtime;
  return {
    full: full.blob,
    thumb: thumb.blob,
    width: full.w,
    height: full.h,
    capturedAt,
    timeSource: exif ? "exif" : fromName ? "name" : mtime ? "mtime" : "none",
    name,
  };
}

/** Image files from a paste or drop. */
export function imageFiles(dt: DataTransfer | null | undefined): File[] {
  if (!dt) return [];
  const files = Array.from(dt.files ?? []).filter((f) => f.type.startsWith("image/"));
  if (files.length) return files;
  return Array.from(dt.items ?? [])
    .filter((i) => i.kind === "file" && i.type.startsWith("image/"))
    .map((i) => i.getAsFile())
    .filter((f): f is File => !!f);
}

const MAC_SHOT = /screen\s*shot\s+(\d{4})-(\d{2})-(\d{2})\s+at\s+(\d{1,2})\.(\d{2})\.(\d{2})/i;
const STAMP = /(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[.\-:](\d{2})(?:[.\-:](\d{2}))?/;

/** "Screenshot 2026-11-05 at 23.25.13.png" → that local time. */
export function timeFromName(name: string): Date | null {
  const m = MAC_SHOT.exec(name) ?? STAMP.exec(name);
  if (!m) return null;
  const [y, mo, d, h, mi, s] = m.slice(1).map((v) => Number(v ?? 0));
  const date = new Date(y, mo - 1, d, h, mi, s || 0);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** DateTimeOriginal (0x9003) from a JPEG APP1 or PNG eXIf chunk. Local time of the camera. */
export function readExifDate(view: DataView): Date | null {
  try {
    let tiff = -1;
    if (view.getUint16(0) === 0xffd8) {
      let p = 2;
      while (p + 4 < view.byteLength) {
        const marker = view.getUint16(p);
        const len = view.getUint16(p + 2);
        if (marker === 0xffe1 && view.getUint32(p + 4) === 0x45786966) {
          tiff = p + 10;
          break;
        }
        if ((marker & 0xff00) !== 0xff00) break;
        p += 2 + len;
      }
    } else if (view.getUint32(0) === 0x89504e47) {
      let p = 8;
      while (p + 8 < view.byteLength) {
        const len = view.getUint32(p);
        const type = view.getUint32(p + 4);
        if (type === 0x65584966) {
          tiff = p + 8;
          break;
        }
        if (type === 0x49444154) break; // IDAT: no eXIf before the data
        p += 12 + len;
      }
    }
    if (tiff < 0 || tiff + 8 > view.byteLength) return null;
    const le = view.getUint16(tiff) === 0x4949;
    const u16 = (o: number) => view.getUint16(o, le);
    const u32 = (o: number) => view.getUint32(o, le);
    const ifd0 = tiff + u32(tiff + 4);
    const findTag = (ifd: number, tag: number): number | null => {
      if (ifd + 2 > view.byteLength) return null;
      const n = u16(ifd);
      for (let i = 0; i < n; i++) {
        const e = ifd + 2 + i * 12;
        if (e + 12 > view.byteLength) return null;
        if (u16(e) === tag) return e;
      }
      return null;
    };
    const exifPtr = findTag(ifd0, 0x8769);
    if (!exifPtr) return null;
    const exifIfd = tiff + u32(exifPtr + 8);
    const entry = findTag(exifIfd, 0x9003) ?? findTag(exifIfd, 0x9004);
    if (!entry) return null;
    const count = u32(entry + 4);
    const off = count > 4 ? tiff + u32(entry + 8) : entry + 8;
    let s = "";
    for (let i = 0; i < Math.min(count, 19); i++) s += String.fromCharCode(view.getUint8(off + i));
    const m = /^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})/.exec(s);
    if (!m) return null;
    const [y, mo, d, h, mi, sec] = m.slice(1).map(Number);
    return new Date(y, mo - 1, d, h, mi, sec);
  } catch {
    return null;
  }
}
